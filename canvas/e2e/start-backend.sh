#!/usr/bin/env bash
# Starts an isolated FlowKit (temp DB, assistant provider) + a fake media worker for E2E.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
FK=$(cd "$HERE/../../backend" && pwd)
TMP=$(mktemp -d)
FIX="$TMP/fixtures"
mkdir -p "$FIX"
[ -f "$FIX/img.png" ] || ffmpeg -v error -y -f lavfi -i color=c=orange:s=640x360 -frames:v 1 "$FIX/img.png"
[ -f "$FIX/vid.mp4" ] || ffmpeg -v error -y -f lavfi -i color=c=blue:s=640x360:d=2 -c:v libx264 -pix_fmt yuv420p "$FIX/vid.mp4"
FK_URL=http://127.0.0.1:8120 FK_IMG="$FIX/img.png" FK_VID="$FIX/vid.mp4" node "$HERE/fake-worker.mjs" &
WORKER=$!
trap 'kill $WORKER 2>/dev/null || true; rm -rf "$TMP"' EXIT
cd "$FK"
FLOWKIT_DB_PATH="$TMP/e2e.db" FLOWKIT_DATA_DIR="$TMP" FLOWKIT_OUTPUT_DIR="$TMP/phim" API_PORT=8120 WS_PORT=9243 DEFAULT_PROVIDER=assistant \
FLOW_PROJECT_ID=e2e-flow-project FK_ALLOWED_UI_ORIGINS=http://127.0.0.1:5181 \
ASSISTANT_PROVIDER_POLL_S=1 POLL_INTERVAL=1 \
FK_EXTENSION_ID=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa ./.venv/bin/python -m agent.main
