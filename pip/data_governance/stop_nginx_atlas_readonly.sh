#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONF="${ROOT_DIR}/pip/data_governance/nginx/atlas_readonly.conf"

RUN_DIR="${NGINX_RUN_DIR:-/tmp/nginx-atlas-readonly}"

exec nginx -p "${RUN_DIR}" -c "${CONF}" -g "error_log ${RUN_DIR}/logs/error.log;" -s stop
