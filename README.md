# RoadPulse 🛣️ — Telegram Mini App + FastAPI + Admin Dashboard

Crowdsourced road-defect reporting: users photograph potholes in a Telegram Mini App,
Gemini 1.5 Flash verifies the defect, points are awarded, and the city sees a live heatmap.

## Architecture

```
Telegram Mini App (/client) ─┐
                             ├─→ FastAPI (:8000) → SQLite + /media/uploads + Gemini Vision
Admin Dashboard (/dashboard) ┘
```

## Quickstart

```bash
cp backend/.env.example .env          # optional: set GEMINI_API_KEY, MOCK_AI=false for real AI
~/.local/bin/python3.11 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
python init_db.py                     # creates roadpulse.db + seeds 24 Tashkent points
uvicorn backend.app.main:app --reload --port 8000
```

Open:
- Mini App: http://localhost:8000/client/ (or http://localhost:8000/)
- Dashboard: http://localhost:8000/dashboard/
- API docs: http://localhost:8000/docs

## API (spec §3)

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/reports` | multipart `photo, latitude, longitude, telegram_user_id` (+optional `username, first_name`) → 201 success / 422 AI-rejected |
| GET | `/api/v1/map/points?min_lat&max_lat&min_lng&max_lng` | active + in_review points for Leaflet |
| GET | `/api/v1/admin/stats` | totals + critical zones |
| GET | `/api/v1/admin/reports?limit&offset&status` | latest table rows |
| PATCH | `/api/v1/admin/reports/{id}` | `{"status":"repaired"}` |
| GET | `/api/v1/users/{telegram_id}` | points header |
| GET | `/health` | liveness |

## AI pipeline (spec §4)

1. Image analysed **before** saving. `is_road==false` or `has_defect==false` → 422, nothing persisted.
2. `confidence < 0.65` → `in_review` (yellow), 0 points. Otherwise `active` + 10 points.
3. Without `GEMINI_API_KEY` (or `MOCK_AI=true`) a deterministic mock verdict is used so the demo never stalls.

To use real Gemini: `pip install google-generativeai`, set `GEMINI_API_KEY`, `MOCK_AI=false`.

## Demo seed

`mock_data.json` holds 24 points; 12 clustered on **Amir Temur Avenue** → red heat zone.
`init_db.py [--reset]` reseeds. The server also auto-seeds an empty DB on startup.

## Project structure

```
backend/app/      FastAPI: main, config, models, schemas, routers/
  seed.py | crud.py | storage.py | spatial.py | ai_service.py | auth.py
backend/tests/    pytest suite (isolated in-memory DB)
client/           Telegram Mini App (index.html + app.js, Leaflet)
dashboard/        Admin dashboard (index.html + dashboard.js, Leaflet.heat)
mock_data.json    24 demo points · init_db.py [--reset] seeds them
```

## Development

```bash
pip install -r backend/requirements-dev.txt
ruff check backend init_db.py run_bot.py   # lint
pytest                                      # tests (uploads go to a tmp dir)
```

CI (`.github/workflows/ci.yml`) runs lint + tests on every push/PR.

## Deploy with Docker

```bash
docker compose up --build   # API on :8000, bot polling, data in a volume
```

Needs `.env` with `TELEGRAM_BOT_TOKEN` / `MINI_APP_URL` next to the compose file.
Point Telegram at `https://<your-host>/client/` afterwards.

## Telegram Mini App

The client is Telegram-native with a browser fallback:

- Follows the user's Telegram theme (`themeParams` → app colors, dark/light map tiles, live `themeChanged` updates)
- Native **MainButton** ("📸 Take Photo / Report") inside Telegram, HTML action bar in browsers
- Native **BackButton** closes the location picker and "My reports" sheet
- Haptics (`impact` / `notification`), avatar from Telegram photo, `initData` sent for server verification
- 📋 **My reports** sheet backed by `GET /api/v1/users/{id}/reports`

To embed in Telegram you need an HTTPS URL: expose the server (e.g. `ngrok http 8001`),
then BotFather → `/newbot` → `/newapp` → paste `https://<your-host>/client/`.

## Telegram bot (answers /start)

The bot process is separate from the API server — it must be running or
`/start` goes unanswered:

```bash
python run_bot.py   # long polling; needs TELEGRAM_BOT_TOKEN + MINI_APP_URL in .env
```

Commands: `/start` (welcome + Open button), `/points` (⭐️ balance + report count),
`/myid` (Telegram ID for admin setup), `/help`.
Keep `uvicorn` (API), `cloudflared` (HTTPS) and `run_bot.py` all running during the demo.

## MVP checklist status (spec §7)

Backend, frontend, dashboard and demo-seed items are implemented; rate limiting is
process-local sliding-window, Telegram auth validator is lenient without a bot token,
spatial clustering is grid-based (~150 m) with street-anchored `critical_zones`.
PostGIS/Geohash upgrade path is isolated in `backend/app/spatial.py`.
