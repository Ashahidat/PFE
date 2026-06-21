#!/usr/bin/env bash
# Reset local Grafana state so stale folders/dashboards disappear.
set -euo pipefail

GRAFANA_DB_DIR="/var/lib/grafana"
GRAFANA_DB="${GRAFANA_DB_DIR}/grafana.db"
STATE_FILES=(
  "${GRAFANA_DB}"
  "${GRAFANA_DB}.shm"
  "${GRAFANA_DB}.wal"
  "${GRAFANA_DB}-journal"
)

if [[ "${EUID}" -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    exec sudo -E bash "$0" "$@"
  fi
  echo "Run as root (use sudo)." >&2
  exit 1
fi

stop_grafana() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl stop grafana-server || systemctl stop grafana || true
  elif command -v service >/dev/null 2>&1; then
    service grafana-server stop || true
  fi
}

start_grafana() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl start grafana-server || systemctl start grafana || true
  elif command -v service >/dev/null 2>&1; then
    service grafana-server start || true
  fi
}

echo "➡️  [0/3] Arrêt de Grafana..."
stop_grafana

if [[ -f "${GRAFANA_DB}" ]]; then
  ts="$(date +%Y%m%d-%H%M%S)"
  backup="${GRAFANA_DB}.bak-${ts}"
  echo "➡️  [1/3] Sauvegarde de la base Grafana vers ${backup}..."
  cp -a "${GRAFANA_DB}" "${backup}"
else
  echo "➡️  [1/3] Base Grafana introuvable, pas de sauvegarde à faire."
fi

echo "➡️  [2/3] Suppression de l'état local Grafana (dashboards/folders/users) ..."
mkdir -p "${GRAFANA_DB_DIR}"
for path in "${STATE_FILES[@]}"; do
  rm -f "${path}"
done

echo "➡️  [3/3] Redémarrage de Grafana..."
start_grafana

echo "✅ Réinitialisation Grafana terminée"
echo "   - La base SQLite locale a été supprimée"
echo "   - Les dashboards et folders provisionnés seront recréés à la demande"
