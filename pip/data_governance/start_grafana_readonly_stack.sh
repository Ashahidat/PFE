#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Grafana is exposed through the FastAPI backend on /api/grafana/.
# This avoids the extra Nginx hop on :8081 and keeps the browser entrypoint
# aligned with the React app's default Grafana links.
"${ROOT_DIR}/scripts/grafana_start_readonly.sh"
"${ROOT_DIR}/pip/data_quality/app/backend/start_api.sh"

echo "OK: Grafana service + backend proxy (:8000/api/grafana/) started"
