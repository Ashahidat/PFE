#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Legacy wrapper kept for backward compatibility.
# The stable browser entrypoint is now the FastAPI proxy on :8000/api/grafana/.
exec "${ROOT_DIR}/pip/data_governance/start_grafana_readonly_stack.sh"
