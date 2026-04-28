# ARK — Commands Reference

## Start the Backend (run this every time)

```cmd
cd C:\Users\Aranya\Pictures\ARK\backend
C:\Python314\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open teacher dashboard in browser:
```
http://localhost:8000/dashboard
```

---

## Check Backend is Running

```cmd
curl http://localhost:8000/api/status
```

---

## Seed Demo Student Data (for demo/testing)

```cmd
cd C:\Users\Aranya\Pictures\ARK\backend\data
python demo_seed.py
```

---

## Build the Android APK

```cmd
set PATH=C:\Program Files\nodejs;C:\Users\Aranya\AppData\Roaming\npm;%PATH%
cd C:\Users\Aranya\Pictures\ARK\mobile
eas build --platform android --profile apk
```

Download link appears in terminal when build finishes (~10 min).

---

## Check EAS Build Status

```cmd
set PATH=C:\Program Files\nodejs;C:\Users\Aranya\AppData\Roaming\npm;%PATH%
cd C:\Users\Aranya\Pictures\ARK\mobile
eas build:list --platform android --limit 3
```

---

## Run Expo Dev Mode (for testing without APK build)

```cmd
set PATH=C:\Program Files\nodejs;%PATH%
cd C:\Users\Aranya\Pictures\ARK\mobile
npx expo start --lan
```

Scan QR code with Expo Go app. Phone must be on same WiFi.

---

## Install / Reinstall Mobile Dependencies

```cmd
set PATH=C:\Program Files\nodejs;%PATH%
cd C:\Users\Aranya\Pictures\ARK\mobile
npm install --legacy-peer-deps
```

---

## Re-index Obsidian Vault

```cmd
curl -X POST http://localhost:8000/api/obsidian/index
```

---

## Clear Student Session Data

```cmd
curl -X DELETE http://localhost:8000/api/session
```

---

## Start All Services (Windows — run as Admin)

```cmd
:: Redis (if installed as service)
net start Redis

:: MongoDB (if installed as service)
net start MongoDB

:: Ollama
ollama serve

:: Backend
cd C:\Users\Aranya\Pictures\ARK\backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

---

## Check / Pull Ollama Model

```cmd
:: Check what is installed
ollama list

:: Pull the model (one time, 6.6 GB)
ollama pull qwen3.5:9b

:: Pull vision model for image chat (one time, 1.1 GB)
ollama pull moondream2
```

---

## Find Your PC IP Address (for mobile app setup)

```cmd
ipconfig
```

Look for **IPv4 Address** under Wi-Fi adapter.
Enter it in the ARK app as: `http://192.168.x.x:8000`

Your current IP: **192.168.31.18**

---

## One-Click Launch (double-click this file)

```
C:\Users\Aranya\Pictures\ARK\start.bat
```

Launches backend + Expo in separate windows and opens dashboard in browser.

---

## EAS Login (one time)

```cmd
set PATH=C:\Program Files\nodejs;C:\Users\Aranya\AppData\Roaming\npm;%PATH%
eas login
```

Expo account: **beaconbandhu**

---

## Project Paths

| Component       | Path                                          |
|----------------|-----------------------------------------------|
| Backend        | `C:\Users\Aranya\Pictures\ARK\backend\`       |
| Mobile app     | `C:\Users\Aranya\Pictures\ARK\mobile\`        |
| Dashboard HTML | `C:\Users\Aranya\Pictures\ARK\backend\templates\dashboard.html` |
| .env config    | `C:\Users\Aranya\Pictures\ARK\backend\.env`   |
| Hex graph data | `C:\Users\Aranya\Pictures\ARK\backend\data\science_grade6.json` |
| Offline cache  | `C:\Users\Aranya\Pictures\ARK\backend\data\cache.json` |
