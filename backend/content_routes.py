"""Content generation routes — notes, MCQ quiz, leaderboard, rewards, file upload."""

import asyncio
import io
import json
import logging
import os
import re
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request models ────────────────────────────────────────────────────────────

class GenerateNotesReq(BaseModel):
    topic: str
    context: str = ""

class GenerateQuizReq(BaseModel):
    topic: str
    num_questions: int = 5
    context: str = ""

class QuizSubmitReq(BaseModel):
    student_id: str
    student_name: str
    topic: str
    answers: list[int]


# ── File text extraction ──────────────────────────────────────────────────────

async def _extract_text(file: UploadFile) -> str:
    data  = await file.read()
    fname = (file.filename or "").lower()

    if fname.endswith(".pdf"):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages[:20])
        except ImportError:
            return data.decode("utf-8", errors="ignore")[:6000]

    if fname.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            return data.decode("utf-8", errors="ignore")[:6000]

    return data.decode("utf-8", errors="ignore")[:6000]


def _parse_json_from_llm(text: str):
    """Extract the first JSON array from an LLM response that may have extra prose."""
    # Strip markdown code fences (Gemini wraps JSON in ```json ... ```)
    text = re.sub(r'```(?:json)?\s*', '', text).strip().rstrip('`').strip()

    # Greedy match to capture the full outer array (not a nested one)
    m = re.search(r'\[.*\]', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # Fix trailing commas and retry
    cleaned = re.sub(r',\s*([}\]])', r'\1', text)
    m = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None


# ── AI generation helper — Gemini primary, Ollama fallback ───────────────────

async def _ai_generate(prompt: str) -> str:
    """Try OpenAI first; fall back to Ollama if unavailable."""
    key = os.getenv("OPENAI_API_KEY", "")
    if key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=key)
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.warning("OpenAI generation failed: %s — trying Ollama", e)

    from app import ollama
    if await ollama.is_available():
        return await ollama.generate(prompt)

    raise RuntimeError("No AI backend available — set OPENAI_API_KEY or start Ollama")


# ── Upload reference material ─────────────────────────────────────────────────

@router.post("/api/content/upload")
async def upload_content(
    file:  UploadFile = File(...),
    topic: str        = Form("general"),
):
    from app import mongo_svc
    text = await _extract_text(file)
    text = text[:8000]

    try:
        if await mongo_svc.is_available():
            await mongo_svc.db.content_store.replace_one(
                {"topic": topic},
                {
                    "topic":       topic,
                    "filename":    file.filename,
                    "text":        text,
                    "uploaded_at": datetime.utcnow().isoformat(),
                },
                upsert=True,
            )
    except Exception as e:
        logger.warning("upload save failed: %s", e)

    return JSONResponse({
        "status":   "ok",
        "topic":    topic,
        "filename": file.filename,
        "chars":    len(text),
        "preview":  text[:300],
    })


# ── Generate study notes ──────────────────────────────────────────────────────

@router.post("/api/content/generate-notes")
async def generate_notes(req: GenerateNotesReq):
    from app import mongo_svc

    context = req.context
    if not context:
        try:
            if await mongo_svc.is_available():
                doc = await mongo_svc.db.content_store.find_one({"topic": req.topic})
                if doc:
                    context = doc.get("text", "")[:2000]
        except Exception:
            pass

    topic_plain = req.topic.replace("_", " ").title()
    ref_block   = f"Reference material:\n{context[:2000]}\n\n" if context else ""

    prompt = f"""{ref_block}You are a science teacher writing study notes for Grade 6 students (age 11-12) in India.

Topic: {topic_plain}

Write clear, simple notes with EXACTLY these 5 sections, each on a new line with the label:

DEFINITION: (one clear sentence — what this topic is)

KEY STEPS:
1. (first step)
2. (second step)
3. (third step)
4. (fourth step)
5. (fifth step)

EASY TRICK TO REMEMBER: (one clever sentence or analogy that makes it stick)

REAL WORLD EXAMPLE: (one example from everyday life a student in India would recognise)

COMMON MISTAKE: (the one thing students most often get wrong and why it is wrong)

Keep the total under 280 words. Write in plain English — no bullet symbols, no markdown."""

    try:
        notes_text = await _ai_generate(prompt)
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    doc = {
        "topic":        req.topic,
        "notes":        notes_text.strip(),
        "generated_at": datetime.utcnow().isoformat(),
        "has_context":  bool(context),
    }
    try:
        if await mongo_svc.is_available():
            await mongo_svc.db.notes.replace_one({"topic": req.topic}, doc, upsert=True)
    except Exception:
        pass

    return JSONResponse(doc)


