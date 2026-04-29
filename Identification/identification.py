"""
Live Person Identification & Access Control System
Loads trained face model, identifies persons in real-time,
shows ACCESS GRANTED (green) or ACCESS DENIED (red).
Run annotation.py first to enroll persons and train the model.
"""

import cv2
import numpy as np
import face_recognition
import pymongo
import pickle
import threading
import logging
from collections import namedtuple
from datetime import datetime, timedelta
from pathlib import Path

# ==================== CONFIGURATION ====================
MONGO_URI              = "mongodb://localhost:27017/"
DB_NAME                = "access_control"
MODEL_PATH             = "face_model.pkl"

TOLERANCE              = 0.62    # face_recognition default is 0.6 — 0.62 handles lighting variation
SCALE_FACTOR           = 0.75   # 640x480 * 0.75 = 480x360 — faces ~75px wide, reliable for HOG
PROCESS_EVERY_N_FRAMES = 2      # kept for compatibility, not used in threaded mode
LOG_COOLDOWN_SECONDS   = 3.0    # min seconds between DB writes per face

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

RecognitionResult = namedtuple(
    "RecognitionResult",
    ["name", "person_id", "confidence", "access_granted", "bbox"]
    # bbox = (top, right, bottom, left) in full-frame coordinates
)


# ==================== MONGO MANAGER ====================
class MongoManager:
    def __init__(self, uri=MONGO_URI, db_name=DB_NAME):
        self.uri     = uri
        self.db_name = db_name
        self.client  = None
        self.db      = None

    def connect(self) -> bool:
        try:
            self.client = pymongo.MongoClient(self.uri, serverSelectionTimeoutMS=3000)
            self.client.server_info()
            self.db = self.client[self.db_name]
            logger.info("MongoDB connected")
            return True
        except Exception as e:
            logger.warning(f"MongoDB unavailable: {e} — detections will not be logged")
            return False

    def log_detection(self, result: RecognitionResult):
        """Write detection record in a background thread (non-blocking)."""
        if self.db is None:
            return

        def _write():
            try:
                self.db["detections"].insert_one({
                    "name":           result.name,
                    "person_id":      result.person_id,
                    "timestamp":      datetime.now(),
                    "confidence":     float(result.confidence),
                    "access_granted": result.access_granted
                })
                if result.access_granted and result.person_id:
                    self.db["persons"].update_one(
                        {"person_id": result.person_id},
                        {
                            "$set": {"last_seen": datetime.now()},
                            "$inc": {"detection_count": 1}
                        }
                    )
            except Exception as e:
                logger.debug(f"DB write error: {e}")

        threading.Thread(target=_write, daemon=True).start()

    def get_access_rules(self) -> dict:
        """
        Returns {name: allowed_bool} from the access_rules collection.
        Called by AccessControlApp to override per-person access.
        """
        if self.db is None:
            return {}
        try:
            rules = {}
            for doc in self.db["access_rules"].find({}, {"name": 1, "access_allowed": 1}):
                rules[doc["name"]] = doc.get("access_allowed", True)
            return rules
        except Exception:
            return {}

    def close(self):
        if self.client:
            self.client.close()


# ==================== MODEL LOADER ====================
class ModelLoader:
    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path
        self._encodings  = None
        self._names      = None
        self._person_ids = None
        self._is_loaded  = False

    def load(self) -> bool:
        path = Path(self.model_path)
        if not path.exists():
            logger.warning(f"Model not found at '{self.model_path}'. Run annotation.py to enroll persons.")
            self._is_loaded = False
            return False
        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            self._encodings  = np.array(data["encodings"])
            self._names      = [n.strip() for n in data["names"]]   # strip whitespace
            self._person_ids = data["person_ids"]
            self._is_loaded  = True
            unique = sorted(set(self._names))
            logger.info(f"Model loaded: {len(self._names)} encodings for {len(unique)} person(s): {unique}")
            logger.info(f"Tolerance: {TOLERANCE}  (if dist <= {TOLERANCE} → GRANTED)")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self._is_loaded = False
            return False

    def reload(self) -> bool:
        logger.info("Reloading model...")
        return self.load()

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def encodings(self):
        return self._encodings

    @property
    def names(self):
        return self._names

    @property
    def person_ids(self):
        return self._person_ids


