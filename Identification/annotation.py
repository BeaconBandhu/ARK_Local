"""
Person Annotation & Training System
Capture face samples, save to MongoDB, train face recognition model
"""

import cv2
import numpy as np
import face_recognition
import pymongo
import pickle
import uuid
import logging
from datetime import datetime
from pathlib import Path

# ==================== CONFIGURATION ====================
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME   = "access_control"
MODEL_PATH = "face_model.pkl"

TARGET_SAMPLES = 30
MIN_SAMPLES    = 10
SCALE_FACTOR   = 0.5

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==================== MONGO MANAGER ====================
class MongoManager:
    def __init__(self, uri=MONGO_URI, db_name=DB_NAME):
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.db = None
        self.persons = None

    def connect(self):
        try:
            self.client = pymongo.MongoClient(self.uri, serverSelectionTimeoutMS=3000)
            self.client.server_info()
            self.db = self.client[self.db_name]
            self.persons = self.db["persons"]
            logger.info("Connected to MongoDB")
            return True
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            return False

    def person_exists(self, name: str) -> bool:
        return self.persons.find_one({"name": name}) is not None

    def save_person(self, name: str, encodings: list) -> str:
        """Upsert person — merges new encodings if person already exists"""
        encodings_as_lists = [enc.tolist() for enc in encodings]

        existing = self.persons.find_one({"name": name})
        if existing:
            self.persons.update_one(
                {"name": name},
                {
                    "$push": {"face_encodings": {"$each": encodings_as_lists}},
                    "$inc":  {"images_count": len(encodings_as_lists)},
                    "$set":  {"last_updated": datetime.now()}
                }
            )
            person_id = existing["person_id"]
            logger.info(f"Updated encodings for '{name}' ({len(encodings_as_lists)} new samples added)")
        else:
            person_id = str(uuid.uuid4())
            doc = {
                "person_id":       person_id,
                "name":            name,
                "face_encodings":  encodings_as_lists,
                "first_registered": datetime.now(),
                "last_updated":    datetime.now(),
                "last_seen":       None,
                "detection_count": 0,
                "images_count":    len(encodings_as_lists)
            }
            self.persons.insert_one(doc)
            logger.info(f"Registered new person '{name}' ({len(encodings_as_lists)} samples)")

        return person_id

    def get_all_persons(self) -> list:
        return list(self.persons.find({}, {"name": 1, "person_id": 1, "face_encodings": 1, "images_count": 1}))

    def list_persons(self):
        return list(self.persons.find({}, {"name": 1, "images_count": 1, "first_registered": 1, "_id": 0}))

    def delete_person(self, name: str) -> bool:
        result = self.persons.delete_one({"name": name})
        return result.deleted_count > 0

    def close(self):
        if self.client:
            self.client.close()


