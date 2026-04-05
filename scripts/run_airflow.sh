#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR"/.. && pwd)"

VENV_ACTIVATE="$PROJECT_ROOT/env/bin/activate"
AIRFLOW_HOME="$PROJECT_ROOT/pip/data_quality/orchestration/airflow"

if [[ -f "$VENV_ACTIVATE" ]]; then
  # shellcheck disable=SC1090
  source "$VENV_ACTIVATE"
else
  echo "❗ Le venv env/ est absent, crée-le avec : python3 -m venv env"
  exit 1
fi

export AIRFLOW_HOME

cd "$AIRFLOW_HOME" || exit 1

echo "🛠️  Airflow standalone (webserver + scheduler) démarré depuis $AIRFLOW_HOME"
echo "ℹ️  UI: http://localhost:8080 (admin/admin par défaut). Ctrl+C pour arrêter."

exec airflow standalone
