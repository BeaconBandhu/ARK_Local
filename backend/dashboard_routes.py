"""Dashboard routes — serves teacher GUI and all data endpoints it needs."""

import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

router = APIRouter()

TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.html"

# ── Serve the dashboard HTML ─────────────────────────────────────────────────

@router.get("/dashboard", include_in_schema=False)
async def dashboard():
    if not TEMPLATE_PATH.exists():
        raise HTTPException(404, "dashboard.html not found")
    return FileResponse(str(TEMPLATE_PATH), media_type="text/html")


# ── Student detail from MongoDB (with Redis fallback) ────────────────────────

@router.get("/api/student/{student_id}")
async def get_student_detail(student_id: str):
    """Return full student record from MongoDB, fall back to Redis session."""
    from app import mongo_svc, redis_svc

    # Try MongoDB first (persisted records)
    try:
        if await mongo_svc.is_available():
            doc = await mongo_svc.get_student(student_id)
            if doc:
                return JSONResponse(doc)
    except Exception:
        pass

    # Fall back to current session in Redis/memory
    students = await redis_svc.get_all_students()
    for s in students:
        if s.get("student_id") == student_id:
            return JSONResponse(s)

    raise HTTPException(404, f"Student {student_id} not found")


@router.get("/api/student/{student_id}/history")
async def get_student_history(student_id: str):
    """Return all historical submissions for a student from MongoDB."""
    from app import mongo_svc

    try:
        if await mongo_svc.is_available():
            cursor = mongo_svc.db.students_history.find(
                {"student_id": student_id}, {"_id": 0}
            ).sort("timestamp", 1).limit(50)
            history = await cursor.to_list(length=50)
            return JSONResponse({"history": history})
    except Exception:
        pass

    return JSONResponse({"history": []})


@router.get("/api/fingerprint-legend")
async def fingerprint_legend():
    return JSONResponse({
        "GHOST":    {"color": "#f59e0b", "description": "Strong but completely wrong belief — student is confident but incorrect"},
        "INVERT":   {"color": "#ef4444", "description": "Cause and effect reversed — has the parts, wrong direction"},
        "HOLLOW":   {"color": "#3b82f6", "description": "Right keywords, zero mechanism — sounds correct, means nothing"},
        "FRAGMENT": {"color": "#10b981", "description": "Partial understanding — one link missing from the chain"},
        "ORPHAN":   {"color": "#8b5cf6", "description": "Prerequisite gap — earlier concept broken, cascading confusion"},
    })


@router.get("/api/offline-cache")
async def offline_cache():
    """Send the offline cache JSON to the mobile app for priming AsyncStorage."""
    cache_path = Path(__file__).parent / "data" / "cache.json"
    if not cache_path.exists():
        return JSONResponse({})
    with open(cache_path, encoding="utf-8") as f:
        return JSONResponse(json.load(f))
