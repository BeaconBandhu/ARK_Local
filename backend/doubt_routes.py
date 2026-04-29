"""Doubt routes — doubt access control, peer assignment, AI visual explanations."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

# In-memory stores, backed by MongoDB when available
_doubt_access: dict = {}          # student_id → bool
_peer_assignments: dict = {}      # student_id → {peer_id, peer_name}
_manual_slow_learners: set = set()  # student_ids manually added by teacher


class DoubtAccessBody(BaseModel):
    allowed: bool


class PeerAssignBody(BaseModel):
    student_id: str
    peer_id: str
    peer_name: str


class ManualSlowLearnerBody(BaseModel):
    student_id: str


class DoubtGenerateBody(BaseModel):
    student_id: str
    topic: str
    fingerprint: str
    doubt_type: str          # "flowchart" | "pictorial"
    language: str = "english"
    what_is_wrong: str = ""


# ── Doubt access per student ─────────────────────────────────────────────────

@router.get("/api/doubt/access/{student_id}")
async def get_doubt_access(student_id: str):
    allowed = _doubt_access.get(student_id, False)
    try:
        from app import mongo_svc
        if await mongo_svc.is_available():
            doc = await mongo_svc.db.doubt_access.find_one({"student_id": student_id})
            if doc is not None:
                allowed = doc.get("allowed", False)
                _doubt_access[student_id] = allowed
    except Exception:
        pass
    return JSONResponse({"student_id": student_id, "allowed": allowed})


@router.post("/api/doubt/access/{student_id}")
async def set_doubt_access(student_id: str, body: DoubtAccessBody):
    _doubt_access[student_id] = body.allowed
    try:
        from app import mongo_svc
        if await mongo_svc.is_available():
            await mongo_svc.db.doubt_access.replace_one(
                {"student_id": student_id},
                {"student_id": student_id, "allowed": body.allowed},
                upsert=True,
            )
    except Exception:
        pass
    return JSONResponse({"student_id": student_id, "allowed": body.allowed})


@router.get("/api/doubt/access-all")
async def get_all_doubt_access():
    """Return {student_id: bool} for all students — used by teacher dashboard."""
    result = dict(_doubt_access)
    try:
        from app import mongo_svc
        if await mongo_svc.is_available():
            cursor = mongo_svc.db.doubt_access.find({}, {"_id": 0})
            docs = await cursor.to_list(length=500)
            for doc in docs:
                sid = doc.get("student_id")
                if sid:
                    result[sid] = doc.get("allowed", False)
    except Exception:
        pass
    return JSONResponse(result)


# ── Peer assignments ─────────────────────────────────────────────────────────

@router.get("/api/doubt/peer-assignments")
async def get_peer_assignments():
    result = dict(_peer_assignments)
    try:
        from app import mongo_svc
        if await mongo_svc.is_available():
            cursor = mongo_svc.db.peer_assignments.find({}, {"_id": 0})
            docs = await cursor.to_list(length=500)
            for doc in docs:
                sid = doc.get("student_id")
                if sid:
                    result[sid] = {
                        "peer_id":   doc.get("peer_id", ""),
                        "peer_name": doc.get("peer_name", ""),
                    }
    except Exception:
        pass
    return JSONResponse({"assignments": result})


@router.post("/api/doubt/peer-assign")
async def assign_peer(body: PeerAssignBody):
    _peer_assignments[body.student_id] = {
        "peer_id": body.peer_id, "peer_name": body.peer_name
    }
    try:
        from app import mongo_svc
        if await mongo_svc.is_available():
            await mongo_svc.db.peer_assignments.replace_one(
                {"student_id": body.student_id},
                {"student_id": body.student_id,
                 "peer_id": body.peer_id, "peer_name": body.peer_name},
                upsert=True,
            )
    except Exception:
        pass
    return JSONResponse({"status": "ok", "student_id": body.student_id,
                         "peer_name": body.peer_name})


# ── Manual slow learners ────────────────────────────────────────────────────

@router.get("/api/doubt/manual-slow-learners")
async def get_manual_slow_learners():
    result = list(_manual_slow_learners)
    try:
        from app import mongo_svc
        if await mongo_svc.is_available():
            cursor = mongo_svc.db.manual_slow_learners.find({}, {"_id": 0, "student_id": 1})
            docs = await cursor.to_list(length=500)
            for doc in docs:
                sid = doc.get("student_id")
                if sid and sid not in result:
                    result.append(sid)
    except Exception:
        pass
    return JSONResponse({"student_ids": result})


@router.post("/api/doubt/manual-slow-learners")
async def add_manual_slow_learner(body: ManualSlowLearnerBody):
    _manual_slow_learners.add(body.student_id)
    try:
        from app import mongo_svc
        if await mongo_svc.is_available():
            await mongo_svc.db.manual_slow_learners.replace_one(
                {"student_id": body.student_id},
                {"student_id": body.student_id},
                upsert=True,
            )
    except Exception:
        pass
    return JSONResponse({"status": "ok", "student_id": body.student_id})


@router.delete("/api/doubt/manual-slow-learners/{student_id}")
async def remove_manual_slow_learner(student_id: str):
    _manual_slow_learners.discard(student_id)
    try:
        from app import mongo_svc
        if await mongo_svc.is_available():
            await mongo_svc.db.manual_slow_learners.delete_one({"student_id": student_id})
    except Exception:
        pass
    return JSONResponse({"status": "ok", "student_id": student_id})


# ── AI explanation generation ────────────────────────────────────────────────

import logging as _logging
import os as _os

_log = _logging.getLogger(__name__)


def _dalle_prompt(fingerprint: str, topic: str, gap: str) -> str:
    t = topic.replace("_", " ")
    base = (
        f"Educational science diagram for Grade 6 students. Topic: {t}. "
        "White background. Bright friendly colours. Textbook illustration style. "
        "No human figures. Clear bold labels in English on every component. "
        "Arrows showing direction of processes. "
    )
    if fingerprint == "INVERT":
        return (
            base +
            f"Show the CORRECT cause → effect sequence for {t} with numbered arrows. "
            f"Highlight the correct flow direction to fix this misconception: {gap}. "
            "Include a clear 'CORRECT ✓' label on the right-direction arrow."
        )
    if fingerprint == "ORPHAN":
        return (
            base +
            f"Show TWO connected panels side by side: "
            f"Panel 1 — the prerequisite concept that comes BEFORE {t}, "
            f"Panel 2 — {t} itself. "
            "Draw a bold arrow from Panel 1 to Panel 2 labelled 'leads to'. "
            f"This helps fix: {gap}."
        )
    return (
        base +
        f"Show all key components and processes involved in {t}. "
        f"Clarify: {gap}."
    )


@router.post("/api/doubt/generate")
async def generate_doubt_explanation(req: DoubtGenerateBody):
    import os
    from app import ollama

    lang_display  = {"english": "English", "hindi": "Hindi", "kannada": "Kannada"}.get(
        req.language, "English"
    )
    topic_display = req.topic.replace("_", " ").title()
    gap_text      = req.what_is_wrong or "conceptual misunderstanding"

    fp_context = {
        "INVERT": (
            f"The student has cause and effect reversed for {topic_display}. "
            "They know the parts but applied the wrong direction or sequence."
        ),
        "ORPHAN": (
            f"The student is missing a prerequisite concept needed for {topic_display}, "
            "causing cascading confusion about everything that follows."
        ),
    }.get(req.fingerprint, f"The student has a conceptual gap in {topic_display}.")

    OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

    # ── Pictorial → DALL-E 3 ────────────────────────────────────────────────
    if req.doubt_type == "pictorial" and OPENAI_KEY:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=OPENAI_KEY)
            dp = _dalle_prompt(req.fingerprint, req.topic, gap_text)
            resp = await client.images.generate(
                model="dall-e-3",
                prompt=dp,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = resp.data[0].url
            return JSONResponse({
                "image_url": image_url,
                "type":      "pictorial",
                "language":  req.language,
            })
        except Exception as e:
            _log.warning("DALL-E failed (%s) — falling back to text", e)

    # ── Flowchart text prompt ────────────────────────────────────────────────
    if req.doubt_type == "flowchart":
        text_prompt = f"""You are a Grade 6 science teacher.
