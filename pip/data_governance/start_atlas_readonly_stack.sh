#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

"${ROOT_DIR}/pip/data_governance/run_atlas_internal.sh"
"${ROOT_DIR}/pip/data_governance/run_nginx_atlas_readonly.sh"

echo "OK: Atlas internal (21001) + read-only UI proxy (21000) started"

