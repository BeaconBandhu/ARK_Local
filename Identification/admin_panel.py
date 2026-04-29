"""
Access Control Admin Panel
Face-verified admin interface — only Aranya Bandhu can log in.
Manages per-person access rules stored in MongoDB.
identification.py reads those rules in real-time; this file never touches it.

Usage:
    python admin_panel.py
"""

import cv2
import numpy as np
import face_recognition
import pymongo
import pickle
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime
from pathlib import Path
import logging

# ==================== CONFIGURATION ====================
MONGO_URI        = "mongodb://localhost:27017/"
DB_NAME          = "access_control"
MODEL_PATH       = "face_model.pkl"

ADMIN_NAME       = "Aranya Bandhu"    # only this person passes verification
VERIFY_TOLERANCE = 0.62               # match identification.py threshold
CONFIRM_FRAMES   = 3                  # total matching frames needed (not consecutive)
SCALE_FACTOR     = 0.75              # 640x480 * 0.75 = 480x360 — faces ~75px, reliable HOG detection
VERIFY_TIMEOUT_S = 60                 # max seconds to wait for faqce before giving up

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==================== FACE VERIFIER ====================
class FaceVerifier:
    """
    Opens the camera, detects and identifies a face.
    Returns True only if ADMIN_NAME is confirmed for CONFIRM_FRAMES consecutive frames.
    Camera window stays open until verified, cancelled (ESC/q), or timed out.
    """

    def __init__(self, model_path=MODEL_PATH,
                 admin_name=ADMIN_NAME,
                 tolerance=VERIFY_TOLERANCE,
                 confirm_frames=CONFIRM_FRAMES,
                 scale=SCALE_FACTOR,
                 timeout_s=VERIFY_TIMEOUT_S):
        self.model_path     = model_path
        self.admin_name     = admin_name
        self.tolerance      = tolerance
        self.confirm_frames = confirm_frames
        self.scale          = scale
        self.timeout_s      = timeout_s
        self._encodings     = None
        self._names         = None

    def _load_model(self) -> bool:
        if not Path(self.model_path).exists():
            print(f"\n  [ERROR] Model not found at '{self.model_path}'")
            print(f"  Run annotation.py and enroll '{self.admin_name}' first.\n")
            return False
        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            self._encodings = np.array(data["encodings"])
            self._names     = data["names"]
            # Normalize whitespace to handle any accidental leading/trailing spaces
            self._names = [n.strip() for n in self._names]
            if self.admin_name.strip() not in self._names:
                print(f"\n  [ERROR] '{self.admin_name}' is not enrolled in the model.")
                print(f"  Enrolled persons: {sorted(set(self._names))}")
                print(f"  Run annotation.py and enroll '{self.admin_name}' first.\n")
                return False
            self.admin_name = self.admin_name.strip()
            return True
        except Exception as e:
            print(f"\n  [ERROR] Failed to load model: {e}\n")
            return False

    def _identify(self, encoding) -> tuple:
        """Returns (name, confidence). name='Unknown' if no match."""
        if self._encodings is None or len(self._encodings) == 0:
            return "Unknown", 0.0
        distances  = face_recognition.face_distance(self._encodings, encoding)
        best_idx   = int(np.argmin(distances))
        best_dist  = distances[best_idx]
        confidence = round(1.0 - float(best_dist), 3)
        print(f"  [VERIFY] Best match: '{self._names[best_idx]}'  dist={best_dist:.3f}  threshold={self.tolerance}")
        if best_dist <= self.tolerance:
            return self._names[best_idx], confidence
        return "Unknown", confidence

    def verify(self) -> bool:
        """
        Blocking call. Shows camera window.
        Returns True when admin face is confirmed, False otherwise.
        """
        if not self._load_model():
            return False

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("  [ERROR] Cannot open camera")
            return False

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS,          30)

        window = "Admin Verification — Face Required"
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)

        # confirm_count counts TOTAL successful matches (not consecutive).
        # It never resets on no-face frames — only resets if a DIFFERENT person is
        # confidently detected (impostor attempt).
        confirm_count   = 0
        frame_num       = 0
        start_time      = datetime.now()
        verified        = False

        # Cache last drawn bounding boxes so display doesn't go blank between
        # recognition frames (recognition only runs every 3rd frame).
        last_display_boxes = []

        print(f"\n  Camera open. Please look at the camera.")
        print(f"  Only '{self.admin_name}' can access the admin panel.")
        print(f"  Press ESC or 'q' to cancel.\n")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_num += 1
            elapsed    = (datetime.now() - start_time).total_seconds()
            remaining  = max(0, self.timeout_s - elapsed)
            display    = frame.copy()
            h, w       = frame.shape[:2]

            # Timeout
            if elapsed > self.timeout_s:
                self._draw_banner(display, "VERIFICATION TIMED OUT", (0, 100, 200), h, w)
                cv2.imshow(window, display)
                cv2.waitKey(1500)
                break

            # ── Run recognition every 3rd frame only ──────────────────────
            if frame_num % 3 == 0:
                small     = cv2.resize(frame, (0, 0), fx=self.scale, fy=self.scale)
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

                try:
                    face_locs = face_recognition.face_locations(rgb_small, model="hog")
                    face_encs = face_recognition.face_encodings(rgb_small, face_locs)
                except Exception:
                    face_locs, face_encs = [], []

                last_display_boxes = []

                for loc, enc in zip(face_locs, face_encs):
                    n, c = self._identify(enc)

                    top    = int(loc[0] / self.scale)
                    right  = int(loc[1] / self.scale)
                    bottom = int(loc[2] / self.scale)
                    left   = int(loc[3] / self.scale)

                    is_admin  = (n == self.admin_name)
                    box_color = (0, 220, 0) if is_admin else (0, 0, 220)
                    last_display_boxes.append((left, top, right, bottom, box_color, n, c))

                    if is_admin:
                        confirm_count += 1
                        print(f"  [VERIFY] Match #{confirm_count}: '{n}' ({c:.0%})")
                    elif n != "Unknown":
                        # A DIFFERENT known person is in frame — reset
                        print(f"  [VERIFY] Wrong person detected: '{n}' — resetting counter")
                        confirm_count = 0

                # no face found this frame: do nothing (don't penalise)

            # ── Draw cached boxes on every frame ──────────────────────────
            for (lx, ty, rx, by, col, n, c) in last_display_boxes:
                cv2.rectangle(display, (lx, ty), (rx, by), col, 2)
                cv2.putText(display, f"{n} ({c:.0%})",
                            (lx, ty - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)

            # ── Progress bar ──────────────────────────────────────────────
            progress = min(confirm_count / self.confirm_frames, 1.0)
            bar_w    = w - 20
            filled   = int(bar_w * progress)
            cv2.rectangle(display, (10, h - 30), (10 + bar_w, h - 10), (60, 60, 60), -1)
            cv2.rectangle(display, (10, h - 30), (10 + filled, h - 10), (0, 220, 0), -1)
            cv2.putText(display,
                        f"Verifying {self.admin_name}... {confirm_count}/{self.confirm_frames} matches",
                        (10, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

            # ── Top status bar ─────────────────────────────────────────────
            cv2.rectangle(display, (0, 0), (w, 45), (20, 20, 20), -1)
            cv2.putText(display, f"ADMIN VERIFICATION  |  Required: {self.admin_name}",
                        (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)
            cv2.putText(display, f"Timeout: {remaining:.0f}s  |  ESC/q = cancel",
                        (10, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (120, 120, 120), 1)

            # ── Verified! ─────────────────────────────────────────────────
            if confirm_count >= self.confirm_frames:
                self._draw_banner(display, f"VERIFIED: {self.admin_name}", (0, 200, 0), h, w)
                cv2.imshow(window, display)
                cv2.waitKey(1200)
                verified = True
                break

            cv2.imshow(window, display)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord('q')):
                print("  Verification cancelled.")
                break

        cap.release()
        cv2.destroyAllWindows()
        return verified

    @staticmethod
    def _draw_banner(frame, text: str, color: tuple, h: int, w: int):
        """Draw a large centred banner on the frame."""
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h // 2 - 40), (w, h // 2 + 40), color, -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
        (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
        cv2.putText(frame, text, ((w - tw) // 2, h // 2 + 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)


# ==================== ACCESS RULES DB ====================
class AccessRulesDB:
    """
    Manages the 'access_rules' collection in MongoDB.
    Schema: { name, person_id, access_allowed: bool, modified_by, modified_at }
    """

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
            # Ensure unique index on name
            self.db["access_rules"].create_index("name", unique=True)
            return True
        except Exception as e:
            print(f"  [ERROR] MongoDB: {e}")
            return False

    def get_all_persons(self) -> list:
        """Returns all enrolled persons from the 'persons' collection."""
        try:
            return list(self.db["persons"].find(
                {}, {"name": 1, "person_id": 1, "detection_count": 1, "last_seen": 1, "_id": 0}
            ).sort("name", 1))
        except Exception:
            return []

    def get_all_rules(self) -> dict:
        """Returns {name: access_allowed_bool}."""
        try:
            return {doc["name"]: doc.get("access_allowed", True)
                    for doc in self.db["access_rules"].find()}
        except Exception:
            return {}

    def set_access(self, name: str, person_id: str, allowed: bool, admin: str = ADMIN_NAME):
        """Upsert an access rule for a person."""
        try:
            self.db["access_rules"].update_one(
                {"name": name},
                {"$set": {
                    "name":          name,
                    "person_id":     person_id,
                    "access_allowed": allowed,
                    "modified_by":   admin,
                    "modified_at":   datetime.now()
                }},
                upsert=True
            )
        except Exception as e:
            logger.error(f"set_access error: {e}")

    def set_role(self, name: str, role: str, ark_student_id: str = ""):
        """Set teacher/student role and optional ARK student ID for a person."""
        try:
            self.db["persons"].update_one(
                {"name": name},
                {"$set": {"role": role, "ark_student_id": ark_student_id}},
            )
        except Exception as e:
            logger.error("set_role error: %s", e)

    def get_recent_detections(self, limit: int = 30) -> list:
        """Returns the most recent detection log entries."""
        try:
            return list(self.db["detections"].find(
                {}, {"name": 1, "timestamp": 1, "confidence": 1, "access_granted": 1, "_id": 0}
            ).sort("timestamp", -1).limit(limit))
        except Exception:
            return []

    def check_recent_grant(self, name: str, within_seconds: int = 60) -> bool:
        """
        Returns True if identification.py granted access to `name`
        within the last `within_seconds` seconds.
        This lets admin_panel piggyback on identification.py's camera
        instead of opening a competing camera stream.
        """
        try:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(seconds=within_seconds)
            result = self.db["detections"].find_one({
                "name":           name,
                "access_granted": True,
                "timestamp":      {"$gte": cutoff}
            })
            return result is not None
        except Exception:
            return False

    def get_stats(self) -> dict:
        try:
            total      = self.db["detections"].count_documents({})
            granted    = self.db["detections"].count_documents({"access_granted": True})
            denied     = self.db["detections"].count_documents({"access_granted": False})
            persons    = self.db["persons"].count_documents({})
            blocked    = self.db["access_rules"].count_documents({"access_allowed": False})
            return {"total": total, "granted": granted, "denied": denied,
                    "persons": persons, "blocked": blocked}
        except Exception:
            return {}

    def close(self):
        if self.client:
            self.client.close()


# ==================== ADMIN PANEL GUI ====================
class AdminPanelGUI:
    """
    Tkinter admin panel.
    Left panel: person list with Allow / Deny toggles.
    Right panel: live detection log + stats.
    """

    # Colour palette
    BG          = "#1a1a2e"
    PANEL_BG    = "#16213e"
    ACCENT      = "#0f3460"
    GREEN       = "#00c853"
    RED         = "#d50000"
    ORANGE      = "#ff6f00"
    TEXT        = "#e0e0e0"
    SUBTEXT     = "#9e9e9e"
    WHITE       = "#ffffff"
    ROW_EVEN    = "#1e2a45"
    ROW_ODD     = "#162035"

    def __init__(self, db: AccessRulesDB, admin_name: str = ADMIN_NAME):
        self.db         = db
        self.admin_name = admin_name
        self.root       = tk.Tk()
        self._person_rows   = {}   # name -> {frame, status_label, btn}
        self._rules_cache   = {}   # {name: allowed_bool}
        self._auto_refresh  = True

        self._setup_window()
        self._build_ui()
        self._refresh_all()

    # ── window setup ──────────────────────────────────────────────────────
    def _setup_window(self):
        self.root.title("Access Control Admin Panel")
        self.root.configure(bg=self.BG)
        self.root.geometry("1050x680")
        self.root.minsize(900, 580)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # ttk style
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Dark.TFrame",       background=self.BG)
        style.configure("Panel.TFrame",      background=self.PANEL_BG)
        style.configure("Dark.TLabel",       background=self.BG,       foreground=self.TEXT)
        style.configure("Panel.TLabel",      background=self.PANEL_BG, foreground=self.TEXT)
        style.configure("Sub.TLabel",        background=self.PANEL_BG, foreground=self.SUBTEXT,
                        font=("Helvetica", 9))
        style.configure("Title.TLabel",      background=self.BG,       foreground=self.WHITE,
                        font=("Helvetica", 14, "bold"))
        style.configure("SectionTitle.TLabel", background=self.PANEL_BG, foreground=self.WHITE,
                        font=("Helvetica", 11, "bold"))

    # ── UI build ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=self.ACCENT, height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(header, text="  ACCESS CONTROL ADMIN PANEL",
                 bg=self.ACCENT, fg=self.WHITE,
                 font=("Helvetica", 15, "bold")).pack(side="left", pady=10)

        # Admin badge
        tk.Label(header, text=f"  Admin: {self.admin_name}  ",
                 bg="#0d2137", fg=self.GREEN,
                 font=("Helvetica", 10, "bold")).pack(side="left", padx=20, pady=15)

        self._clock_lbl = tk.Label(header, text="", bg=self.ACCENT, fg=self.SUBTEXT,
                                   font=("Helvetica", 9))
        self._clock_lbl.pack(side="right", padx=15)

        tk.Button(header, text="  Logout  ", bg="#c62828", fg=self.WHITE,
                  font=("Helvetica", 10, "bold"), relief="flat", cursor="hand2",
                  activebackground="#b71c1c", activeforeground=self.WHITE,
                  command=self._logout).pack(side="right", padx=10, pady=12)

        # ── Body (two panels) ────────────────────────────────────────────
        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        # Left: person management
        left = tk.Frame(body, bg=self.PANEL_BG, bd=0)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._build_left_panel(left)

        # Right: log + stats
        right = tk.Frame(body, bg=self.PANEL_BG, bd=0, width=340)
        right.pack(side="right", fill="both", padx=(6, 0))
        right.pack_propagate(False)
        self._build_right_panel(right)

    def _build_left_panel(self, parent):
        # Title row
        title_row = tk.Frame(parent, bg=self.PANEL_BG)
        title_row.pack(fill="x", padx=12, pady=(10, 6))

        tk.Label(title_row, text="PERSON ACCESS MANAGEMENT",
                 bg=self.PANEL_BG, fg=self.WHITE,
                 font=("Helvetica", 11, "bold")).pack(side="left")

        tk.Button(title_row, text="Refresh", bg=self.ACCENT, fg=self.WHITE,
                  font=("Helvetica", 9), relief="flat", cursor="hand2",
                  padx=8, pady=3,
                  command=self._refresh_all).pack(side="right")

        # Column headers
        hdr = tk.Frame(parent, bg="#0d2137")
        hdr.pack(fill="x", padx=12, pady=(0, 4))
        for txt, w in [("Person Name", 22), ("Detections", 8), ("Last Seen", 16), ("Role", 10), ("ARK ID", 8), ("Access", 8), ("Actions", 16)]:
            tk.Label(hdr, text=txt, bg="#0d2137", fg=self.SUBTEXT,
                     font=("Helvetica", 9, "bold"),
                     width=w, anchor="w").pack(side="left", padx=4, pady=5)

        # Scrollable person list
        container = tk.Frame(parent, bg=self.PANEL_BG)
        container.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        canvas    = tk.Canvas(container, bg=self.PANEL_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self._persons_frame = tk.Frame(canvas, bg=self.PANEL_BG)

        self._persons_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._persons_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left",  fill="both", expand=True)

        # Bind mouse wheel
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._persons_canvas = canvas

        # Bottom stats bar
        self._stats_bar = tk.Label(parent, text="", bg=self.ACCENT,
                                   fg=self.SUBTEXT, font=("Helvetica", 9),
                                   anchor="w", padx=10)
        self._stats_bar.pack(fill="x", padx=12, pady=(0, 8))

    def _build_right_panel(self, parent):
        tk.Label(parent, text="RECENT DETECTIONS",
                 bg=self.PANEL_BG, fg=self.WHITE,
                 font=("Helvetica", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        # Log listbox
        log_frame = tk.Frame(parent, bg=self.PANEL_BG)
        log_frame.pack(fill="both", expand=True, padx=12)

        self._log_text = tk.Text(log_frame, bg="#0d1b2a", fg=self.TEXT,
                                 font=("Courier", 9), relief="flat",
                                 state="disabled", wrap="none",
                                 selectbackground=self.ACCENT)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical",
                                   command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self._log_text.pack(side="left", fill="both", expand=True)

        # Tag colours
        self._log_text.tag_configure("granted", foreground=self.GREEN)
        self._log_text.tag_configure("denied",  foreground=self.RED)
        self._log_text.tag_configure("ts",      foreground=self.SUBTEXT)

        # Refresh log button
        tk.Button(parent, text="Refresh Log", bg=self.ACCENT, fg=self.WHITE,
                  font=("Helvetica", 9), relief="flat", cursor="hand2",
                  padx=8, pady=3,
                  command=self._refresh_log).pack(anchor="e", padx=12, pady=6)

        # Stats box
        tk.Label(parent, text="STATISTICS",
                 bg=self.PANEL_BG, fg=self.WHITE,
                 font=("Helvetica", 11, "bold")).pack(anchor="w", padx=12, pady=(6, 4))

        self._stats_frame = tk.Frame(parent, bg=self.PANEL_BG)
        self._stats_frame.pack(fill="x", padx=12, pady=(0, 10))
        self._stats_labels = {}
        for key, label in [("persons",  "Enrolled"),
                            ("blocked",  "Blocked"),
                            ("granted",  "Granted today"),
                            ("denied",   "Denied today"),
                            ("total",    "Total detections")]:
            row = tk.Frame(self._stats_frame, bg=self.PANEL_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label + ":", bg=self.PANEL_BG,
                     fg=self.SUBTEXT, font=("Helvetica", 9),
                     width=18, anchor="w").pack(side="left")
            lbl = tk.Label(row, text="—", bg=self.PANEL_BG,
                           fg=self.WHITE, font=("Helvetica", 9, "bold"), anchor="w")
            lbl.pack(side="left")
            self._stats_labels[key] = lbl

    # ── data refresh ──────────────────────────────────────────────────────
    def _refresh_all(self):
        self._refresh_persons()
        self._refresh_log()
        self._refresh_stats()

    def _refresh_persons(self):
        """Re-populate the persons list from MongoDB."""
        self._rules_cache = self.db.get_all_rules()
        persons           = self.db.get_all_persons()

        # Clear existing rows
        for w in self._persons_frame.winfo_children():
            w.destroy()
        self._person_rows = {}

        if not persons:
            tk.Label(self._persons_frame,
                     text="No persons enrolled. Run annotation.py to add people.",
                     bg=self.PANEL_BG, fg=self.SUBTEXT,
                     font=("Helvetica", 10)).pack(pady=30)
            return

        # Fetch all persons with role data too
        all_persons_full = list(self.db.db["persons"].find(
            {}, {"name": 1, "person_id": 1, "detection_count": 1,
                 "last_seen": 1, "role": 1, "ark_student_id": 1, "_id": 0}
        ).sort("name", 1)) if self.db.db else persons

        for i, person in enumerate(all_persons_full):
            name      = person.get("name", "?")
            person_id = person.get("person_id", "")
            det_count = person.get("detection_count", 0)
            last_seen = person.get("last_seen")
            last_str  = last_seen.strftime("%d %b %H:%M") if isinstance(last_seen, datetime) else "Never"
            allowed   = self._rules_cache.get(name, True)
            role      = person.get("role", "student")
            ark_id    = person.get("ark_student_id", "")

            row_bg = self.ROW_EVEN if i % 2 == 0 else self.ROW_ODD
            row    = tk.Frame(self._persons_frame, bg=row_bg)
            row.pack(fill="x", pady=1)

            tk.Label(row, text=name, bg=row_bg, fg=self.WHITE,
                     font=("Helvetica", 10), width=22, anchor="w").pack(side="left", padx=4, pady=6)
            tk.Label(row, text=str(det_count), bg=row_bg, fg=self.SUBTEXT,
                     font=("Helvetica", 9), width=8, anchor="w").pack(side="left", padx=4)
            tk.Label(row, text=last_str, bg=row_bg, fg=self.SUBTEXT,
                     font=("Helvetica", 9), width=16, anchor="w").pack(side="left", padx=4)

            # Role badge + toggle
            role_color = self.GREEN if role == "teacher" else self.ORANGE
            role_lbl   = tk.Label(row, text=role.upper(), bg=row_bg, fg=role_color,
                                  font=("Helvetica", 9, "bold"), width=10, anchor="w")
            role_lbl.pack(side="left", padx=4)

            # ARK ID (editable for students)
            ark_var = tk.StringVar(value=ark_id)
            ark_entry = tk.Entry(row, textvariable=ark_var, bg="#0d1b2a", fg=self.WHITE,
                                 font=("Helvetica", 9), width=8, relief="flat",
                                 insertbackground=self.WHITE)
            ark_entry.pack(side="left", padx=4)

            # Access badge
            s_color    = self.GREEN if allowed else self.RED
            s_text     = "OK" if allowed else "DENY"
            status_lbl = tk.Label(row, text=s_text, bg=row_bg, fg=s_color,
                                  font=("Helvetica", 9, "bold"), width=8, anchor="w")
            status_lbl.pack(side="left", padx=4)

            # Actions frame
            acts = tk.Frame(row, bg=row_bg)
            acts.pack(side="left", padx=4)

            # Role toggle button
            next_role  = "student" if role == "teacher" else "teacher"
            role_btn   = tk.Button(acts, text="→ " + next_role.title(),
                                   bg=self.ACCENT, fg=self.WHITE,
                                   font=("Helvetica", 8), relief="flat", padx=6, pady=1,
                                   cursor="hand2", activeforeground=self.WHITE)
            role_btn.configure(
                command=lambda n=name, rl=role_lbl, rb=role_btn, av=ark_var:
                    self._toggle_role(n, rl, rb, av)
            )
            role_btn.pack(side="left", padx=2)

            # Save ARK ID button
            save_btn = tk.Button(acts, text="Save ID",
                                 bg="#2e7d32", fg=self.WHITE,
                                 font=("Helvetica", 8), relief="flat", padx=6, pady=1,
                                 cursor="hand2", activeforeground=self.WHITE)
            save_btn.configure(
                command=lambda n=name, av=ark_var, rl=role_lbl:
                    self._save_ark_id(n, av, rl)
            )
            save_btn.pack(side="left", padx=2)

            # Access toggle button
            acc_btn_text  = "Block" if allowed else "Allow"
            acc_btn_color = self.RED if allowed else self.GREEN
            acc_btn = tk.Button(acts, text=acc_btn_text, bg=acc_btn_color, fg=self.WHITE,
                                font=("Helvetica", 8, "bold"), relief="flat",
                                padx=6, pady=1, cursor="hand2", activeforeground=self.WHITE)
            acc_btn.configure(
                command=lambda n=name, pid=person_id, a=allowed, sl=status_lbl, b=acc_btn:
                    self._toggle_access(n, pid, a, sl, b)
            )
            acc_btn.pack(side="left", padx=2)

            self._person_rows[name] = {"status": status_lbl, "role_lbl": role_lbl,
                                       "allowed": allowed, "role": role}

    def _refresh_log(self):
        detections = self.db.get_recent_detections(30)
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")

        for d in detections:
            ts      = d.get("timestamp")
            ts_str  = ts.strftime("%H:%M:%S") if isinstance(ts, datetime) else "??:??:??"
            name    = d.get("name", "Unknown")
            granted = d.get("access_granted", False)
            conf    = d.get("confidence", 0.0)
            tag     = "granted" if granted else "denied"
            status  = "GRANTED" if granted else "DENIED "

            self._log_text.insert("end", f"{ts_str}  ", "ts")
            self._log_text.insert("end", f"{status}  ", tag)
            self._log_text.insert("end", f"{name:<20}  {conf:.0%}\n")

        self._log_text.configure(state="disabled")
        self._log_text.see("1.0")

    def _refresh_stats(self):
        stats = self.db.get_stats()
        for key, lbl in self._stats_labels.items():
            lbl.configure(text=str(stats.get(key, "—")))

        blocked = stats.get("blocked", 0)
        persons = stats.get("persons", 0)
        self._stats_bar.configure(
            text=f"  {persons} enrolled  |  {blocked} blocked  |  "
                 f"{persons - blocked} active  |  Last updated: {datetime.now().strftime('%H:%M:%S')}"
        )

    # ── access toggle ──────────────────────────────────────────────────────
    def _toggle_access(self, name: str, person_id: str, currently_allowed: bool,
                       status_lbl: tk.Label, btn: tk.Button):
        new_allowed = not currently_allowed

        # Confirm deny action
        if not new_allowed:
            ok = messagebox.askyesno(
                "Confirm Deny",
                f"Deny access to '{name}'?\n\nThey will be shown ACCESS DENIED "
                f"in the identification system immediately.",
                parent=self.root
            )
            if not ok:
                return

        # Save to MongoDB
        self.db.set_access(name, person_id, new_allowed, self.admin_name)
        self._rules_cache[name] = new_allowed

        # Update UI immediately (no re-render needed)
        if new_allowed:
            status_lbl.configure(text="ALLOWED", fg=self.GREEN)
            btn.configure(text="DENY",  bg=self.RED,   fg=self.WHITE,
                          command=lambda n=name, pid=person_id, sl=status_lbl, b=btn:
                              self._toggle_access(n, pid, True, sl, b))
        else:
            status_lbl.configure(text="DENIED",  fg=self.RED)
            btn.configure(text="ALLOW", bg=self.GREEN, fg=self.WHITE,
                          command=lambda n=name, pid=person_id, sl=status_lbl, b=btn:
                              self._toggle_access(n, pid, False, sl, b))

        self._refresh_stats()
        logger.info(f"Admin '{self.admin_name}' set '{name}' → {'ALLOWED' if new_allowed else 'DENIED'}")

    def _toggle_role(self, name: str, role_lbl: tk.Label, role_btn: tk.Button, ark_var):
        current = "teacher" if role_lbl.cget("text") == "TEACHER" else "student"
        new_role = "student" if current == "teacher" else "teacher"
        ark_id   = ark_var.get().strip()
        self.db.set_role(name, new_role, ark_id)
        role_color = self.GREEN if new_role == "teacher" else self.ORANGE
        role_lbl.configure(text=new_role.upper(), fg=role_color)
        role_btn.configure(text=f"→ {'student' if new_role == 'teacher' else 'teacher'}")
        logger.info("Role updated: %s → %s", name, new_role)

    def _save_ark_id(self, name: str, ark_var, role_lbl: tk.Label):
        ark_id   = ark_var.get().strip()
        current  = "teacher" if role_lbl.cget("text") == "TEACHER" else "student"
        self.db.set_role(name, current, ark_id)
        messagebox.showinfo("Saved", f"ARK ID '{ark_id}' saved for {name}.", parent=self.root)

    # ── clock + auto-refresh ──────────────────────────────────────────────
    def _tick(self):
        now = datetime.now().strftime("%d %b %Y  %H:%M:%S")
        self._clock_lbl.configure(text=now + "  ")
        self.root.after(1000, self._tick)

    def _auto_refresh_loop(self):
        if self._auto_refresh:
            self._refresh_log()
            self._refresh_stats()
        self.root.after(5000, self._auto_refresh_loop)   # refresh every 5 s

    # ── lifecycle ─────────────────────────────────────────────────────────
    def _logout(self):
        if messagebox.askyesno("Logout", "Log out of the admin panel?", parent=self.root):
            self._auto_refresh = False
            self.db.close()
            self.root.destroy()

    def _on_close(self):
        self._auto_refresh = False
        self.db.close()
        self.root.destroy()

    def run(self):
        self._tick()
        self._auto_refresh_loop()
        self.root.mainloop()


# ==================== MAIN ====================
def main():
    print("\n" + "=" * 65)
    print("  ACCESS CONTROL ADMIN PANEL")
    print("=" * 65)
    print(f"  Admin: {ADMIN_NAME}")
    print(f"  Model: {MODEL_PATH}  |  DB: {MONGO_URI}{DB_NAME}")
    print("=" * 65)

    # ── Step 1: Connect MongoDB (needed for both verification paths) ──────
    print("\n  Connecting to MongoDB...")
    db = AccessRulesDB()
    if not db.connect():
        print("  [ERROR] Cannot connect to MongoDB. Exiting.")
        return
    print("  Connected.\n")

    verified      = False
    verify_method = ""

    # ── Step 2a: Check if identification.py already verified admin recently ─
    print(f"  Checking if '{ADMIN_NAME}' was recently verified by identification.py...")
    if db.check_recent_grant(ADMIN_NAME, within_seconds=60):
        print(f"  ✓ Recent ACCESS GRANTED found for '{ADMIN_NAME}' (within last 60 s).")
        print(f"  ✓ Skipping camera — identity confirmed via identification system.")
        verified      = True
        verify_method = "identification.py"

    # ── Step 2b: Fallback — open camera directly ───────────────────────────
    if not verified:
        print(f"\n  No recent verification found.")
        print(f"  Tip: Run identification.py first and look at the camera until")
        print(f"  it shows 'ACCESS GRANTED — {ADMIN_NAME}', then run admin_panel.py.")
        print(f"\n  Alternatively, starting camera verification now...")
        print(f"  (If camera appears black/frozen, identification.py is using it.")
        print(f"   In that case, close this, get verified in identification.py, then rerun.)\n")

        verifier = FaceVerifier()
        verified  = verifier.verify()
        if verified:
            verify_method = "camera"

    # ── Step 3: Open admin panel or deny ──────────────────────────────────
    if not verified:
        print(f"\n  Access denied. Admin panel not opened.")
        print(f"  Only '{ADMIN_NAME}' can access this panel.")
        print(f"\n  HOW TO GET IN:")
        print(f"  1. Run identification.py")
        print(f"  2. Stand in front of the camera until it shows ACCESS GRANTED")
        print(f"  3. Run admin_panel.py within 60 seconds")
        db.close()
        return

    print(f"\n  ✓ Verified as '{ADMIN_NAME}' via {verify_method}.")
    print(f"  Opening admin panel...\n")
    gui = AdminPanelGUI(db=db, admin_name=ADMIN_NAME)
    gui.run()


if __name__ == "__main__":
    main()
