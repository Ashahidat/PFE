#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR"/.. && pwd)"

BACKEND_DIR="$PROJECT_ROOT/pip/data_quality/app/backend"
VENV_ACTIVATE="$PROJECT_ROOT/env/bin/activate"

cd "$BACKEND_DIR" || exit 1

if [[ -f "$VENV_ACTIVATE" ]]; then
  # shellcheck disable=SC1090
  source "$VENV_ACTIVATE"
else
  echo "❗ Le venv env/ est absent, crée-le avec: python3 -m venv env"
  exit 1
fi

echo "🚀 Lancement de FastAPI (uvicorn main:app --reload --host 0.0.0.0 --port 8000)"
exec uvicorn main:app --reload --host 0.0.0.0 --port 8000
