#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Stop UI proxy first, then Atlas.
"${ROOT_DIR}/pip/data_governance/stop_nginx_atlas_readonly.sh" || true
(cd "${ROOT_DIR}/pip/data_governance/apache-atlas-2.4.0/bin" && ./atlas_stop.py) || true

echo "OK: read-only UI proxy + Atlas stopped"

