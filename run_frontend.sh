#!/usr/bin/env bash
# Start the I-ITSM web UI (macOS / Linux). Usage: ./run_frontend.sh   (backend must be running on :8000)
set -euo pipefail
cd "$(dirname "$0")/frontend"
if [ ! -d node_modules ]; then
  echo "Installing frontend dependencies (npm ci) ..."
  npm ci
fi
exec npm run dev -- --host 127.0.0.1
