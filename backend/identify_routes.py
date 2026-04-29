"""Browser-based face identification endpoint."""

import asyncio
import io
import logging
import os
import pickle
import threading
from pathlib import Path

import numpy as np
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)

FACE_MODEL_PATH = os.getenv("FACE_MODEL_PATH", "../Identification/face_model.pkl")
FACE_DB_URI     = os.getenv("MONGO_URI",     "mongodb://localhost:27017/")
FACE_DB_NAME    = os.getenv("FACE_DB_NAME",  "access_control")
TOLERANCE       = float(os.getenv("FACE_TOLERANCE", "0.62"))

_model_cache = None
_model_lock  = threading.Lock()

# Persistent MongoDB connection for role lookups
_face_db = None


def _get_face_db():
    global _face_db
    if _face_db is not None:
        return _face_db
    try:
        import pymongo
        client = pymongo.MongoClient(FACE_DB_URI, serverSelectionTimeoutMS=2000)
        client.server_info()
        _face_db = client[FACE_DB_NAME]
    except Exception:
        pass
    return _face_db


def _load_model(force: bool = False):
    global _model_cache
    with _model_lock:
        if _model_cache is not None and not force:
            return _model_cache
        path = Path(FACE_MODEL_PATH)
        if not path.exists():
            logger.warning("Face model not found at %s", path.resolve())
            return None
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            _model_cache = {
                "encodings":  np.array(data["encodings"]),
                "names":      [n.strip() for n in data["names"]],
                "person_ids": data.get("person_ids", []),
            }
            logger.info("Face model loaded: %d encodings", len(_model_cache["names"]))
            return _model_cache
        except Exception as e:
            logger.error("Face model load error: %s", e)
            return None


def _person_info(name: str) -> dict:
    db = _get_face_db()
    if db is None:
        return {"role": "student", "ark_id": "", "person_id": ""}
    try:
        doc = db["persons"].find_one({"name": name})
        if doc:
            return {
                "role":      doc.get("role", "student"),
                "ark_id":    doc.get("ark_student_id", ""),
                "person_id": doc.get("person_id", ""),
            }
    except Exception:
        pass
    return {"role": "student", "ark_id": "", "person_id": ""}


def _identify_sync(image_bytes: bytes) -> dict:
    """CPU-bound — called via asyncio.to_thread."""
    try:
        import face_recognition
        from PIL import Image as PILImage

        model = _load_model()
        if model is None:
            return {"access_granted": False,
                    "error": "Face model not found. Run annotation.py first."}

        img       = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)

        locs = face_recognition.face_locations(img_array, model="hog")
        if not locs:
            return {"access_granted": False, "name": "Unknown", "reason": "no_face"}

        encs = face_recognition.face_encodings(img_array, locs, num_jitters=1)
        if not encs:
            return {"access_granted": False, "name": "Unknown", "reason": "no_face"}

        distances = face_recognition.face_distance(model["encodings"], encs[0])
        best_idx  = int(np.argmin(distances))
        best_dist = distances[best_idx]
        confidence = round(1.0 - float(best_dist), 4)

        if best_dist <= TOLERANCE:
            name = model["names"][best_idx]
            info = _person_info(name)
            return {
                "access_granted": True,
                "name":           name,
                "role":           info["role"],
                "ark_id":         info["ark_id"],
                "person_id":      info["person_id"],
                "confidence":     confidence,
            }

        return {"access_granted": False, "name": "Unknown",
                "confidence": confidence, "reason": "no_match"}

    except Exception as e:
        logger.error("Identify error: %s", e)
        return {"access_granted": False, "error": str(e)}


@router.post("/api/identify")
async def identify(image: UploadFile = File(...)):
    image_bytes = await image.read()
    result = await asyncio.to_thread(_identify_sync, image_bytes)

    # If face matched but no ARK student ID stored in access_control DB,
    # try to find the student in the ARK database by name.
    if result.get("access_granted") and not result.get("ark_id"):
        try:
            from app import mongo_svc
            if await mongo_svc.is_available():
                name = result.get("name", "")
                doc = await mongo_svc.db.students.find_one(
                    {"student_name": {"$regex": f"^{name}$", "$options": "i"}},
                    {"student_id": 1},
                )
                if doc and doc.get("student_id"):
                    result["ark_id"] = doc["student_id"]
        except Exception:
            pass

    # Mark attendance asynchronously if granted
    if result.get("access_granted"):
        asyncio.create_task(_mark_attendance_async(result))

    return JSONResponse(result)


async def _mark_attendance_async(result: dict):
    try:
        from app import mongo_svc
        from datetime import date, datetime
        today = date.today().isoformat()
        record = {
            "person_name":    result["name"],
            "person_id":      result.get("person_id", ""),
            "role":           result.get("role", "student"),
            "ark_student_id": result.get("ark_id", ""),
            "confidence":     result.get("confidence", 0.0),
            "date":           today,
            "marked_at":      datetime.utcnow().isoformat(),
        }
        if await mongo_svc.is_available():
            await mongo_svc.db.attendance.update_one(
                {"person_name": result["name"], "date": today},
                {"$set": record},
                upsert=True,
            )
    except Exception:
        pass


@router.get("/api/identify/model-status")
async def model_status():
    model = await asyncio.to_thread(_load_model)
    if model is None:
        return JSONResponse({"loaded": False, "persons": 0, "encodings": 0})
    unique = len(set(model["names"]))
    return JSONResponse({"loaded": True, "persons": unique,
                         "encodings": len(model["names"])})


@router.post("/api/identify/reload-model")
async def reload_model():
    model = await asyncio.to_thread(lambda: _load_model(force=True))
    if model is None:
        return JSONResponse({"status": "error", "message": "Model not found"})
    return JSONResponse({"status": "ok", "encodings": len(model["names"])})
