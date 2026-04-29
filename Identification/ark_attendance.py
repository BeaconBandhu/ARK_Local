"""
ARK Attendance & Access System
Recognizes faces → teacher opens dashboard, student opens their profile.
Marks attendance in ARK backend. Admin GUI accessible only to Aranya Bandhu.
"""

import cv2
import numpy as np
import face_recognition
import pymongo
import pickle
import threading
import logging
import webbrowser
import requests
from datetime import datetime, timedelta
from pathlib import Path
from collections import namedtuple

# ==================== CONFIG ====================
MONGO_URI    = "mongodb://localhost:27017/"
DB_NAME      = "access_control"
MODEL_PATH   = "face_model.pkl"
ARK_BASE_URL = "http://localhost:8000"
ADMIN_NAME   = "Aranya Bandhu"

TOLERANCE     = 0.62
SCALE_FACTOR  = 0.75
COOLDOWN_SECS = 30.0   # seconds before re-routing same person

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RecognitionResult = namedtuple(
    "RecognitionResult",
    ["name", "person_id", "role", "ark_id", "confidence", "bbox"]
)


# ==================== PERSON DB ====================
class PersonDB:
    def __init__(self):
        self.client = None
        self.db     = None

    def connect(self) -> bool:
        try:
            self.client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            self.client.server_info()
            self.db = self.client[DB_NAME]
            return True
        except Exception as e:
            logger.warning("MongoDB unavailable: %s", e)
            return False

    def get_person_info(self, name: str) -> dict:
        if not self.db:
            return {}
        try:
            doc = self.db["persons"].find_one({"name": name})
            if doc:
                return {
                    "role":      doc.get("role", "student"),
                    "ark_id":    doc.get("ark_student_id", ""),
                    "person_id": doc.get("person_id", ""),
                }
        except Exception:
            pass
        return {}

    def log_detection(self, result: RecognitionResult):
        if not self.db:
            return
        def _write():
            try:
                self.db["detections"].insert_one({
                    "name":           result.name,
                    "person_id":      result.person_id,
                    "role":           result.role,
                    "timestamp":      datetime.now(),
                    "confidence":     float(result.confidence),
                    "access_granted": True,
                })
                self.db["persons"].update_one(
                    {"person_id": result.person_id},
                    {"$set": {"last_seen": datetime.now()},
                     "$inc": {"detection_count": 1}},
                )
            except Exception as e:
                logger.debug("DB write error: %s", e)
        threading.Thread(target=_write, daemon=True).start()

    def close(self):
        if self.client:
            self.client.close()


# ==================== MODEL ====================
class ModelLoader:
    def __init__(self):
        self.encodings  = None
        self.names      = None
        self.person_ids = None
        self.is_loaded  = False

    def load(self) -> bool:
        if not Path(MODEL_PATH).exists():
            logger.warning("Model not found — run annotation.py first")
            self.is_loaded = False
            return False
        try:
            with open(MODEL_PATH, "rb") as f:
                data = pickle.load(f)
            self.encodings  = np.array(data["encodings"])
            self.names      = [n.strip() for n in data["names"]]
            self.person_ids = data["person_ids"]
            self.is_loaded  = True
            logger.info("Model loaded: %d encodings, persons: %s",
                        len(self.names), sorted(set(self.names)))
            return True
        except Exception as e:
            logger.error("Model load failed: %s", e)
            self.is_loaded = False
            return False


# ==================== ATTENDANCE ROUTER ====================
class AttendanceRouter:
    def __init__(self):
        self._last_routed = {}  # name -> datetime

    def should_route(self, name: str) -> bool:
        last = self._last_routed.get(name)
        return last is None or (datetime.now() - last).total_seconds() > COOLDOWN_SECS

    def route(self, result: RecognitionResult):
        self._last_routed[result.name] = datetime.now()
        threading.Thread(target=self._mark_attendance, args=(result,), daemon=True).start()

        if result.role == "teacher":
            url = f"{ARK_BASE_URL}/dashboard"
        elif result.ark_id:
            url = (f"{ARK_BASE_URL}/student"
                   f"?auto_id={result.ark_id}"
                   f"&auto_name={result.name.replace(' ', '+')}")
        else:
            url = f"{ARK_BASE_URL}/student"

        webbrowser.open(url)
        logger.info("Routed %s (%s) → %s", result.name, result.role, url)

    def _mark_attendance(self, result: RecognitionResult):
        try:
            requests.post(
                f"{ARK_BASE_URL}/api/attendance/mark",
                json={
                    "person_name":    result.name,
                    "person_id":      result.person_id,
                    "role":           result.role,
                    "ark_student_id": result.ark_id,
                    "confidence":     result.confidence,
                },
                timeout=3,
            )
        except Exception as e:
            logger.debug("Attendance POST failed: %s", e)