# ==================== FACE IDENTIFIER (threaded) ====================
class FaceIdentifier:
    """
    Runs face recognition in a background daemon thread.
    The main display loop reads `results` at any time without blocking —
    it always gets the most recently computed detections while the camera
    renders at full speed (30-60 FPS).
    """

    def __init__(self, tolerance=TOLERANCE, scale_factor=SCALE_FACTOR):
        self.tolerance    = tolerance
        self.scale_factor = scale_factor

        # Shared state between main thread and recognition thread
        self._lock            = threading.Lock()
        self._latest_frame    = None   # main thread writes, bg thread reads
        self._results         = []     # bg thread writes, main thread reads
        self._new_frame_event = threading.Event()
        self._stop_event      = threading.Event()

        # Start background recognition thread
        self._thread = threading.Thread(target=self._recognition_loop, daemon=True)
        self._thread.start()

    # ── called by main thread ──────────────────────────────────────────────
    def submit_frame(self, frame: np.ndarray):
        """Give the latest frame to the recognition thread (non-blocking)."""
        with self._lock:
            self._latest_frame = frame
        self._new_frame_event.set()

    @property
    def results(self) -> list:
        """Read the latest recognition results (non-blocking)."""
        with self._lock:
            return list(self._results)

    def stop(self):
        self._stop_event.set()
        self._new_frame_event.set()  # unblock waiting thread

    # ── background thread ──────────────────────────────────────────────────
    def _recognition_loop(self):
        while not self._stop_event.is_set():
            self._new_frame_event.wait(timeout=1.0)
            self._new_frame_event.clear()

            with self._lock:
                frame     = self._latest_frame
                model_ref = getattr(self, '_model', None)

            if frame is None or model_ref is None:
                continue

            try:
                computed = self._process(frame, model_ref)
                with self._lock:
                    self._results = computed
            except Exception as e:
                # Log and continue — never let the thread die silently
                logger.error(f"Recognition error: {e}", exc_info=True)

    def set_model(self, model: 'ModelLoader'):
        """Update model reference (thread-safe, called from main thread)."""
        with self._lock:
            self._model = model

    # ── recognition logic (runs in bg thread) ─────────────────────────────
    def _process(self, frame: np.ndarray, model: 'ModelLoader') -> list:
        small     = cv2.resize(frame, (0, 0), fx=self.scale_factor, fy=self.scale_factor)
        rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_small, model="hog")
        if not face_locations:
            return []

        face_encodings = face_recognition.face_encodings(
            rgb_small, face_locations, num_jitters=1
        )
        results = []
        for location, encoding in zip(face_locations, face_encodings):
            top, right, bottom, left = location
            bbox = (
                int(top    / self.scale_factor),
                int(right  / self.scale_factor),
                int(bottom / self.scale_factor),
                int(left   / self.scale_factor)
            )
            results.append(self._identify(encoding, bbox, model))
        return results

    def _identify(self, encoding, bbox, model: 'ModelLoader') -> RecognitionResult:
        if not model.is_loaded or model.encodings is None or len(model.encodings) == 0:
            return RecognitionResult(
                name="Unknown", person_id=None,
                confidence=0.0, access_granted=False, bbox=bbox
            )

        distances  = face_recognition.face_distance(model.encodings, encoding)
        best_idx   = int(np.argmin(distances))
        best_dist  = distances[best_idx]
        confidence = round(1.0 - float(best_dist), 4)

        # Debug: print best match so you can tune tolerance
        logger.debug(f"Best match: '{model.names[best_idx]}' dist={best_dist:.3f} (threshold={self.tolerance})")

        if best_dist <= self.tolerance:
            logger.info(f"GRANTED → {model.names[best_idx]} ({confidence:.0%})")
            return RecognitionResult(
                name=model.names[best_idx],
                person_id=model.person_ids[best_idx],
                confidence=confidence,
                access_granted=True,
                bbox=bbox
            )
        logger.info(f"DENIED  → best guess '{model.names[best_idx]}' dist={best_dist:.3f} > {self.tolerance}")
        return RecognitionResult(
            name="Unknown", person_id=None,
            confidence=confidence, access_granted=False, bbox=bbox
        )


