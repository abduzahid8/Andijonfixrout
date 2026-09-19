#!/bin/bash
# RoadPulse dev launcher
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-$HOME/.local/bin/python3.11}"
"$PY" -m venv "$ROOT/.venv" 2>/dev/null || true
source "$ROOT/.venv/bin/activate"
pip install -q -r "$ROOT/backend/requirements.txt"
python "$ROOT/init_db.py"
uvicorn backend.app.main:app --reload --port 8000 --app-dir "$ROOT"
