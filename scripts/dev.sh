#!/usr/bin/env bash
# Local dev: seed the featured report, run the intel API and the web app together.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/apps/intel"
uv sync -q
uv run python -m intel.seed tests/fixtures/netchex_snapshot.json >/dev/null
uv run uvicorn intel.api:app --port 8000 --reload &
INTEL_PID=$!
trap 'kill $INTEL_PID 2>/dev/null' EXIT
cd "$ROOT/apps/web"
[ -d node_modules ] || npm install
INTEL_URL=http://127.0.0.1:8000 npm run dev
