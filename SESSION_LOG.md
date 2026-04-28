# ARK — Full Build Session Log
**Date:** 2026-04-29  
**Project:** ARK (formerly ECHO) — Classroom Comprehension Analysis System

---

## What Was Built

A full-stack ed-tech application:
- **Student mobile app** (React Native APK) — students submit answers, see fingerprint results
- **Teacher dashboard** (web GUI at `http://localhost:8000/dashboard`) — live class heatmap, student details, graphs
- **FastAPI backend** — 5-layer H-6 hexgraph pipeline, Ollama LLM, Redis cache, MongoDB storage
- **Obsidian Vault integration** — RAG-based note search and image chat via Ollama

---

## Architecture

```
Android Phone (ARK APK)
        │  WiFi (same network)
        ▼
Teacher's PC — FastAPI backend (:8000)
        │
        ├── Ollama (qwen3.5:9b) — LLM processing
        ├── Redis — session cache + offline sync queue
        ├── MongoDB — persistent student records
        └── Obsidian Vault — markdown RAG knowledge base

Browser → http://localhost:8000/dashboard (Teacher GUI)
```

---

## Session Timeline

### 1. Project Scaffolding
- Created full directory structure under `C:\Users\Aranya\Pictures\ARK\`
- Built all 5 pipeline layers:
  - `pipeline/parser.py` — surface claim extraction
  - `pipeline/hexgraph.py` — H-6 concept graph matcher
  - `pipeline/scorer.py` — drift score calculator
  - `pipeline/classifier.py` — fingerprint classifier (GHOST/INVERT/HOLLOW/FRAGMENT/ORPHAN)
  - `pipeline/remediation.py` — Ollama-first, cache fallback

### 2. Services
- `services/ollama_service.py` — text + vision (image) via Ollama HTTP API
- `services/redis_service.py` — Redis with **automatic in-memory fallback** when Redis not installed
- `services/mongodb_service.py` — Motor async MongoDB client
- `services/obsidian_service.py` — vault indexer + RAG query engine

### 3. Data Files
- `data/science_grade6.json` — hexgraph for photosynthesis, water cycle, food chain
- `data/cache.json` — 15 pre-built offline fingerprint responses
- `data/demo_seed.py` — seeds 9 demo students for hackathon demo

### 4. Backend (FastAPI)
- `app.py` — all API routes, WebSocket, background sync loop
- `dashboard_routes.py` — dashboard HTML serving, student detail, history endpoints
- Routes: `/analyse`, `/dashboard`, `/api/class-data`, `/api/student/{id}`, `/api/status`, `/ws/dashboard`

### 5. Teacher Dashboard
- Single HTML file at `templates/dashboard.html` — no npm/React needed
- 4 tabs: Overview | Students | Vault Chat | Settings
- Student detail modal with 3 charts:
  - **Radar chart** — H-6 hexgraph node activation
  - **Drift gauge** — semicircle score visualisation
  - **History line chart** — drift over time from MongoDB
- Live WebSocket updates + 10-second polling fallback
- App name changed from ECHO to **ARK**

### 6. Mobile App (React Native)
- Built as Expo SDK 51 project
- Single-file `App.js` — no navigation library, no netinfo (removed to fix TurboModule crash)
- Screens: Setup → Home → Result → Image Chat
- Features: answer submission, fingerprint result display, image chat with Ollama

---

## Errors Encountered and Fixed

| Error | Cause | Fix |
|---|---|---|
| `listen tcp 127.0.0.1:11434: bind` | Ollama already running | Not an error — Ollama was already up |
| `net start Redis` — service name invalid | Redis not installed | Added in-memory fallback to RedisService |
| `net start MongoDB` — access denied | MongoDB already running | Not an error — already running |
| `npm not recognized` | Node.js not installed | `choco install nodejs-lts -y` as Admin |
| Node installed but not in PATH | PATH not refreshed | Used full path `C:\Program Files\nodejs\` |
| SDK mismatch (51 vs 54) | Expo Go was SDK 54, project was SDK 51 | Kept SDK 51, used EAS build instead of Expo Go |
| `TurboModuleRegistry: PlatformConstants not found` | `@react-native-community/netinfo` not pre-bundled | Removed netinfo, replaced with `expo-network` |
| Gradle build failed | Missing `assets/` directory | Created placeholder PNG assets |
| `ARK keeps stopping` | `"main": "App.js"` wrong for production APK | Changed to `"main": "node_modules/expo/AppEntry.js"` |
| `No module named uvicorn` | Terminal using Python 3.14, not 3.12 | Installed requirements for Python 3.14 |
| Phone can't reach backend | Android blocks HTTP + Windows Firewall | Added `usesCleartextTraffic: true`, opened port 8000 in Firewall |

---

## Key Commands

### Start Backend
```cmd
cd C:\Users\Aranya\Pictures\ARK\backend
C:\Python314\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Teacher Dashboard
```
http://localhost:8000/dashboard
```

### Build Android APK
```cmd
set PATH=C:\Program Files\nodejs;C:\Users\Aranya\AppData\Roaming\npm;%PATH%
cd C:\Users\Aranya\Pictures\ARK\mobile
eas build --platform android --profile apk
```

### Check Build Status
```cmd
eas build:list --platform android --limit 3
```

### Seed Demo Data
```cmd
cd C:\Users\Aranya\Pictures\ARK\backend\data
C:\Python314\python.exe demo_seed.py
```

---

## Service Status at End of Session

| Service | Status |
|---|---|
| Ollama | Running — `qwen3.5:9b` (6.6 GB) |
| MongoDB | Running as Windows service |
| Redis | Not installed — using in-memory fallback |
| Backend | Running on port 8000 |
| APK Build | 3rd build in progress (cleartext fix) |

---

## Environment

| Item | Value |
|---|---|
| PC IP | 192.168.31.18 |
| Backend URL | http://192.168.31.18:8000 |
| Python | C:\Python314\python.exe (3.14.4) |
| Node.js | C:\Program Files\nodejs\ (v24.15.0) |
| Expo account | beaconbandhu |
| EAS project | ark-student |
| EAS project ID | 9a82c595-f557-465d-9de4-2f2f37b1723f |
| Ollama model (text) | qwen3.5:9b |
| Ollama model (vision) | moondream2 (not yet pulled) |

---

## File Structure

```
C:\Users\Aranya\Pictures\ARK\
├── COMMANDS.md                   ← all commands reference
├── SESSION_LOG.md                ← this file
├── SETUP.md                      ← full setup guide
├── start.bat                     ← one-click launcher
├── backend\
│   ├── app.py                    ← FastAPI main app
│   ├── dashboard_routes.py       ← dashboard + student detail routes
│   ├── requirements.txt
│   ├── .env                      ← environment config
│   ├── pipeline\
│   │   ├── parser.py
│   │   ├── hexgraph.py
│   │   ├── scorer.py
│   │   ├── classifier.py
│   │   └── remediation.py
│   ├── services\
│   │   ├── ollama_service.py
│   │   ├── redis_service.py
│   │   ├── mongodb_service.py
│   │   └── obsidian_service.py
│   ├── data\
│   │   ├── science_grade6.json
│   │   ├── cache.json
│   │   └── demo_seed.py
│   └── templates\
│       └── dashboard.html
└── mobile\
    ├── App.js                    ← full single-file student app
    ├── app.json
    ├── package.json
    ├── eas.json
    ├── babel.config.js
    └── assets\
        ├── icon.png
        ├── splash.png
        └── adaptive-icon.png
```