# ==================== FACE CAPTURE ====================
class FaceCapture:
    def __init__(self, target_samples=TARGET_SAMPLES, scale_factor=SCALE_FACTOR, camera_index=0):
        self.target_samples  = target_samples
        self.scale_factor    = scale_factor
        self.camera_index    = camera_index

    def capture_samples(self, person_name: str) -> list:
        """
        Opens webcam, auto-detects face, collects face encodings.
        Returns list of numpy 128-d encoding arrays.
        """
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            logger.error("Cannot open camera")
            return []

        samples = []
        window_name = f"Annotating: {person_name}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        logger.info(f"Capturing samples for '{person_name}'. Look at the camera.")
        logger.info("Move your head slightly (left, right, tilt) for better coverage.")

        # Throttle capture: don't take two samples from the same static frame
        last_encoding = None
        skip_frames   = 0

        while len(samples) < self.target_samples:
            ret, frame = cap.read()
            if not ret:
                break

            skip_frames += 1
            display = frame.copy()
            h, w = frame.shape[:2]

            small_frame = cv2.resize(frame, (0, 0), fx=self.scale_factor, fy=self.scale_factor)
            rgb_small   = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(rgb_small, model="hog")

            if len(face_locations) == 0:
                cv2.putText(display, "No face detected — please look at the camera",
                            (10, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            elif len(face_locations) > 1:
                cv2.putText(display, "Multiple faces detected — please be alone in frame",
                            (10, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

            else:
                top, right, bottom, left = face_locations[0]
                # Scale bbox back to display coordinates
                pt1 = (int(left   / self.scale_factor), int(top    / self.scale_factor))
                pt2 = (int(right  / self.scale_factor), int(bottom / self.scale_factor))

                encodings = face_recognition.face_encodings(rgb_small, face_locations)
                if encodings:
                    encoding = encodings[0]

                    # Skip if too similar to last sample (prevents near-duplicate captures)
                    capture_ok = True
                    if last_encoding is not None and skip_frames < 3:
                        dist = face_recognition.face_distance([last_encoding], encoding)[0]
                        if dist < 0.10:
                            capture_ok = False

                    if capture_ok:
                        samples.append(encoding)
                        last_encoding = encoding
                        skip_frames   = 0

                        # Flash green border on successful capture
                        cv2.rectangle(display, (0, 0), (w - 1, h - 1), (0, 255, 0), 6)

                # Draw face box
                color = (0, 255, 0) if len(samples) > 0 else (255, 255, 0)
                cv2.rectangle(display, pt1, pt2, color, 2)

            # Header bar
            cv2.rectangle(display, (0, 0), (w, 55), (0, 0, 0), -1)
            cv2.putText(display, f"Person: {person_name}", (10, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

            # Progress bar
            bar_x, bar_y, bar_w, bar_h = 10, 35, w - 20, 14
            progress = int(bar_w * len(samples) / self.target_samples)
            cv2.rectangle(display, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (60, 60, 60), -1)
            cv2.rectangle(display, (bar_x, bar_y), (bar_x + progress, bar_y + bar_h), (0, 200, 80), -1)
            cv2.putText(display, f"{len(samples)}/{self.target_samples}",
                        (bar_x + bar_w // 2 - 20, bar_y + 11),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)

            cv2.imshow(window_name, display)

            key = cv2.waitKey(30) & 0xFF
            if key == 27:
                logger.info("Capture cancelled by user")
                break

        cap.release()
        cv2.destroyAllWindows()

        logger.info(f"Captured {len(samples)} samples for '{person_name}'")
        return samples


# ==================== MODEL TRAINER ====================
class ModelTrainer:
    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path

    def build_and_save(self, all_persons: list) -> bool:
        """
        Flatten all person encodings into parallel lists, save as pickle.
        all_persons: list of dicts from MongoDB (with 'name', 'person_id', 'face_encodings')
        """
        encodings_list = []
        names_list     = []
        ids_list       = []

        for person in all_persons:
            name      = person["name"]
            person_id = person["person_id"]
            for enc_list in person["face_encodings"]:
                encodings_list.append(np.array(enc_list, dtype=np.float64))
                names_list.append(name)
                ids_list.append(person_id)

        if not encodings_list:
            logger.warning("No encodings found — model not saved")
            return False

        model_data = {
            "encodings":  np.array(encodings_list),   # shape (N, 128)
            "names":      names_list,
            "person_ids": ids_list,
            "trained_at": datetime.now().isoformat(),
            "version":    1
        }

        with open(self.model_path, "wb") as f:
            pickle.dump(model_data, f, protocol=4)

        unique = len(set(names_list))
        logger.info(f"Model saved: {len(encodings_list)} encodings for {unique} person(s) → {self.model_path}")
        return True

    def get_stats(self) -> dict:
        if not Path(self.model_path).exists():
            return {"loaded": False}
        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            unique = len(set(data["names"]))
            return {
                "loaded":         True,
                "total_encodings": len(data["names"]),
                "unique_persons":  unique,
                "trained_at":     data.get("trained_at", "unknown")
            }
        except Exception:
            return {"loaded": False, "error": "corrupt model file"}


# ==================== ANNOTATION APP ====================
class AnnotationApp:
    def __init__(self):
        self.db      = MongoManager()
        self.capture = FaceCapture()
        self.trainer = ModelTrainer()

    def _ask_name(self) -> str:
        while True:
            name = input("\nEnter person's full name: ").strip()
            if not name:
                print("  Name cannot be empty. Please try again.")
                continue
            if len(name) < 2:
                print("  Name too short. Please try again.")
                continue
            return name

    def enroll_person(self):
        """Full enrollment pipeline: capture → name → save → train"""
        print("\n" + "─" * 60)
        print("  ENROLL NEW PERSON")
        print("─" * 60)

        print("\n  A camera window will open. Look directly at the camera.")
        print("  Slowly move your head left, right, tilt up/down for variation.")
        print("  Press ESC to cancel capture at any time.\n")
        input("  Press ENTER to open camera...")

        # Temporarily use a placeholder name for the window title
        temp_name = "New Person"
        samples = self.capture.capture_samples(temp_name)

        if len(samples) < MIN_SAMPLES:
            print(f"\n  Only {len(samples)} samples captured (minimum {MIN_SAMPLES} required).")
            print("  Enrollment cancelled — please try again with better lighting or camera position.")
            return

        name = self._ask_name()

        # Confirm
        print(f"\n  Name: {name}")
        print(f"  Samples: {len(samples)}")
        confirm = input("  Save to database? [Y/n]: ").strip().lower()
        if confirm == 'n':
            print("  Enrollment cancelled.")
            return

        # Save to MongoDB (or local-only if DB unavailable)
        db_ok = self.db.connect()
        if db_ok:
            person_id = self.db.save_person(name, samples)
            all_persons = self.db.get_all_persons()
            self.db.close()
        else:
            print("\n  WARNING: MongoDB unavailable — saving model locally only.")
            # Build a minimal person list for model training
            all_persons = [{
                "name":           name,
                "person_id":      str(uuid.uuid4()),
                "face_encodings": [enc.tolist() for enc in samples],
                "images_count":   len(samples)
            }]

        # Retrain model
        trained = self.trainer.build_and_save(all_persons)

        print("\n" + "─" * 60)
        if trained:
            print(f"  ✓ '{name}' enrolled successfully")
            print(f"  ✓ {len(samples)} face samples saved")
            stats = self.trainer.get_stats()
            print(f"  ✓ Model now covers {stats.get('unique_persons', '?')} person(s)")
        else:
            print("  ✗ Model training failed")
        print("─" * 60)

    def retrain_from_db(self):
        """Rebuild model from all data currently in MongoDB"""
        print("\n  Retraining model from MongoDB data...")
        db_ok = self.db.connect()
        if not db_ok:
            print("  ERROR: Cannot connect to MongoDB")
            return

        all_persons = self.db.get_all_persons()
        self.db.close()

        if not all_persons:
            print("  No persons in database — nothing to train")
            return

        self.trainer.build_and_save(all_persons)

    def list_persons(self):
        """Print all registered persons"""
        db_ok = self.db.connect()
        if not db_ok:
            print("  ERROR: Cannot connect to MongoDB")
            return

        persons = self.db.list_persons()
        self.db.close()

        print("\n  Registered Persons:")
        print("  " + "─" * 50)
        if persons:
            for p in persons:
                reg_date = p.get("first_registered", "N/A")
                if isinstance(reg_date, datetime):
                    reg_date = reg_date.strftime("%Y-%m-%d %H:%M")
                print(f"  • {p['name']:30s}  {p.get('images_count', 0):>3d} samples  (registered: {reg_date})")
        else:
            print("  No persons registered yet")
        print("  " + "─" * 50)

    def delete_person(self):
        """Remove a person from the database and retrain"""
        self.list_persons()
        name = input("\n  Enter name to delete (exactly as shown): ").strip()
        if not name:
            return

        confirm = input(f"  Delete '{name}'? This cannot be undone. [y/N]: ").strip().lower()
        if confirm != 'y':
            print("  Cancelled")
            return

        db_ok = self.db.connect()
        if not db_ok:
            print("  ERROR: Cannot connect to MongoDB")
            return

        deleted = self.db.delete_person(name)
        if deleted:
            print(f"  ✓ '{name}' deleted from database")
            all_persons = self.db.get_all_persons()
            self.db.close()
            self.trainer.build_and_save(all_persons)
        else:
            print(f"  '{name}' not found in database")
            self.db.close()

    def show_model_stats(self):
        stats = self.trainer.get_stats()
        print("\n  Model Statistics:")
        print("  " + "─" * 40)
        if stats.get("loaded"):
            print(f"  Encodings:   {stats['total_encodings']}")
            print(f"  Persons:     {stats['unique_persons']}")
            print(f"  Trained at:  {stats['trained_at']}")
            print(f"  File:        {MODEL_PATH}")
        else:
            print("  No trained model found")
            print(f"  Expected at: {MODEL_PATH}")
        print("  " + "─" * 40)

    def run(self):
        print("\n" + "=" * 60)
        print("  FACE RECOGNITION — ANNOTATION & TRAINING SYSTEM")
        print("=" * 60)

        while True:
            print("\n  OPTIONS:")
            print("  1. Enroll new person")
            print("  2. Retrain model from database")
            print("  3. List registered persons")
            print("  4. Delete a person")
            print("  5. Show model statistics")
            print("  6. Exit")

            choice = input("\n  Choice: ").strip()

            if choice == "1":
                self.enroll_person()
            elif choice == "2":
                self.retrain_from_db()
            elif choice == "3":
                self.list_persons()
            elif choice == "4":
                self.delete_person()
            elif choice == "5":
                self.show_model_stats()
            elif choice == "6":
                print("\n  Exiting annotation system.")
                break
            else:
                print("  Invalid choice")


# ==================== MAIN ====================
if __name__ == "__main__":
    app = AnnotationApp()
    app.run()
