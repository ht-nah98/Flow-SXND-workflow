#!/usr/bin/env bash
# Start Flow Canvas: the FlowKit backend (API + extension bridge) and the canvas UI.
#   ./start.sh            backend in the background, canvas in the foreground (Ctrl+C stops both)
#   ./start.sh backend    backend only
#   ./start.sh canvas     canvas only (production build: fast)
#   ./start.sh canvas-dev canvas with hot reload (for coding; React dev mode is several times slower)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)
[ -f "$ROOT/.env" ] || { echo "Missing .env — copy .env.example to .env and fill it in."; exit 1; }
set -a; . "$ROOT/.env"; set +a
abs() { case "$1" in /*) echo "$1" ;; *) (mkdir -p "$ROOT/$1" && cd "$ROOT/$1" && pwd) ;; esac; }
export FLOWKIT_DATA_DIR=$(abs "${FLOWKIT_DATA_DIR:-../du-lieu}")
export FLOWKIT_OUTPUT_DIR=$(abs "${FLOWKIT_OUTPUT_DIR:-../phim}")
mkdir -p "$FLOWKIT_DATA_DIR/logs" "$FLOWKIT_OUTPUT_DIR"
LOG="$FLOWKIT_DATA_DIR/logs/backend-$(date +%Y%m%d-%H%M%S).log"

backend() {
  [ -x "$ROOT/backend/.venv/bin/python" ] || {
    python3 -m venv "$ROOT/backend/.venv"
    "$ROOT/backend/.venv/bin/pip" install -q -r "$ROOT/backend/requirements.txt"; }
  (cd "$ROOT/backend" && exec ./.venv/bin/python -m agent.main) >"$LOG" 2>&1 &
  BACKEND_PID=$!
  echo "backend  http://127.0.0.1:${API_PORT:-8110}  (pid $BACKEND_PID, log $LOG)"
}
canvas() {
  [ -d "$ROOT/canvas/node_modules" ] || (cd "$ROOT/canvas" && npm ci)
  (cd "$ROOT/canvas" && npx vite build --logLevel warn)
  echo "canvas   http://127.0.0.1:${CANVAS_PORT:-5180}"
  (cd "$ROOT/canvas" && npx vite preview)
}
canvas_dev() {
  [ -d "$ROOT/canvas/node_modules" ] || (cd "$ROOT/canvas" && npm ci)
  echo "canvas   http://127.0.0.1:${CANVAS_PORT:-5180}  (dev, hot reload)"
  (cd "$ROOT/canvas" && npx vite)
}

case "${1:-all}" in
  backend) backend ;;
  canvas) canvas ;;
  canvas-dev) canvas_dev ;;
  all) backend; trap 'kill -INT "$BACKEND_PID" 2>/dev/null || true' EXIT; canvas ;;
  *) echo "usage: $0 [all|backend|canvas|canvas-dev]"; exit 2 ;;
esac
