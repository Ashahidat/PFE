#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONF="${ROOT_DIR}/pip/data_governance/nginx/atlas_readonly.conf"

RUN_DIR="${NGINX_RUN_DIR:-/tmp/nginx-atlas-readonly}"
mkdir -p "${RUN_DIR}"
mkdir -p "${RUN_DIR}/logs"

# Set error_log early (before config parsing) to avoid permission warnings when running as a non-root user.
# Nginx on Ubuntu 1.18 doesn't support `-e`, but `-g` does.
exec nginx -p "${RUN_DIR}" -c "${CONF}" -g "error_log ${RUN_DIR}/logs/error.log;"
