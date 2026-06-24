#!/usr/bin/env bash
# Reset local Grafana state so stale folders/dashboards disappear.
set -euo pipefail

GRAFANA_DB_DIR="/var/lib/grafana"
GRAFANA_DB="${GRAFANA_DB_DIR}/grafana.db"
BACKUP_DIR="${GRAFANA_RESET_BACKUP_DIR:-/tmp/grafana-reset-backups}"

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
  mkdir -p "${BACKUP_DIR}"
  backup="${BACKUP_DIR}/grafana.db.bak-${ts}"
  echo "➡️  [1/3] Sauvegarde de la base Grafana vers ${backup}..."
  cp -a "${GRAFANA_DB}" "${backup}"
else
  echo "➡️  [1/3] Base Grafana introuvable, pas de sauvegarde à faire."
fi

echo "➡️  [2/3] Suppression de l'état local Grafana (dashboards/folders/users/cache) ..."
mkdir -p "${GRAFANA_DB_DIR}"

# Wipe every local state artifact so stale folders, dashboards, caches and sessions disappear.
# This is a reset command, so we intentionally prefer a full local cleanup over a partial one.
find "${GRAFANA_DB_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

echo "➡️  [3/3] Redémarrage de Grafana..."
start_grafana

echo "✅ Réinitialisation Grafana terminée"
echo "   - L'état local Grafana a été supprimé"
echo "   - Les dashboards et folders provisionnés seront recréés à la demande"