# ==================== UI RENDERER ====================
class UIRenderer:
    GRANTED_COLOR = (0, 220, 0)     # green  (BGR)
    DENIED_COLOR  = (0, 0, 230)     # red    (BGR)
    WHITE         = (255, 255, 255)
    BLACK         = (0, 0, 0)

    def draw_result(self, frame: np.ndarray, result: RecognitionResult, pulse: int):
        top, right, bottom, left = result.bbox
        h, w = frame.shape[:2]

        # Clamp to frame bounds
        top    = max(0, top)
        left   = max(0, left)
        bottom = min(h, bottom)
        right  = min(w, right)

        if result.access_granted:
            self._draw_granted(frame, top, right, bottom, left, result)
        else:
            self._draw_denied(frame, top, right, bottom, left, pulse)

    def _draw_granted(self, frame, top, right, bottom, left, result):
        color = self.GRANTED_COLOR

        # Face rectangle
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

        # Status badge below the face box
        badge_top    = bottom + 2
        badge_bottom = bottom + 58
        badge_bottom = min(badge_bottom, frame.shape[0] - 1)
        cv2.rectangle(frame, (left, badge_top), (right, badge_bottom), color, -1)

        # "ACCESS GRANTED" label
        cv2.putText(frame, "ACCESS GRANTED",
                    (left + 5, badge_top + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, self.WHITE, 2)

        # Name + confidence
        display_name = result.name
        conf_str     = f"{result.confidence:.0%}"
        cv2.putText(frame, f"{display_name}  ({conf_str})",
                    (left + 5, badge_top + 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.WHITE, 1)

        # Corner accents on face box
        accent_len = max(10, (right - left) // 6)
        thick      = 3
        for (sx, sy), (dx, dy) in [
            ((left,  top),    (accent_len, 0)),
            ((left,  top),    (0, accent_len)),
            ((right, top),    (-accent_len, 0)),
            ((right, top),    (0, accent_len)),
            ((left,  bottom), (accent_len, 0)),
            ((left,  bottom), (0, -accent_len)),
            ((right, bottom), (-accent_len, 0)),
            ((right, bottom), (0, -accent_len)),
        ]:
            cv2.line(frame, (sx, sy), (sx + dx, sy + dy), color, thick)

    def _draw_denied(self, frame, top, right, bottom, left, pulse: int):
        color = self.DENIED_COLOR

        # Pulsing border thickness (cycles 2 → 7)
        thickness = 2 + (pulse // 3) % 6
        cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)

        # Semi-transparent red overlay on face region (flash effect)
        overlay = frame.copy()
        alpha   = 0.15 + 0.12 * abs(np.sin(pulse * 0.18))
        cv2.rectangle(overlay, (left, top), (right, bottom), color, -1)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        # Status badge
        badge_top    = bottom + 2
        badge_bottom = bottom + 58
        badge_bottom = min(badge_bottom, frame.shape[0] - 1)
        cv2.rectangle(frame, (left, badge_top), (right, badge_bottom), color, -1)

        # "ACCESS DENIED" — larger, bold
        cv2.putText(frame, "ACCESS DENIED",
                    (left + 5, badge_top + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.WHITE, 2)

        cv2.putText(frame, "UNKNOWN PERSON",
                    (left + 5, badge_top + 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.WHITE, 1)

    def draw_status_bar(self, frame: np.ndarray, model_loaded: bool,
                        fps: float, num_faces: int, tolerance: float):
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w, 50), (20, 20, 20), -1)

        status_color = (0, 200, 0) if model_loaded else (0, 100, 220)
        status_text  = "MODEL: LOADED" if model_loaded else "MODEL: NOT FOUND — run annotation.py"
        cv2.putText(frame, status_text, (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, status_color, 1)

        info = f"FPS: {fps:.1f}  |  Faces: {num_faces}  |  Tolerance: {tolerance}  |  'r'=reload  'q'=quit"
        cv2.putText(frame, info, (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)

    def draw_no_model_warning(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        lines = [
            "No face model found.",
            "Run  annotation.py  to enroll persons.",
            "Press 'r' to reload after training."
        ]
        y_start = h // 2 - 40
        for i, line in enumerate(lines):
            size   = 0.7 if i == 0 else 0.55
            color  = (0, 100, 220) if i == 0 else (180, 180, 180)
            (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, size, 2)
            x = (w - tw) // 2
            cv2.putText(frame, line, (x, y_start + i * 38),
                        cv2.FONT_HERSHEY_SIMPLEX, size, color, 2)


# ==================== ACCESS CONTROL APP ====================
class AccessControlApp:
    def __init__(self, camera_index=0):
        self.camera_index  = camera_index
        self.model         = ModelLoader()
        self.identifier    = FaceIdentifier()
        self.renderer      = UIRenderer()
        self.db            = MongoManager()

        self._frame_count  = 0
        self._pulse        = 0
        self._fps          = 0.0
        self._fps_timer    = datetime.now()
        self._fps_frames   = 0

        # Rate-limit DB logging per (name, access_granted) pair
        self._last_logged  = {}   # key -> datetime

        # Access rules cache (refreshed every 3 s from MongoDB)
        self._access_rules      = {}   # {name: allowed_bool}
        self._rules_refresh_at  = datetime.min

    def _should_log(self, result: RecognitionResult) -> bool:
        key      = (result.name, result.access_granted)
        last     = self._last_logged.get(key)
        now      = datetime.now()
        cooldown = timedelta(seconds=LOG_COOLDOWN_SECONDS)
        if last is None or (now - last) > cooldown:
            self._last_logged[key] = now
            return True
        return False

    def _update_fps(self):
        self._fps_frames += 1
        elapsed = (datetime.now() - self._fps_timer).total_seconds()
        if elapsed >= 1.0:
            self._fps        = self._fps_frames / elapsed
            self._fps_frames = 0
            self._fps_timer  = datetime.now()

    def _apply_access_rules(self, results: list) -> list:
        """Override access_granted based on admin-set rules (cached, non-blocking)."""
        now = datetime.now()
        if (now - self._rules_refresh_at).total_seconds() > 3:
            self._access_rules     = self.db.get_access_rules()
            self._rules_refresh_at = now

        if not self._access_rules:
            return results

        overridden = []
        for r in results:
            if r.name in self._access_rules and not self._access_rules[r.name]:
                r = r._replace(access_granted=False)
            overridden.append(r)
        return overridden

    def _handle_key(self, key: int) -> str:
        if key == ord('q') or key == 27:
            return "quit"
        if key == ord('r'):
            return "reload"
        return ""

    def run(self):
        # Load model + connect DB
        self.model.load()
        self.db.connect()

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            logger.error("Cannot open camera")
            self.db.close()
            return

        # 640x480 @ 30 FPS — lower resolution means far less work per frame
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS,          30)

        # Give the recognition thread the initial model reference
        self.identifier.set_model(self.model)

        window_name = "Face Identification — Access Control"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        logger.info("\n" + "=" * 70)
        logger.info("  FACE IDENTIFICATION & ACCESS CONTROL SYSTEM")
        logger.info("=" * 70)
        logger.info("  'r'  Reload face model (after enrolling new persons)")
        logger.info("  'q' / ESC  Quit")
        logger.info("=" * 70 + "\n")

        model_poll_timer = datetime.now()

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.error("Camera read failed")
                    break

                self._frame_count += 1
                self._pulse       += 1
                self._update_fps()

                # Feed frame to background recognition thread (non-blocking)
                self.identifier.submit_frame(frame)

                display = frame.copy()

                # Auto-reload model if it appears on disk
                if not self.model.is_loaded:
                    if (datetime.now() - model_poll_timer).total_seconds() > 5:
                        model_poll_timer = datetime.now()
                        if Path(MODEL_PATH).exists():
                            self.model.load()
                            self.identifier.set_model(self.model)

                # Read latest results from bg thread (never blocks)
                if self.model.is_loaded:
                    results = self._apply_access_rules(self.identifier.results)

                    for result in results:
                        self.renderer.draw_result(display, result, self._pulse)
                        if self._should_log(result):
                            self.db.log_detection(result)
                else:
                    self.renderer.draw_no_model_warning(display)
                    results = []

                self.renderer.draw_status_bar(
                    display,
                    self.model.is_loaded,
                    self._fps,
                    len(results),
                    self.identifier.tolerance
                )

                cv2.imshow(window_name, display)

                key    = cv2.waitKey(1) & 0xFF
                action = self._handle_key(key)
                if action == "quit":
                    break
                elif action == "reload":
                    self.model.reload()
                    self.identifier.set_model(self.model)

        finally:
            self.identifier.stop()
            cap.release()
            cv2.destroyAllWindows()
            self.db.close()
            logger.info(f"\nSystem closed. Frames processed: {self._frame_count}")


# ==================== MAIN ====================
if __name__ == "__main__":
    import sys

    print("\n" + "=" * 70)
    print("  FACE IDENTIFICATION & ACCESS CONTROL SYSTEM")
    print("=" * 70)
    print("  Requires a trained model from annotation.py")
    print("  MongoDB: access_control database")
    print("=" * 70 + "\n")

    camera = 0
    if len(sys.argv) > 1:
        try:
            camera = int(sys.argv[1])
        except ValueError:
            camera = sys.argv[1]  # video file path

    app = AccessControlApp(camera_index=camera)
    app.run()