# ==================== MAIN APP ====================
class ArkAttendanceApp:
    COLOR_TEACHER = (0, 200, 80)    # green
    COLOR_STUDENT = (255, 160, 0)   # amber
    COLOR_DENIED  = (0, 0, 220)     # red
    WHITE         = (255, 255, 255)

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.model  = ModelLoader()
        self.db     = PersonDB()
        self.router = AttendanceRouter()

        self._lock         = threading.Lock()
        self._latest_frame = None
        self._results      = []
        self._stop         = threading.Event()

        self._welcome_text  = ""
        self._welcome_until = datetime.min
        self._pulse = 0

    # ── background recognition ───────────────────────────────────────────────
    def _recognition_thread(self):
        while not self._stop.is_set():
            with self._lock:
                frame = self._latest_frame
            if frame is None or not self.model.is_loaded:
                self._stop.wait(timeout=0.05)
                continue

            small = cv2.resize(frame, (0, 0), fx=SCALE_FACTOR, fy=SCALE_FACTOR)
            rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            locs  = face_recognition.face_locations(rgb, model="hog")

            if not locs:
                with self._lock:
                    self._results = []
                continue

            encs = face_recognition.face_encodings(rgb, locs, num_jitters=1)
            results = []
            for loc, enc in zip(locs, encs):
                r = self._identify(enc, loc)
                results.append(r)

                if r.name != "Unknown" and self.router.should_route(r.name):
                    self.db.log_detection(r)
                    self.router.route(r)
                    role_label = "Teacher" if r.role == "teacher" else "Student"
                    with self._lock:
                        self._welcome_text  = f"Welcome, {r.name}! ({role_label})"
                        self._welcome_until = datetime.now() + timedelta(seconds=4)

            with self._lock:
                self._results = results

    def _identify(self, encoding, loc) -> RecognitionResult:
        def scale(v, factor=SCALE_FACTOR):
            return int(v / factor)

        top, right, bottom, left = loc
        bbox = (scale(top), scale(right), scale(bottom), scale(left))

        if not self.model.is_loaded or self.model.encodings is None:
            return RecognitionResult("Unknown", "", "unknown", "", 0.0, bbox)

        distances = face_recognition.face_distance(self.model.encodings, encoding)
        best_idx  = int(np.argmin(distances))
        best_dist = distances[best_idx]
        conf      = round(1.0 - float(best_dist), 4)

        if best_dist <= TOLERANCE:
            name = self.model.names[best_idx]
            pid  = self.model.person_ids[best_idx]
            info = self.db.get_person_info(name)
            return RecognitionResult(
                name=name, person_id=pid,
                role=info.get("role", "student"),
                ark_id=info.get("ark_id", ""),
                confidence=conf, bbox=bbox,
            )
        return RecognitionResult("Unknown", "", "unknown", "", conf, bbox)

    # ── drawing ──────────────────────────────────────────────────────────────
    def _draw(self, frame, results):
        h, w = frame.shape[:2]
        self._pulse += 1

        for r in results:
            top, right, bottom, left = r.bbox
            top    = max(0, min(top,    h))
            bottom = max(0, min(bottom, h))
            left   = max(0, min(left,   w))
            right  = max(0, min(right,  w))

            if r.name != "Unknown":
                color = self.COLOR_TEACHER if r.role == "teacher" else self.COLOR_STUDENT
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                by = min(bottom + 2, h - 52)
                cv2.rectangle(frame, (left, by), (right, by + 50), color, -1)
                cv2.putText(frame, "ACCESS GRANTED",
                            (left + 4, by + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.50, self.WHITE, 2)
                cv2.putText(frame, f"{r.name}  |  {r.role.upper()}  |  {r.confidence:.0%}",
                            (left + 4, by + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.36, self.WHITE, 1)
            else:
                thick = 2 + (self._pulse // 3) % 5
                cv2.rectangle(frame, (left, top), (right, bottom), self.COLOR_DENIED, thick)
                by = min(bottom + 2, h - 52)
                cv2.rectangle(frame, (left, by), (right, by + 50), self.COLOR_DENIED, -1)
                cv2.putText(frame, "ACCESS DENIED",
                            (left + 4, by + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.50, self.WHITE, 2)
                cv2.putText(frame, "UNKNOWN PERSON",
                            (left + 4, by + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.WHITE, 1)

        # Status bar
        cv2.rectangle(frame, (0, 0), (w, 46), (20, 20, 20), -1)
        model_txt = "MODEL LOADED" if self.model.is_loaded else "NO MODEL — run annotation.py"
        cv2.putText(frame, f"ARK ATTENDANCE  |  {model_txt}  |  r=reload  q=quit",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

        # Welcome banner
        if datetime.now() < self._welcome_until:
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, h // 2 - 55), (w, h // 2 + 55), (0, 140, 60), -1)
            cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)
            (tw, _), _ = cv2.getTextSize(
                self._welcome_text, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2)
            cv2.putText(frame, self._welcome_text,
                        ((w - tw) // 2, h // 2 + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, self.WHITE, 2)

    # ── run ──────────────────────────────────────────────────────────────────
    def run(self):
        self.model.load()
        self.db.connect()

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            logger.error("Cannot open camera %s", self.camera_index)
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS,          30)

        t = threading.Thread(target=self._recognition_thread, daemon=True)
        t.start()

        cv2.namedWindow("ARK — Attendance & Access", cv2.WINDOW_NORMAL)
        logger.info("ARK Attendance running — press 'q' to quit, 'r' to reload model")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                with self._lock:
                    self._latest_frame = frame.copy()
                    results = list(self._results)

                display = frame.copy()
                self._draw(display, results)
                cv2.imshow("ARK — Attendance & Access", display)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                elif key == ord("r"):
                    self.model.load()
        finally:
            self._stop.set()
            cap.release()
            cv2.destroyAllWindows()
            self.db.close()
            logger.info("ARK Attendance stopped.")


# ==================== MAIN ====================
if __name__ == "__main__":
    import sys
    cam = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print("=" * 60)
    print("  ARK ATTENDANCE & ACCESS SYSTEM")
    print("  Teacher → opens dashboard")
    print("  Student → opens personal profile")
    print("  Admin GUI → run admin_panel.py (face-verified)")
    print("=" * 60)
    ArkAttendanceApp(camera_index=cam).run()
