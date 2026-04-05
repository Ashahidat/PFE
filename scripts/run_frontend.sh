#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR"/.. && pwd)"

FRONTEND_DIR="$PROJECT_ROOT/pip/data_quality/app/frontend"

cd "$FRONTEND_DIR" || exit 1

echo "📡 Frontend statique servi sur http://localhost:8002"
exec python3 -m http.server 8002
