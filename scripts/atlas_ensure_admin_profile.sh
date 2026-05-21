#!/usr/bin/env bash
set -euo pipefail

# Ensure the default Atlas user profile exists after a fresh/reset Atlas start.
#
# Usage:
#   ./scripts/atlas_ensure_admin_profile.sh
#   ATLAS_URL=http://localhost:21002 ATLAS_USER=admin ATLAS_PASS=admin ./scripts/atlas_ensure_admin_profile.sh

ATLAS_URL="${ATLAS_URL:-http://localhost:21002}"
ATLAS_USER="${ATLAS_USER:-admin}"
ATLAS_PASS="${ATLAS_PASS:-admin}"

VERSION_URL="${ATLAS_URL%/}/api/atlas/admin/version"
PROFILE_GET_URL="${ATLAS_URL%/}/api/atlas/v2/entity/uniqueAttribute/type/__AtlasUserProfile?attr:name=${ATLAS_USER}"
PROFILE_POST_URL="${ATLAS_URL%/}/api/atlas/v2/entity"

wait_seconds="${WAIT_SECONDS:-60}"

echo "[atlas] Waiting for Atlas: ${VERSION_URL} (timeout: ${wait_seconds}s)"
start_ts="$(date +%s)"
while true; do
  code="$(curl -sS -u "${ATLAS_USER}:${ATLAS_PASS}" -o /dev/null -w "%{http_code}" "${VERSION_URL}" || true)"
  if [[ "${code}" == "200" ]]; then
    break
  fi
  now_ts="$(date +%s)"
  if (( now_ts - start_ts >= wait_seconds )); then
    echo "[atlas] Atlas not ready (last HTTP ${code})."
    exit 1
  fi
  sleep 2
done

code="$(curl -sS -u "${ATLAS_USER}:${ATLAS_PASS}" -o /dev/null -w "%{http_code}" "${PROFILE_GET_URL}" || true)"
if [[ "${code}" == "200" ]]; then
  echo "[atlas] __AtlasUserProfile exists for '${ATLAS_USER}'."
  exit 0
fi

echo "[atlas] __AtlasUserProfile missing for '${ATLAS_USER}' (HTTP ${code}). Creating..."
curl -sS -u "${ATLAS_USER}:${ATLAS_PASS}" \
  -H "Content-Type: application/json" \
  -X POST "${PROFILE_POST_URL}" \
  -d "{
    \"entity\": {
      \"typeName\": \"__AtlasUserProfile\",
      \"attributes\": {
        \"name\": \"${ATLAS_USER}\",
        \"qualifiedName\": \"${ATLAS_USER}@atlas\"
      }
    }
  }" >/dev/null

echo "[atlas] Created __AtlasUserProfile for '${ATLAS_USER}'."