# ── Generate MCQ quiz ─────────────────────────────────────────────────────────

@router.post("/api/content/generate-quiz")
async def generate_quiz(req: GenerateQuizReq):
    from app import mongo_svc

    n = min(max(req.num_questions, 2), 10)

    context = req.context
    if not context:
        try:
            if await mongo_svc.is_available():
                doc = await mongo_svc.db.content_store.find_one({"topic": req.topic})
                if doc:
                    context = doc.get("text", "")[:1500]
                else:
                    notes = await mongo_svc.db.notes.find_one({"topic": req.topic})
                    if notes:
                        context = notes.get("notes", "")[:1500]
        except Exception:
            pass

    ref_block   = f"Reference:\n{context}\n\n" if context else ""
    topic_plain = req.topic.replace("_", " ")

    prompt = f"""{ref_block}Create exactly {n} multiple-choice questions about "{topic_plain}" for Grade 6 students.

Return ONLY a JSON array. Nothing else — no intro sentence, no explanation after.

[
  {{
    "question": "Full question text ending with ?",
    "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
    "correct": 1,
    "explanation": "One sentence explaining why this answer is correct."
  }}
]

Rules:
- "correct" is the 0-based index (0=A, 1=B, 2=C, 3=D)
- All 4 options must be plausible, not obviously wrong
- Test understanding, not just memory
- Simple language suitable for 11-12 year olds
- Generate exactly {n} items in the array"""

    try:
        raw = await _ai_generate(prompt)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    questions = _parse_json_from_llm(raw)

    if not questions:
        logger.warning("Quiz JSON parse failed for topic %s, using fallback", req.topic)
        questions = _fallback_quiz(req.topic)[:n]

    # Validate each question
    valid = []
    for q in questions:
        if isinstance(q, dict) and "question" in q and "options" in q and len(q.get("options", [])) == 4 and "correct" in q:
            valid.append(q)
    if not valid:
        valid = _fallback_quiz(req.topic)[:n]

    doc = {
        "topic":         req.topic,
        "questions":     valid,
        "generated_at":  datetime.utcnow().isoformat(),
        "num_questions": len(valid),
    }
    try:
        if await mongo_svc.is_available():
            await mongo_svc.db.quiz_questions.replace_one({"topic": req.topic}, doc, upsert=True)
    except Exception:
        pass

    return JSONResponse(doc)


