# ECHO ARK — Setup Guide

## Architecture Overview

```
Mobile (React Native/Expo APK)
        │  LAN WiFi
        ▼
[FastAPI Backend]  ←→  [Ollama :11434]  (qwen2.5-vl:7b)
        │
        ├── [Redis :6379]     ← offline cache + pub/sub
        ├── [MongoDB :27017]  ← persistent storage
        └── [Obsidian Vault]  ← RAG knowledge base

[React Dashboard]  ←→  [FastAPI WebSocket]
```

---

## 1. Prerequisites

Install these on the teacher's PC:

- **Python 3.11+**: https://python.org
- **Node.js 20+**: https://nodejs.org
- **Redis**: `winget install Redis.Redis` or https://github.com/microsoftarchive/redis/releases
- **MongoDB**: `winget install MongoDB.Server` or https://www.mongodb.com/try/download/community
- **Ollama**: https://ollama.com/download
- **Expo CLI** (for mobile dev): `npm install -g expo-cli eas-cli`

---

## 2. Pull the Ollama model

```bash
# Primary model — vision + text + multilingual (4.5 GB)
ollama pull qwen2.5-vl:7b

# Lightweight fallback (1.1 GB, faster, less capable)
ollama pull moondream2
```

Verify: `ollama list`

---

## 3. Backend setup

```bash
cd backend

# Copy and edit environment config
cp .env.example .env
# Edit .env:
#   OBSIDIAN_VAULT_PATH=C:/Users/YourName/Documents/ObsidianVault
#   DWANI_API_KEY=your_key (optional, for voice)

pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Test: http://localhost:8000/api/status

---

## 4. Dashboard setup

```bash
cd dashboard
npm install
npm start
```

Opens at http://localhost:3000

---

## 5. Mobile app setup

### For development (on same WiFi as PC):

```bash
cd mobile
npm install
npx expo start
```

Scan QR code with **Expo Go** app (Android/iOS).

Update your PC's local IP in the app setup screen (e.g. `http://192.168.1.100:8000`).
Find your IP: `ipconfig` on Windows, look for IPv4 Address.

### Build an APK (for distribution):

```bash
cd mobile
eas login          # Create free Expo account
eas build:configure

# Build APK
eas build --platform android --profile apk
```

Download the `.apk` from the Expo dashboard and install on Android devices.

---

## 6. Demo seed data

Once the backend is running:

```bash
cd backend/data
python demo_seed.py
```

This adds 9 demo students with different fingerprints for the teacher dashboard demo.

---

## 7. Obsidian vault integration

1. Set `OBSIDIAN_VAULT_PATH` in `.env` to your vault directory
2. Restart the backend — it auto-indexes on startup
3. In the teacher dashboard, use the "Obsidian Vault Chat" panel to query your notes
4. For image questions: use the mobile app's "Image Chat" feature

---

## 8. Services quick-start (Windows)

```bash
# Start Redis (if installed as service)
net start Redis

# Start MongoDB (if installed as service)
net start MongoDB

# Start Ollama (runs as background service after install)
ollama serve

# Backend
cd ARK/backend && python -m uvicorn app:app --host 0.0.0.0 --port 8000

# Dashboard
cd ARK/dashboard && npm start
```

---

## 9. Offline behavior

| Scenario | Behavior |
|---|---|
| Phone + LAN WiFi, internet down | Uses Ollama on teacher's PC via LAN |
| Phone + no network at all | Uses cached fingerprint responses from AsyncStorage |
| Network restored | App auto-syncs queued results to Redis → MongoDB |
| Dashboard | WebSocket reconnects automatically; falls back to 10s polling |

---

## 10. Recommended Ollama models

| Model | Size | Speed | Capability |
|---|---|---|---|
| `qwen2.5-vl:7b` | 4.5 GB | ~30-40s on CPU | **Best** — vision + text + multilingual |
| `llava:7b` | 4.5 GB | ~30-40s on CPU | Good vision, less multilingual |
| `moondream2` | 1.1 GB | ~8-12s | Lightweight — decent vision, less text quality |
| `phi3.5` | 2.2 GB | ~15s | Fast text, no vision |

**Recommended**: `qwen2.5-vl:7b` — handles Hindi/Kannada output and image analysis.
