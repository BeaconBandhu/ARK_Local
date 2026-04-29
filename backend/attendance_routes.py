"""Attendance routes — face-verified presence tracking for ARK."""

from datetime import datetime, date, timezone
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


class MarkAttendanceReq(BaseModel):
    person_name: str
    person_id: str
    role: str           # "teacher" or "student"
    ark_student_id: str = ""
    confidence: float = 0.0


@router.post("/api/attendance/mark")
async def mark_attendance(req: MarkAttendanceReq):
    from app import mongo_svc
    today = date.today().isoformat()
    record = {
        "person_name":    req.person_name,
        "person_id":      req.person_id,
        "role":           req.role,
        "ark_student_id": req.ark_student_id,
        "confidence":     req.confidence,
        "date":           today,
        "marked_at":      datetime.utcnow().isoformat(),
    }
    try:
        if await mongo_svc.is_available():
            await mongo_svc.db.attendance.update_one(
                {"person_name": req.person_name, "date": today},
                {"$set": record},
                upsert=True,
            )
    except Exception:
        pass
    return JSONResponse({"status": "ok", "role": req.role, "date": today})


@router.get("/api/attendance/today")
async def attendance_today():
    from app import mongo_svc
    today = date.today().isoformat()
    students, teachers = [], []
    try:
        if await mongo_svc.is_available():
            cursor = mongo_svc.db.attendance.find({"date": today}, {"_id": 0})
            async for doc in cursor:
                (teachers if doc.get("role") == "teacher" else students).append(doc)
    except Exception:
        pass
    return JSONResponse({
        "date":          today,
        "students":      students,
        "teachers":      teachers,
        "student_count": len(students),
        "teacher_count": len(teachers),
    })


@router.get("/api/attendance/teachers/today")
async def teachers_today():
    from app import mongo_svc
    today = date.today().isoformat()
    teachers = []
    try:
        if await mongo_svc.is_available():
            cursor = mongo_svc.db.attendance.find(
                {"date": today, "role": "teacher"},
                {"_id": 0, "person_name": 1, "marked_at": 1},
            )
            teachers = await cursor.to_list(length=20)
    except Exception:
        pass
    return JSONResponse({"teachers": teachers, "date": today})
