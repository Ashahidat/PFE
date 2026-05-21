#!/usr/bin/env bash
set -euo pipefail

ATLAS_HOME="${ATLAS_HOME:-/home/ashahi/PFE/pip/data_governance/apache-atlas-2.4.0}"
ATLAS_INTERNAL_BIND_ADDRESS="${ATLAS_INTERNAL_BIND_ADDRESS:-127.0.0.1}"

# Keep the write-capable Atlas listener pinned to loopback even if the distro
# is launched outside the readonly stack helper.
if [[ "${ATLAS_SERVER_OPTS:-}" != *"-Datlas.server.bind.address="* ]]; then
  export ATLAS_SERVER_OPTS="${ATLAS_SERVER_OPTS:-} -Datlas.server.bind.address=${ATLAS_INTERNAL_BIND_ADDRESS}"
fi

cd "${ATLAS_HOME}/bin"

pkill -f 'org.apache.atlas.Atlas' || true
./atlas_stop.py || true
./atlas_start.py -port "${ATLAS_INTERNAL_PORT:-21002}"