def _fallback_quiz(topic: str) -> list:
    fb = {
        "photosynthesis": [
            {"question": "What gas do plants absorb from the air during photosynthesis?", "options": ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"], "correct": 1, "explanation": "Plants take in CO2 through tiny pores called stomata."},
            {"question": "Which pigment in leaves captures sunlight energy?", "options": ["Melanin", "Carotene", "Chlorophyll", "Haemoglobin"], "correct": 2, "explanation": "Chlorophyll is the green pigment that absorbs sunlight."},
            {"question": "What is the main food (sugar) that plants produce during photosynthesis?", "options": ["Starch", "Fructose", "Glucose", "Cellulose"], "correct": 2, "explanation": "Glucose is the primary product, later converted to starch for storage."},
            {"question": "Which gas is released by plants as a byproduct of photosynthesis?", "options": ["Carbon dioxide", "Nitrogen", "Hydrogen", "Oxygen"], "correct": 3, "explanation": "Oxygen is released as a byproduct when water molecules are split."},
            {"question": "Plants absorb water for photosynthesis through their:", "options": ["Leaves", "Stems", "Roots", "Flowers"], "correct": 2, "explanation": "Roots absorb water from soil and send it up to the leaves."},
        ],
        "water_cycle": [
            {"question": "Which process converts liquid water into water vapour?", "options": ["Condensation", "Precipitation", "Evaporation", "Transpiration"], "correct": 2, "explanation": "Evaporation uses heat energy from the sun to turn water into gas."},
            {"question": "What forms when water vapour cools high in the atmosphere?", "options": ["Rain", "Clouds", "Fog", "Dew"], "correct": 1, "explanation": "Water vapour condenses into tiny droplets that cluster into clouds."},
            {"question": "What is the main energy source that drives the water cycle?", "options": ["Wind", "Gravity", "The Sun", "Ocean currents"], "correct": 2, "explanation": "Solar energy heats water, causing it to evaporate."},
            {"question": "When plants release water vapour through their leaves, this is called:", "options": ["Evaporation", "Condensation", "Transpiration", "Precipitation"], "correct": 2, "explanation": "Transpiration is water loss through leaf pores (stomata)."},
            {"question": "What is it called when water falls from clouds as rain or snow?", "options": ["Evaporation", "Runoff", "Condensation", "Precipitation"], "correct": 3, "explanation": "Precipitation includes rain, snow, sleet, and hail."},
        ],
        "food_chain": [
            {"question": "Which organisms make their own food using sunlight?", "options": ["Herbivores", "Carnivores", "Producers", "Decomposers"], "correct": 2, "explanation": "Producers (plants) make food through photosynthesis."},
            {"question": "What happens to energy as it moves up the food chain?", "options": ["It increases", "It stays the same", "It decreases", "It doubles"], "correct": 2, "explanation": "About 90% of energy is lost as heat at each trophic level."},
            {"question": "Which organisms break down dead plants and animals?", "options": ["Producers", "Primary consumers", "Secondary consumers", "Decomposers"], "correct": 3, "explanation": "Decomposers like fungi and bacteria recycle nutrients back to the soil."},
            {"question": "A primary consumer feeds on:", "options": ["Other animals", "Plants only", "Decomposers only", "Both plants and animals"], "correct": 1, "explanation": "Primary consumers are herbivores that eat plants (producers)."},
            {"question": "Energy in a food chain originally comes from:", "options": ["Soil nutrients", "Decomposers", "The Sun", "Water"], "correct": 2, "explanation": "All food chain energy originates from the sun, captured by producers."},
        ],
    }
    return fb.get(topic, fb["photosynthesis"])


# ── Fetch notes & quiz ────────────────────────────────────────────────────────

@router.get("/api/content/notes/{topic}")
async def get_notes(topic: str):
    from app import mongo_svc
    try:
        if await mongo_svc.is_available():
            doc = await mongo_svc.db.notes.find_one({"topic": topic}, {"_id": 0})
            if doc:
                return JSONResponse(doc)
    except Exception:
        pass
    return JSONResponse({"notes": None, "topic": topic})


@router.get("/api/content/quiz/{topic}")
async def get_quiz(topic: str):
    from app import mongo_svc
    try:
        if await mongo_svc.is_available():
            doc = await mongo_svc.db.quiz_questions.find_one({"topic": topic}, {"_id": 0})
            if doc:
                return JSONResponse(doc)
    except Exception:
        pass
    return JSONResponse({"questions": [], "topic": topic})


# ── Submit quiz answers ───────────────────────────────────────────────────────

@router.post("/api/quiz/submit")
async def submit_quiz(req: QuizSubmitReq):
    from app import mongo_svc

    try:
        quiz_doc = await mongo_svc.db.quiz_questions.find_one({"topic": req.topic}, {"_id": 0})
    except Exception as e:
        raise HTTPException(500, str(e))

    if not quiz_doc:
        raise HTTPException(404, f"No quiz found for topic '{req.topic}'. Ask your teacher to generate one.")

    questions      = quiz_doc.get("questions", [])
    correct_list   = [q["correct"] for q in questions]
    num_correct    = sum(1 for a, c in zip(req.answers, correct_list) if a == c)
    total          = len(questions)
    points_earned  = num_correct * 10 + (25 if num_correct == total and total > 0 else 0)

    result = {
        "student_id":      req.student_id,
        "student_name":    req.student_name,
        "topic":           req.topic,
        "answers":         req.answers,
        "correct_answers": correct_list,
        "num_correct":     num_correct,
        "total":           total,
        "score_pct":       round(num_correct / total * 100) if total else 0,
        "points_earned":   points_earned,
        "submitted_at":    datetime.utcnow().isoformat(),
        "questions":       questions,  # for front-end to show explanations
    }

    try:
        if await mongo_svc.is_available():
            r = result.copy()
            await mongo_svc.db.quiz_results.insert_one(r)
            await mongo_svc.db.student_points.update_one(
                {"student_id": req.student_id},
                {
                    "$inc": {"points": points_earned, "quiz_correct": num_correct, "quizzes_taken": 1},
                    "$set": {"student_name": req.student_name, "updated": datetime.utcnow().isoformat()},
                },
                upsert=True,
            )
    except Exception as e:
        logger.warning("quiz submit DB error: %s", e)

    result.pop("_id", None)
    return JSONResponse(result)


# ── Award points for answer submission (called from app.py /analyse) ──────────

async def award_submission_points(student_id: str, student_name: str):
    from app import mongo_svc
    try:
        if await mongo_svc.is_available():
            await mongo_svc.db.student_points.update_one(
                {"student_id": student_id},
                {
                    "$inc": {"points": 5, "submissions": 1},
                    "$set": {"student_name": student_name, "updated": datetime.utcnow().isoformat()},
                },
                upsert=True,
            )
    except Exception:
        pass


# ── Leaderboard ───────────────────────────────────────────────────────────────

@router.get("/api/leaderboard")
async def leaderboard(limit: int = 30):
    from app import mongo_svc
    rows = []
    try:
        if await mongo_svc.is_available():
            cursor = mongo_svc.db.student_points.find({}, {"_id": 0}).sort("points", -1).limit(limit)
            rows   = await cursor.to_list(length=limit)
    except Exception:
        pass
    return JSONResponse({"leaderboard": rows})


@router.get("/api/student/{student_id}/points")
async def student_points(student_id: str):
    from app import mongo_svc
    try:
        if await mongo_svc.is_available():
            doc = await mongo_svc.db.student_points.find_one({"student_id": student_id}, {"_id": 0})
            if doc:
                return JSONResponse(doc)
    except Exception:
        pass
    return JSONResponse({"student_id": student_id, "points": 0, "submissions": 0, "quiz_correct": 0, "quizzes_taken": 0})


# ── Rewards config ────────────────────────────────────────────────────────────

REWARDS = [
    {"points":   25, "label": "First Step",    "reward": "Rs.5 Paytm Cash",         "color": "#10b981"},
    {"points":   75, "label": "Getting There", "reward": "Rs.15 Mobile Recharge",   "color": "#3b82f6"},
    {"points":  150, "label": "Star Learner",  "reward": "Rs.30 Book Voucher",       "color": "#8b5cf6"},
    {"points":  300, "label": "Consistent",    "reward": "Rs.60 Stationery Kit",     "color": "#f59e0b"},
    {"points":  500, "label": "Top Performer", "reward": "Rs.100 Amazon Voucher",    "color": "#ef4444"},
    {"points": 1000, "label": "Champion",      "reward": "Rs.200 + Trophy + Cert",  "color": "#e94560"},
]

@router.get("/api/rewards")
async def get_rewards():
    return JSONResponse({"rewards": REWARDS})
