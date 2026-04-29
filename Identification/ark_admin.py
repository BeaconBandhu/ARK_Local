"""
ARK Admin — Face Verification → Access Control Admin Panel
Run this single file:
  1. Camera opens for live face verification
  2. When Aranya Bandhu is confirmed → admin panel opens automatically
  3. Admin panel manages roles, ARK IDs, and access rules

GUI access restricted to: Aranya Bandhu
"""

import cv2
import numpy as np
import face_recognition
import pymongo
import pickle
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime
from pathlib import Path

# ==================== CONFIG ====================
MONGO_URI        = "mongodb://localhost:27017/"
DB_NAME          = "access_control"
MODEL_PATH       = "face_model.pkl"
ADMIN_NAME       = "Aranya Bandhu"

VERIFY_TOLERANCE = 0.62
CONFIRM_FRAMES   = 3        # number of matching frames needed
SCALE_FACTOR     = 0.75
VERIFY_TIMEOUT_S = 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ==================== FACE VERIFIER ====================
class FaceVerifier:
    """
    Opens camera, runs live recognition.
    Returns True only when ADMIN_NAME is confirmed CONFIRM_FRAMES times.
    """

    def __init__(self):
        self._encodings = None
        self._names     = None

    def _load_model(self) -> bool:
        if not Path(MODEL_PATH).exists():
            print(f"\n  [ERROR] Model not found at '{MODEL_PATH}'")
            print(f"  Run annotation.py and enroll '{ADMIN_NAME}' first.\n")
            return False
        try:
            with open(MODEL_PATH, "rb") as f:
                data = pickle.load(f)
            self._encodings = np.array(data["encodings"])
            self._names     = [n.strip() for n in data["names"]]
            if ADMIN_NAME not in self._names:
                print(f"\n  [ERROR] '{ADMIN_NAME}' is not enrolled.")
                print(f"  Enrolled: {sorted(set(self._names))}")
                return False
            return True
        except Exception as e:
            print(f"\n  [ERROR] Model load failed: {e}\n")
            return False

    def _identify(self, encoding) -> tuple:
        if self._encodings is None or len(self._encodings) == 0:
            return "Unknown", 0.0
        distances  = face_recognition.face_distance(self._encodings, encoding)
        best_idx   = int(np.argmin(distances))
        best_dist  = distances[best_idx]
        confidence = round(1.0 - float(best_dist), 3)
        if best_dist <= VERIFY_TOLERANCE:
            return self._names[best_idx], confidence
        return "Unknown", confidence

    @staticmethod
    def _banner(frame, text: str, color: tuple, h: int, w: int):
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h // 2 - 45), (w, h // 2 + 45), color, -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
        (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
        cv2.putText(frame, text, ((w - tw) // 2, h // 2 + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

    def verify(self) -> bool:
        if not self._load_model():
            return False

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("  [ERROR] Cannot open camera")
            return False

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS,          30)

        win = "ARK Admin — Face Verification"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)

        confirm_count = 0
        frame_num     = 0
        start_time    = datetime.now()
        verified      = False
        last_boxes    = []

        print(f"\n  Camera open. Only '{ADMIN_NAME}' can open the admin panel.")
        print(f"  Press ESC or 'q' to cancel.\n")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_num += 1
            elapsed   = (datetime.now() - start_time).total_seconds()
            remaining = max(0, VERIFY_TIMEOUT_S - elapsed)
            display   = frame.copy()
            h, w      = frame.shape[:2]

            if elapsed > VERIFY_TIMEOUT_S:
                self._banner(display, "VERIFICATION TIMED OUT", (0, 80, 180), h, w)
                cv2.imshow(win, display)
                cv2.waitKey(1500)
                break

            # Run recognition every 3rd frame
            if frame_num % 3 == 0:
                small    = cv2.resize(frame, (0, 0), fx=SCALE_FACTOR, fy=SCALE_FACTOR)
                rgb      = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                locs     = face_recognition.face_locations(rgb, model="hog")
                encs     = face_recognition.face_encodings(rgb, locs)
                last_boxes = []

                for loc, enc in zip(locs, encs):
                    name, conf = self._identify(enc)
                    t  = int(loc[0] / SCALE_FACTOR)
                    r  = int(loc[1] / SCALE_FACTOR)
                    b  = int(loc[2] / SCALE_FACTOR)
                    l  = int(loc[3] / SCALE_FACTOR)
                    is_admin  = (name == ADMIN_NAME)
                    color     = (0, 220, 0) if is_admin else (0, 0, 220)
                    last_boxes.append((l, t, r, b, color, name, conf))
                    if is_admin:
                        confirm_count += 1
                        print(f"  Match #{confirm_count}: {name} ({conf:.0%})")
                    elif name != "Unknown":
                        print(f"  Wrong person: {name} — resetting")
                        confirm_count = 0

            # Draw cached boxes
            for lx, ty, rx, by, col, n, c in last_boxes:
                cv2.rectangle(display, (lx, ty), (rx, by), col, 2)
                cv2.putText(display, f"{n} ({c:.0%})",
                            (lx, ty - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)

            # Progress bar
            progress = min(confirm_count / CONFIRM_FRAMES, 1.0)
            bar_w    = w - 20
            filled   = int(bar_w * progress)
            cv2.rectangle(display, (10, h - 30), (10 + bar_w, h - 10), (40, 40, 40), -1)
            cv2.rectangle(display, (10, h - 30), (10 + filled, h - 10), (0, 220, 0), -1)
            cv2.putText(display,
                        f"Verifying {ADMIN_NAME}...  {confirm_count}/{CONFIRM_FRAMES}",
                        (10, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

            # Top bar
            cv2.rectangle(display, (0, 0), (w, 46), (20, 20, 20), -1)
            cv2.putText(display,
                        f"ARK ADMIN PANEL  |  Identity required: {ADMIN_NAME}  |  Timeout: {remaining:.0f}s",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (160, 160, 160), 1)

            # Verified
            if confirm_count >= CONFIRM_FRAMES:
                self._banner(display, f"VERIFIED: {ADMIN_NAME}", (0, 180, 0), h, w)
                cv2.imshow(win, display)
                cv2.waitKey(1100)
                verified = True
                break

            cv2.imshow(win, display)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                print("  Cancelled.")
                break

        cap.release()
        cv2.destroyAllWindows()
        return verified


# ==================== ACCESS RULES DB ====================
class AccessRulesDB:
    def __init__(self):
        self.client = None
        self.db     = None

    def connect(self) -> bool:
        try:
            self.client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            self.client.server_info()
            self.db = self.client[DB_NAME]
            self.db["access_rules"].create_index("name", unique=True)
            return True
        except Exception as e:
            print(f"  [ERROR] MongoDB: {e}")
            return False

    def get_all_persons(self) -> list:
        try:
            return list(self.db["persons"].find(
                {},
                {"name": 1, "person_id": 1, "detection_count": 1,
                 "last_seen": 1, "role": 1, "ark_student_id": 1, "_id": 0}
            ).sort("name", 1))
        except Exception:
            return []

    def get_all_rules(self) -> dict:
        try:
            return {doc["name"]: doc.get("access_allowed", True)
                    for doc in self.db["access_rules"].find()}
        except Exception:
            return {}

    def set_access(self, name: str, person_id: str, allowed: bool):
        try:
            self.db["access_rules"].update_one(
                {"name": name},
                {"$set": {"name": name, "person_id": person_id,
                           "access_allowed": allowed,
                           "modified_by": ADMIN_NAME,
                           "modified_at": datetime.now()}},
                upsert=True,
            )
        except Exception as e:
            logger.error("set_access: %s", e)

    def set_role(self, name: str, role: str, ark_id: str = ""):
        try:
            self.db["persons"].update_one(
                {"name": name},
                {"$set": {"role": role, "ark_student_id": ark_id}},
            )
        except Exception as e:
            logger.error("set_role: %s", e)

    def get_recent_detections(self, limit: int = 30) -> list:
        try:
            return list(self.db["detections"].find(
                {}, {"name": 1, "timestamp": 1, "confidence": 1,
                     "access_granted": 1, "role": 1, "_id": 0}
            ).sort("timestamp", -1).limit(limit))
        except Exception:
            return []

    def get_stats(self) -> dict:
        try:
            total   = self.db["detections"].count_documents({})
            granted = self.db["detections"].count_documents({"access_granted": True})
            denied  = self.db["detections"].count_documents({"access_granted": False})
            persons = self.db["persons"].count_documents({})
            blocked = self.db["access_rules"].count_documents({"access_allowed": False})
            return {"total": total, "granted": granted, "denied": denied,
                    "persons": persons, "blocked": blocked}
        except Exception:
            return {}

    def close(self):
        if self.client:
            self.client.close()


# ==================== ADMIN PANEL GUI ====================
class AdminPanelGUI:
    BG       = "#1a1a2e"
    PANEL_BG = "#16213e"
    ACCENT   = "#0f3460"
    GREEN    = "#00c853"
    RED      = "#d50000"
    ORANGE   = "#ff6f00"
    TEXT     = "#e0e0e0"
    SUBTEXT  = "#9e9e9e"
    WHITE    = "#ffffff"
    ROW_EVEN = "#1e2a45"
    ROW_ODD  = "#162035"

    def __init__(self, db: AccessRulesDB):
        self.db   = db
        self.root = tk.Tk()
        self._rules_cache  = {}
        self._auto_refresh = True
        self._setup_window()
        self._build_ui()
        self._refresh_all()

    def _setup_window(self):
        self.root.title("ARK Admin Panel")
        self.root.configure(bg=self.BG)
        self.root.geometry("1100x700")
        self.root.minsize(900, 580)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Dark.TFrame",  background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL_BG)

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=self.ACCENT, height=62)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  ARK ACCESS CONTROL ADMIN PANEL",
                 bg=self.ACCENT, fg=self.WHITE,
                 font=("Helvetica", 15, "bold")).pack(side="left", pady=12)
        tk.Label(hdr, text=f"  Admin: {ADMIN_NAME}  ",
                 bg="#0d2137", fg=self.GREEN,
                 font=("Helvetica", 10, "bold")).pack(side="left", padx=20, pady=16)
        self._clock = tk.Label(hdr, text="", bg=self.ACCENT, fg=self.SUBTEXT,
                               font=("Helvetica", 9))
        self._clock.pack(side="right", padx=15)
        tk.Button(hdr, text="  Logout  ", bg="#c62828", fg=self.WHITE,
                  font=("Helvetica", 10, "bold"), relief="flat", cursor="hand2",
                  command=self._logout).pack(side="right", padx=10, pady=13)

        # Body
        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        left = tk.Frame(body, bg=self.PANEL_BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._build_persons_panel(left)

        right = tk.Frame(body, bg=self.PANEL_BG, width=340)
        right.pack(side="right", fill="both", padx=(6, 0))
        right.pack_propagate(False)
        self._build_log_panel(right)

    # ── Persons panel ────────────────────────────────────────────────────────
    def _build_persons_panel(self, parent):
        title_row = tk.Frame(parent, bg=self.PANEL_BG)
        title_row.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(title_row, text="PERSON MANAGEMENT",
                 bg=self.PANEL_BG, fg=self.WHITE,
                 font=("Helvetica", 11, "bold")).pack(side="left")
        tk.Button(title_row, text="Refresh", bg=self.ACCENT, fg=self.WHITE,
                  font=("Helvetica", 9), relief="flat", cursor="hand2",
                  padx=8, pady=3, command=self._refresh_all).pack(side="right")

        # Column headers
        hdr = tk.Frame(parent, bg="#0d2137")
        hdr.pack(fill="x", padx=12, pady=(0, 4))
        for txt, w in [("Name", 22), ("Detections", 8), ("Last Seen", 15),
                        ("Role", 10), ("ARK ID", 8), ("Access", 7), ("Actions", 18)]:
            tk.Label(hdr, text=txt, bg="#0d2137", fg=self.SUBTEXT,
                     font=("Helvetica", 9, "bold"),
                     width=w, anchor="w").pack(side="left", padx=4, pady=5)

        # Scrollable list
        container = tk.Frame(parent, bg=self.PANEL_BG)
        container.pack(fill="both", expand=True, padx=12)
        canvas    = tk.Canvas(container, bg=self.PANEL_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self._persons_frame = tk.Frame(canvas, bg=self.PANEL_BG)
        self._persons_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._persons_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._stats_bar = tk.Label(parent, text="", bg=self.ACCENT,
                                   fg=self.SUBTEXT, font=("Helvetica", 9),
                                   anchor="w", padx=10)
        self._stats_bar.pack(fill="x", padx=12, pady=(0, 8))

    def _refresh_persons(self):
        self._rules_cache = self.db.get_all_rules()
        persons = self.db.get_all_persons()
        for w in self._persons_frame.winfo_children():
            w.destroy()

        if not persons:
            tk.Label(self._persons_frame,
                     text="No persons enrolled. Run annotation.py to add people.",
                     bg=self.PANEL_BG, fg=self.SUBTEXT,
                     font=("Helvetica", 10)).pack(pady=30)
            return

        for i, p in enumerate(persons):
            name      = p.get("name", "?")
            person_id = p.get("person_id", "")
            det_count = p.get("detection_count", 0)
            last_seen = p.get("last_seen")
            last_str  = last_seen.strftime("%d %b %H:%M") if isinstance(last_seen, datetime) else "Never"
            allowed   = self._rules_cache.get(name, True)
            role      = p.get("role", "student")
            ark_id    = p.get("ark_student_id", "")

            row_bg = self.ROW_EVEN if i % 2 == 0 else self.ROW_ODD
            row    = tk.Frame(self._persons_frame, bg=row_bg)
            row.pack(fill="x", pady=1)

            tk.Label(row, text=name, bg=row_bg, fg=self.WHITE,
                     font=("Helvetica", 10), width=22, anchor="w").pack(side="left", padx=4, pady=6)
            tk.Label(row, text=str(det_count), bg=row_bg, fg=self.SUBTEXT,
                     font=("Helvetica", 9), width=8, anchor="w").pack(side="left", padx=4)
            tk.Label(row, text=last_str, bg=row_bg, fg=self.SUBTEXT,
                     font=("Helvetica", 9), width=15, anchor="w").pack(side="left", padx=4)

            # Role badge
            role_color = self.GREEN if role == "teacher" else self.ORANGE
            role_lbl   = tk.Label(row, text=role.upper(), bg=row_bg, fg=role_color,
                                  font=("Helvetica", 9, "bold"), width=10, anchor="w")
            role_lbl.pack(side="left", padx=4)

            # ARK ID entry
            ark_var = tk.StringVar(value=ark_id)
            tk.Entry(row, textvariable=ark_var, bg="#0d1b2a", fg=self.WHITE,
                     font=("Helvetica", 9), width=8, relief="flat",
                     insertbackground=self.WHITE).pack(side="left", padx=4)

            # Access badge
            acc_lbl = tk.Label(row, text="OK" if allowed else "DENY",
                               bg=row_bg, fg=self.GREEN if allowed else self.RED,
                               font=("Helvetica", 9, "bold"), width=7, anchor="w")
            acc_lbl.pack(side="left", padx=4)

            # Actions
            acts = tk.Frame(row, bg=row_bg)
            acts.pack(side="left", padx=4)

            next_role = "student" if role == "teacher" else "teacher"
            tk.Button(acts, text=f"→{next_role[:3].title()}", bg=self.ACCENT,
                      fg=self.WHITE, font=("Helvetica", 8), relief="flat",
                      padx=5, pady=1, cursor="hand2",
                      command=lambda n=name, rl=role_lbl, rb_=next_role, av=ark_var:
                          self._set_role(n, rb_, rl, av)).pack(side="left", padx=2)

            tk.Button(acts, text="SaveID", bg="#2e7d32", fg=self.WHITE,
                      font=("Helvetica", 8), relief="flat", padx=5, pady=1,
                      cursor="hand2",
                      command=lambda n=name, av=ark_var, rl=role_lbl:
                          self._save_ark_id(n, av, rl)).pack(side="left", padx=2)

            acc_btn_text  = "Block" if allowed else "Allow"
            acc_btn_color = self.RED if allowed else self.GREEN
            tk.Button(acts, text=acc_btn_text, bg=acc_btn_color, fg=self.WHITE,
                      font=("Helvetica", 8, "bold"), relief="flat",
                      padx=5, pady=1, cursor="hand2",
                      command=lambda n=name, pid=person_id, a=allowed, sl=acc_lbl:
                          self._toggle_access(n, pid, a, sl)).pack(side="left", padx=2)

    # ── Log panel ────────────────────────────────────────────────────────────
    def _build_log_panel(self, parent):
        tk.Label(parent, text="RECENT DETECTIONS",
                 bg=self.PANEL_BG, fg=self.WHITE,
                 font=("Helvetica", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        log_frame = tk.Frame(parent, bg=self.PANEL_BG)
        log_frame.pack(fill="both", expand=True, padx=12)
        self._log_text = tk.Text(log_frame, bg="#0d1b2a", fg=self.TEXT,
                                 font=("Courier", 9), relief="flat",
                                 state="disabled", wrap="none")
        sc = ttk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=sc.set)
        sc.pack(side="right", fill="y")
        self._log_text.pack(side="left", fill="both", expand=True)
        self._log_text.tag_configure("granted", foreground=self.GREEN)
        self._log_text.tag_configure("denied",  foreground=self.RED)
        self._log_text.tag_configure("ts",      foreground=self.SUBTEXT)

        tk.Button(parent, text="Refresh Log", bg=self.ACCENT, fg=self.WHITE,
                  font=("Helvetica", 9), relief="flat", cursor="hand2",
                  padx=8, pady=3, command=self._refresh_log).pack(anchor="e", padx=12, pady=6)

        tk.Label(parent, text="STATISTICS", bg=self.PANEL_BG, fg=self.WHITE,
                 font=("Helvetica", 11, "bold")).pack(anchor="w", padx=12, pady=(6, 4))
        self._stats_frame  = tk.Frame(parent, bg=self.PANEL_BG)
        self._stats_frame.pack(fill="x", padx=12, pady=(0, 10))
        self._stats_labels = {}
        for key, label in [("persons", "Enrolled"), ("blocked", "Blocked"),
                            ("granted", "Total granted"), ("denied", "Total denied"),
                            ("total",   "All detections")]:
            row = tk.Frame(self._stats_frame, bg=self.PANEL_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label + ":", bg=self.PANEL_BG,
                     fg=self.SUBTEXT, font=("Helvetica", 9),
                     width=18, anchor="w").pack(side="left")
            lbl = tk.Label(row, text="—", bg=self.PANEL_BG,
                           fg=self.WHITE, font=("Helvetica", 9, "bold"), anchor="w")
            lbl.pack(side="left")
            self._stats_labels[key] = lbl

    # ── Actions ──────────────────────────────────────────────────────────────
    def _set_role(self, name: str, new_role: str, role_lbl: tk.Label, ark_var):
        ark_id = ark_var.get().strip()
        self.db.set_role(name, new_role, ark_id)
        color = self.GREEN if new_role == "teacher" else self.ORANGE
        role_lbl.configure(text=new_role.upper(), fg=color)
        logger.info("Role: %s → %s", name, new_role)

    def _save_ark_id(self, name: str, ark_var, role_lbl: tk.Label):
        ark_id   = ark_var.get().strip()
        cur_role = "teacher" if role_lbl.cget("text") == "TEACHER" else "student"
        self.db.set_role(name, cur_role, ark_id)
        messagebox.showinfo("Saved", f"ARK ID '{ark_id}' saved for {name}.", parent=self.root)

    def _toggle_access(self, name: str, person_id: str,
                       currently_allowed: bool, acc_lbl: tk.Label):
        new_allowed = not currently_allowed
        if not new_allowed:
            if not messagebox.askyesno("Confirm", f"Block access for '{name}'?",
                                        parent=self.root):
                return
        self.db.set_access(name, person_id, new_allowed)
        acc_lbl.configure(
            text="OK" if new_allowed else "DENY",
            fg=self.GREEN if new_allowed else self.RED,
        )
        self._refresh_stats()

    # ── Refresh ──────────────────────────────────────────────────────────────
    def _refresh_all(self):
        self._refresh_persons()
        self._refresh_log()
        self._refresh_stats()

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
            self._log_text.insert("end", f"{name:<22} {conf:.0%}\n")
        self._log_text.configure(state="disabled")
        self._log_text.see("1.0")

    def _refresh_stats(self):
        stats = self.db.get_stats()
        for key, lbl in self._stats_labels.items():
            lbl.configure(text=str(stats.get(key, "—")))
        p = stats.get("persons", 0)
        b = stats.get("blocked", 0)
        self._stats_bar.configure(
            text=f"  {p} enrolled  |  {b} blocked  |  {p - b} active  |  "
                 f"Updated: {datetime.now().strftime('%H:%M:%S')}")

    # ── Clock + auto-refresh ─────────────────────────────────────────────────
    def _tick(self):
        self._clock.configure(text=datetime.now().strftime("%d %b %Y  %H:%M:%S") + "  ")
        self.root.after(1000, self._tick)

    def _auto_loop(self):
        if self._auto_refresh:
            self._refresh_log()
            self._refresh_stats()
        self.root.after(5000, self._auto_loop)

    # ── Lifecycle ────────────────────────────────────────────────────────────
    def _logout(self):
        if messagebox.askyesno("Logout", "Close admin panel?", parent=self.root):
            self._auto_refresh = False
            self.db.close()
            self.root.destroy()

    def _on_close(self):
        self._auto_refresh = False
        self.db.close()
        self.root.destroy()

    def run(self):
        self._tick()
        self._auto_loop()
        self.root.mainloop()


# ==================== MAIN ====================
def main():
    print("\n" + "=" * 65)
    print("  ARK ADMIN — Face Verification → Admin Panel")
    print("=" * 65)
    print(f"  Only '{ADMIN_NAME}' can open the admin panel.")
    print(f"  Model: {MODEL_PATH}  |  DB: {MONGO_URI}{DB_NAME}")
    print("=" * 65 + "\n")

    # Step 1 — Connect MongoDB
    print("  Connecting to MongoDB...")
    db = AccessRulesDB()
    if not db.connect():
        print("  [ERROR] Cannot connect to MongoDB. Is it running?")
        return
    print("  Connected.\n")

    # Step 2 — Live face verification
    print(f"  Starting camera verification for '{ADMIN_NAME}'...")
    verifier = FaceVerifier()
    verified = verifier.verify()

    # Step 3 — Open admin panel or exit
    if not verified:
        print(f"\n  Access denied. Only '{ADMIN_NAME}' can open this panel.")
        db.close()
        return

    print(f"\n  Verified as '{ADMIN_NAME}'. Opening admin panel...\n")
    gui = AdminPanelGUI(db=db)
    gui.run()


if __name__ == "__main__":
    main()
