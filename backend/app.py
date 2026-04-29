"""ECHO ARK — FastAPI backend."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

import aiofiles
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()

from pipeline import parser, hexgraph, scorer, classifier, remediation
from services.ollama_service import OllamaService
from services.redis_service import RedisService
from services.mongodb_service import MongoService
from services.obsidian_service import ObsidianService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ollama = OllamaService()
redis_svc = RedisService()
mongo_svc = MongoService()
obsidian_svc: ObsidianService | None = None

_active_topic: dict = {"topic": "photosynthesis", "grade": 6}
_ws_clients: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global obsidian_svc
    await redis_svc.connect()
    try:
        await mongo_svc.connect()
    except Exception as e:
        logger.warning("MongoDB unavailable at startup: %s", e)

    hexgraph.load_graph()

    obsidian_svc = ObsidianService(
        mongo_service=mongo_svc,
        redis_service=redis_svc,
        ollama_service=ollama,
    )
    asyncio.create_task(obsidian_svc.index_vault())
    asyncio.create_task(obsidian_svc.watch_vault())
    asyncio.create_task(_sync_loop())

    yield

    await ollama.close()
    await redis_svc.close()
    await mongo_svc.close()


app = FastAPI(title="ECHO ARK", version="1.0.0", lifespan=lifespan)

from dashboard_routes import router as dashboard_router
from content_routes import router as content_router
from attendance_routes import router as attendance_router
from identify_routes import router as identify_router
app.include_router(dashboard_router)
app.include_router(content_router)
app.include_router(attendance_router)
app.include_router(identify_router)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ──────────────────────────────────────────────────────────

class AnalyseRequest(BaseModel):
    student_id: str
    student_name: str = "Student"
    topic: str = "photosynthesis"
    answer_text: str
    language: str = "english"
    offline: bool = False


class TopicRequest(BaseModel):
    topic: str
    grade: int = 6


class ChatRequest(BaseModel):
    query: str
    image_path: str | None = None
    history: list[dict] = []


# ── Core pipeline ────────────────────────────────────────────────────────────

async def run_pipeline(req: AnalyseRequest) -> dict:
    claims = parser.parse(req.answer_text)
    match_result = hexgraph.match(claims, req.topic)
    drift = scorer.calculate_drift(match_result, req.topic)
    fp = classifier.classify(drift, match_result)

    topic_data = hexgraph.get_topic(req.topic) or {}
    correct_model = topic_data.get("correct_model", "")

    remedy = await remediation.get_remediation(
        topic=req.topic,
        fingerprint=fp,
        student_answer=req.answer_text,
        language=req.language,
        ollama_service=ollama if await ollama.is_available() else None,
        correct_model=correct_model,
    )

    result = {
        "student_id": req.student_id,
        "student_name": req.student_name,
        "topic": req.topic,
        "fingerprint": fp,
        "drift_score": drift,
        "activated_nodes": match_result["activated_nodes"],
        "skipped_nodes": match_result["skipped_nodes"],
        "what_they_said": req.answer_text,
        "what_is_wrong": remedy.get("what_is_wrong", ""),
        "story_fix": remedy.get("story_fix", ""),
        "follow_up_question": remedy.get("follow_up_question", ""),
        "peer_suggestion": "",
        "language": req.language,
        "timestamp": datetime.utcnow().isoformat(),
    }

    peer = await _find_peer(req.student_id, fp)
    if peer:
        result["peer_suggestion"] = f"Ask {peer} — they fixed this exact gap today"

    return result


async def _find_peer(student_id: str, fingerprint: str) -> str | None:
    try:
        students = await redis_svc.get_all_students()
        for s in students:
            if s.get("student_id") != student_id and s.get("fingerprint") == fingerprint:
                return s.get("student_name", "a classmate")
    except Exception:
        pass
    return None


# ── Routes ───────────────────────────────────────────────────────────────────

@app.post("/analyse")
async def analyse(req: AnalyseRequest):
    if not req.answer_text.strip():
        raise HTTPException(400, "answer_text is required")

    result = await run_pipeline(req)

    await redis_svc.save_student_result(result)
    await redis_svc.enqueue_for_sync(result)
    await _broadcast(result)

    # Award 5 points for submitting an answer
    from content_routes import award_submission_points
    asyncio.create_task(award_submission_points(req.student_id, req.student_name))

    # Immediately persist to MongoDB (don't wait for the slow sync loop)
    try:
        if await mongo_svc.is_available():
            # Upsert latest state into students collection
            await mongo_svc.db.students.replace_one(
                {"student_id": result["student_id"]},
                result,
                upsert=True,
            )
            # Append a history record
            history_record = {
                "student_id":  result["student_id"],
                "drift_score": result["drift_score"],
                "fingerprint": result["fingerprint"],
                "topic":       result["topic"],
                "timestamp":   result["timestamp"],
            }
            await mongo_svc.db.students_history.insert_one(history_record)
    except Exception:
        pass

    return JSONResponse(result)


@app.get("/api/class-data")
async def class_data():
    redis_students = await redis_svc.get_all_students()
    redis_ids = {s.get("student_id") for s in redis_students}

    # Merge with all students stored in MongoDB (seeded + previously synced)
    mongo_students = []
    try:
        if await mongo_svc.is_available():
            cursor = mongo_svc.db.students.find({}, {"_id": 0}).sort("timestamp", -1).limit(200)
            all_mongo = await cursor.to_list(length=200)
            mongo_students = [s for s in all_mongo if s.get("student_id") not in redis_ids]
    except Exception:
        pass

    all_students = redis_students + mongo_students
    return JSONResponse({"students": all_students, "count": len(all_students)})


@app.get("/api/classmates")
async def classmates(exclude: str = "", topic: str = "", limit: int = 6):
    """Return other students (same topic) for the Ask a Classmate feature."""
    peers = []
    try:
        if await mongo_svc.is_available():
            query = {}
            if exclude:
                query["student_id"] = {"$ne": exclude}
            if topic:
                query["topic"] = topic
            cursor = mongo_svc.db.students.find(
                query,
                {"_id": 0, "student_id": 1, "student_name": 1, "fingerprint": 1,
                 "drift_score": 1, "topic": 1, "what_is_wrong": 1, "remediation": 1}
            ).limit(limit)
            peers = await cursor.to_list(length=limit)
    except Exception:
        pass
    return JSONResponse({"peers": peers})


@app.post("/api/set-topic")
async def set_topic(req: TopicRequest):
    _active_topic["topic"] = req.topic
    _active_topic["grade"] = req.grade
    topic_data = hexgraph.get_topic(req.topic)
    return {"status": "ok", "hexgraph_loaded": topic_data is not None, "topic": req.topic}


@app.get("/api/current-topic")
async def current_topic():
    return _active_topic


@app.post("/api/voice-transcribe")
async def voice_transcribe(audio: UploadFile = File(...), language: str = Form("english")):
    """Proxy to Dwani.ai STT — fallback returns placeholder."""
    import httpx
    DWANI_KEY = os.getenv("DWANI_API_KEY", "")
    if not DWANI_KEY:
        return {"transcript": "[Voice transcription unavailable — Dwani API key not set]"}
    try:
        audio_bytes = await audio.read()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://dwani.ai/api/transcribe",
                headers={"Authorization": f"Bearer {DWANI_KEY}"},
                files={"audio": (audio.filename, audio_bytes, audio.content_type)},
                data={"language": language},
            )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("Dwani transcription failed: %s", e)
        return {"transcript": "", "error": str(e)}


@app.post("/api/obsidian/query")
async def obsidian_query(req: ChatRequest):
    if not obsidian_svc:
        raise HTTPException(503, "Obsidian service not ready")
    if not os.getenv("OPENAI_API_KEY") and not await ollama.is_available():
        raise HTTPException(503, "No AI backend available — set OPENAI_API_KEY or start Ollama")
    answer = await obsidian_svc.answer_query(req.query, image_path=req.image_path)
    return {"answer": answer}


@app.post("/api/obsidian/index")
async def obsidian_index():
    if not obsidian_svc:
        raise HTTPException(503, "Obsidian service not ready")
    count = await obsidian_svc.index_vault()
    return {"indexed": count}


@app.post("/api/image-chat")
async def image_chat(
    question:   str              = Form(...),
    image:      UploadFile | None = File(None),
    student_id: str              = Form(""),
):
    image_bytes = await image.read() if image else None

    # ── OpenAI (primary) ──────────────────────────────────────────────────────
    OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
    if OPENAI_KEY:
        try:
            import base64 as _b64
            import imghdr
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=OPENAI_KEY)
            if image_bytes:
                fmt = imghdr.what(None, image_bytes) or "jpeg"
                media_map  = {"jpeg": "image/jpeg", "png": "image/png",
                              "webp": "image/webp", "gif": "image/gif"}
                media_type = media_map.get(fmt, "image/jpeg")
                content = [
                    {"type": "image_url", "image_url": {
                        "url": f"data:{media_type};base64,{_b64.standard_b64encode(image_bytes).decode()}"}},
                    {"type": "text", "text": question},
                ]
            else:
                content = question
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=1024,
                messages=[{"role": "user", "content": content}],
            )
            return JSONResponse({"answer": resp.choices[0].message.content})
        except Exception as oai_err:
            logger.warning("OpenAI failed (%s) — falling back to Ollama", oai_err)

    # ── Ollama (fallback) ────────────────────────────────────────────────────
    if not await ollama.is_available():
        return JSONResponse({"error": "Ollama is not running. Start it with: ollama serve"}, status_code=503)

    try:
        if image_bytes:
            answer = await ollama.generate_with_image(question, image_bytes=image_bytes)
        else:
            answer = await ollama.generate(question)
    except Exception as vision_err:
        logger.warning("Vision model failed (%s) — falling back to text model", vision_err)
        try:
            fallback_prompt = (
                f"A student is looking at an image and asked: {question}\n\n"
                "Answer based on the question text alone. "
                "Give a clear educational answer for a Grade 6 student."
            )
            answer = await ollama.generate(fallback_prompt)
        except Exception as text_err:
            return JSONResponse({"error": f"Both vision and text models failed: {text_err}"}, status_code=500)

    return JSONResponse({"answer": answer})


@app.get("/api/status")
async def status():
    return {
        "ollama": await ollama.is_available(),
        "redis": await redis_svc.is_available(),
        "mongo": await mongo_svc.is_available(),
        "obsidian_configured": obsidian_svc.is_configured() if obsidian_svc else False,
        "current_topic": _active_topic,
        "ollama_models": await ollama.list_models(),
    }


@app.delete("/api/session")
async def clear_session():
    await redis_svc.clear_session()
    return {"status": "cleared"}


# ── WebSocket for real-time dashboard ────────────────────────────────────────

@app.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        students = await redis_svc.get_all_students()
        await ws.send_json({"type": "init", "students": students})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


async def _broadcast(data: dict):
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json({"type": "new_result", "data": data})
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


# ── Background sync: Redis queue → MongoDB ───────────────────────────────────

async def _sync_loop():
    while True:
        await asyncio.sleep(10)
        try:
            if not await mongo_svc.is_available():
                continue
            items = await redis_svc.dequeue_all_for_sync()
            if items:
                count = await mongo_svc.bulk_upsert(items)
                logger.info("Synced %d records to MongoDB", count)
        except Exception as e:
            logger.warning("Sync loop error: %s", e)