Student problem: {fp_context}
Their specific gap: {gap_text}

Create a STEP-BY-STEP FLOWCHART to fix their understanding of {topic_display}.
Use EXACTLY this format:

▶ START
⬇
Step 1: [one-sentence fact]
⬇
Step 2: [one-sentence fact]
⬇
Step 3: [one-sentence fact]
⬇
Step 4: [one-sentence fact]
⬇
Step 5: [one-sentence fact]
⬇
✅ Key Takeaway: [one sentence that directly fixes the student's wrong idea]

Rules:
- Maximum 6 steps.
- Every step must be exactly 1 short sentence.
- Use Grade 6 vocabulary only.
- WRITE ENTIRELY IN {lang_display} — every single word."""
    else:
        # Pictorial fallback (no OpenAI key or DALL-E failed)
        text_prompt = f"""You are a Grade 6 science teacher.
Student problem: {fp_context}
Their specific gap: {gap_text}

Create a PICTORIAL / VISUAL EXPLANATION for {topic_display} using emojis, symbols, and ASCII art.
Use EXACTLY this format:

🖼 VISUAL SCENE:
[ASCII diagram or emoji-rich picture of the concept — at least 4 lines]

🏷 LABELS:
[Name each element in the diagram — one label per line]

📖 WHAT IS HAPPENING:
[Explain each labelled part in 1-2 simple sentences]

💡 THE KEY POINT:
[One sentence that directly fixes the student's wrong idea]

Use visual symbols: →, ⬆, ⬇, ☀️, 🌿, 💧, 🔄, O₂, CO₂, etc.
WRITE ENTIRELY IN {lang_display} — every single word."""

    # ── OpenAI text (flowchart primary / pictorial fallback) ─────────────────
    if OPENAI_KEY:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=OPENAI_KEY)
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=600,
                messages=[{"role": "user", "content": text_prompt}],
            )
            result = resp.choices[0].message.content
            return JSONResponse({
                "explanation": result,
                "type":        req.doubt_type,
                "language":    req.language,
            })
        except Exception as e:
            _log.warning("OpenAI text failed (%s) — falling back to Ollama", e)

    # ── Ollama fallback ──────────────────────────────────────────────────────
    try:
        if await ollama.is_available():
            result = await ollama.generate(text_prompt)
        else:
            result = _fallback(req.fingerprint, req.topic, req.doubt_type, req.language)
    except Exception:
        result = _fallback(req.fingerprint, req.topic, req.doubt_type, req.language)

    return JSONResponse({
        "explanation": result,
        "type":        req.doubt_type,
        "language":    req.language,
    })


def _fallback(fp: str, topic: str, doubt_type: str, lang: str) -> str:
    t = topic.replace("_", " ")
    data = {
        "english": {
            "INVERT":  f"▶ START\n⬇\nStep 1: In {t}, there is a clear cause and a clear effect.\n⬇\nStep 2: The cause always comes FIRST and leads to the effect.\n⬇\nStep 3: You have the direction reversed — trace each step from cause → effect.\n⬇\n✅ Key Takeaway: The process in {t} goes in ONE direction only. Trace it forward.",
            "ORPHAN":  f"▶ START\n⬇\nStep 1: Before understanding {t}, there is a concept that must come first.\n⬇\nStep 2: That missing concept is the reason you are confused.\n⬇\nStep 3: Go back and review the concept that comes BEFORE {t} in your textbook.\n⬇\n✅ Key Takeaway: Once the prerequisite concept is clear, {t} will make sense.",
        },
        "hindi": {
            "INVERT":  f"▶ शुरू\n⬇\nचरण 1: {t} में एक स्पष्ट कारण और एक स्पष्ट प्रभाव है।\n⬇\nचरण 2: कारण हमेशा पहले आता है और प्रभाव की ओर ले जाता है।\n⬇\nचरण 3: आपने दिशा उलट दी है — हर कदम कारण → प्रभाव की ओर ट्रेस करें।\n⬇\n✅ मुख्य बात: {t} की प्रक्रिया केवल एक दिशा में जाती है।",
            "ORPHAN":  f"▶ शुरू\n⬇\nचरण 1: {t} समझने से पहले एक पूर्व-अवधारणा जरूरी है।\n⬇\nचरण 2: वह गायब अवधारणा ही आपके भ्रम का कारण है।\n⬇\nचरण 3: अपनी पाठ्यपुस्तक में {t} से पहले आने वाली अवधारणा दोबारा पढ़ें।\n⬇\n✅ मुख्य बात: पूर्व-अवधारणा स्पष्ट होने पर {t} समझ आएगा।",
        },
        "kannada": {
            "INVERT":  f"▶ ಪ್ರಾರಂಭ\n⬇\nಹಂತ 1: {t} ನಲ್ಲಿ ಒಂದು ಸ್ಪಷ್ಟ ಕಾರಣ ಮತ್ತು ಪರಿಣಾಮ ಇದೆ.\n⬇\nಹಂತ 2: ಕಾರಣ ಯಾವಾಗಲೂ ಮೊದಲು ಬರುತ್ತದೆ.\n⬇\nಹಂತ 3: ನೀವು ದಿಕ್ಕನ್ನು ತಿರುಗಿಸಿದ್ದೀರಿ — ಕಾರಣ → ಪರಿಣಾಮ ದಿಕ್ಕಿನಲ್ಲಿ ಟ್ರೇಸ್ ಮಾಡಿ.\n⬇\n✅ ಮುಖ್ಯ ಅಂಶ: {t} ಪ್ರಕ್ರಿಯೆ ಒಂದೇ ದಿಕ್ಕಿನಲ್ಲಿ ನಡೆಯುತ್ತದೆ.",
            "ORPHAN":  f"▶ ಪ್ರಾರಂಭ\n⬇\nಹಂತ 1: {t} ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲು ಒಂದು ಪೂರ್ವ-ಪರಿಕಲ್ಪನೆ ಅಗತ್ಯ.\n⬇\nಹಂತ 2: ಆ ಕಾಣೆಯಾದ ಪರಿಕಲ್ಪನೆಯೇ ನಿಮ್ಮ ಗೊಂದಲಕ್ಕೆ ಕಾರಣ.\n⬇\nಹಂತ 3: ಪಠ್ಯಪುಸ್ತಕದಲ್ಲಿ {t} ಮೊದಲು ಬರುವ ಪರಿಕಲ್ಪನೆ ಮರು-ಓದಿ.\n⬇\n✅ ಮುಖ್ಯ ಅಂಶ: ಪೂರ್ವ-ಪರಿಕಲ್ಪನೆ ಸ್ಪಷ್ಟವಾದರೆ {t} ಅರ್ಥವಾಗುತ್ತದೆ.",
        },
    }
    lang_data = data.get(lang, data["english"])
    return lang_data.get(fp, f"Review the concept of {t} carefully with your teacher.")
