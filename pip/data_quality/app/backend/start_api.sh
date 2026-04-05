#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# recommended: activate a venv before running this script
# e.g. source /path/to/env/bin/activate
exec uvicorn main:app --reload --host 0.0.0.0 --port 8000
