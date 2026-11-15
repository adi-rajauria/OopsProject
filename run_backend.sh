#!/usr/bin/env bash
# Start the I-ITSM API (macOS / Linux). Usage: ./run_backend.sh
set -euo pipefail
cd "$(dirname "$0")/backend"

PYTHON="${PYTHON:-python3.14}"
if [ ! -d .venv ]; then
  echo "Creating virtual environment with $PYTHON ..."
  "$PYTHON" -m venv .venv
fi
.venv/bin/python -m pip --version >/dev/null 2>&1 || .venv/bin/python -m ensurepip --upgrade >/dev/null
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt

if [ ! -f .env ]; then
  echo "backend/.env is missing. Run: cp backend/.env.example backend/.env  (then set ITSM_DATABASE_URL and ITSM_JWT_SECRET)"
  exit 1
fi

.venv/bin/alembic upgrade head
exec .venv/bin/uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
