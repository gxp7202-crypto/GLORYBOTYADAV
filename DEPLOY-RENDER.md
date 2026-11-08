# 🚀 Render Deploy — YADAV LEVEL UP

## Repo
`https://github.com/gxp7202-crypto/GLORYBOTYADAV.git` — branch `main`

## Service settings (manual Web Service)

| Field | Value |
|---|---|
| Runtime | Python 3 |
| Build Command | `pip install --upgrade pip && pip install -r requirements.txt` |
| Start Command | `python main.py` |
| Health Check Path | `/health` |
| Region | Singapore |

## Environment variables

| Key | Value |
|---|---|
| `ADMIN_PASSWORD` | your password (if unset → `YADAV`) |
| `DEFAULT_REGION` | `IND` |
| `PYTHONUNBUFFERED` | `1` |

⚠️ Do **not** set `PYTHON_VERSION` to an old patch (e.g. `3.11.9`). Render removes old patch
versions and the build fails silently. Leave it unset → Render uses its default Python 3.

## ⚠️ Build-breakers that were removed from this repo
- `runtime.txt` (`python-3.11.9`) — Heroku-only format, Render build fails.
- `.python-version` (`3.11.9`) — old patch, no longer available on Render.

## After deploy — verify

1. `https://<app>.onrender.com/api/version` → must return `"ok": true`
2. `https://<app>.onrender.com/health` → `{"status": "healthy"}`
3. Open `/` → login screen shows **"✅ Server online"**
4. Enter password → dashboard unlocks

## If it still fails
Render → your service → **Logs**. Look for:
- `ModuleNotFoundError` → dependency problem
- `Render does not support Python ...` → version pin problem
- `Address already in use` / no open ports → start command problem
- build error → then old code keeps serving

Use **Manual Deploy → Clear build cache & deploy** after any env change.
