# 🇮🇳 YADAV LEVEL UP — Premium Squad + Guild Bot

A Free Fire squad/guild automation engine with a premium real-time web control center.
Backend is Python (aiohttp), frontend is a single-file modern JavaScript SPA — no build step.

---

## ✨ What's inside

| Layer | File | Role |
|---|---|---|
| Engine | `main.py` | FF login, matchmaking, movement, anti-AFK, guild ops, web API |
| UI | `web/index.html` | Premium dark control center (dashboard, squads, guild, consoles) |
| Extra dashboard | `dashboard_server.py` | Standalone guild/clan dashboard (optional) |
| Schemas | `*_pb2.py` | Protobuf message definitions |

Rebranded to **YADAV LEVEL UP** with India 🇮🇳 region defaults.
Admin password is now read from the `ADMIN_PASSWORD` environment variable.

---

## 🖥️ Run locally

```bash
pip install -r requirements.txt
# optional: set your own password (default is "yadav1only")
set ADMIN_PASSWORD=mysecret        # Windows
export ADMIN_PASSWORD=mysecret     # macOS / Linux

python main.py
```

Open → http://localhost:20333

---

## 🚀 Deploy on Render

### Option A — Blueprint (recommended, one click)

1. Push this folder to a **GitHub** repo.
2. Render → **New +** → **Blueprint** → pick the repo.
3. Render reads `render.yaml` and creates the service automatically.
4. When asked, set `ADMIN_PASSWORD` (marked `sync: false`) to your own secret.
5. Deploy → open the generated `https://<name>.onrender.com` URL.

### Option B — Manual web service

| Setting | Value |
|---|---|
| Environment | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python main.py` |
| Health Check Path | `/health` |

Add environment variable `ADMIN_PASSWORD = <your secret>`.
The app binds to Render's `$PORT` automatically (falls back to `20333` locally).

---

## ⚙️ Environment variables

| Key | Default | Purpose |
|---|---|---|
| `ADMIN_PASSWORD` | `yadav1only` | Dashboard login password |
| `PORT` | `20333` | Web port (Render sets this) |
| `HOST` | `0.0.0.0` | Bind address |
| `DEFAULT_REGION` | `IND` | FF region (`IND`, `BD`, `SG`, …) |

---

## ⚠️ Important — Render's disk is ephemeral

`token_cache.json`, `accounts.json`, `devices.json` are written at runtime and **reset on every
redeploy/restart**. Accounts re-login automatically when re-added. For persistence, attach a
Render **Disk** and point these paths at the mounted volume.

---

© 2026 YADAV LEVEL UP — All Rights Reserved.
