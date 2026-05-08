#!/usr/bin/env bash
set -euo pipefail

ATLAS_HOME="${ATLAS_HOME:-/home/ashahi/PFE/pip/data_governance/apache-atlas-2.4.0}"

cd "${ATLAS_HOME}/bin"

./atlas_stop.py || true
./atlas_start.py -port "${ATLAS_INTERNAL_PORT:-21001}"

