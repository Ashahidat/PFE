#!/bin/bash
# 🚀 Script pour réinitialiser Apache Atlas
set -euo pipefail

ATLAS_HOME="/home/ashahi/PFE/pip/data_governance/apache-atlas-2.4.0"
ATLAS_CONF="$ATLAS_HOME/conf/atlas-application.properties"
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ATLAS_HTTP_PORT="21002"
STATE_DIRS=(
  "$ATLAS_HOME/data/hbase-root"
  "$ATLAS_HOME/data/hbase-zookeeper-data"
  "$ATLAS_HOME/data/kafka"
  "$ATLAS_HOME/data/solr"
)

echo "➡️  [0/3] Arrêt du stack Atlas/Nginx..."
"${ROOT_DIR}/pip/data_governance/stop_atlas_readonly_stack.sh" || true

echo "➡️  [1/3] Mise à jour de la configuration Atlas (port ${ATLAS_HTTP_PORT})..."
sed -i \
  -e "s|^#*atlas.server.http.port=.*|atlas.server.http.port=${ATLAS_HTTP_PORT}|" \
  -e "s|^atlas.rest.address=http://[^:]*:[0-9][0-9]*|atlas.rest.address=http://127.0.0.1:${ATLAS_HTTP_PORT}|" \
  -e "s|^#*atlas.server.address.id1=[^:]*:[0-9][0-9]*|#atlas.server.address.id1=localhost:${ATLAS_HTTP_PORT}|" \
  -e "s|^#*atlas.server.bind.address=.*|atlas.server.bind.address=127.0.0.1|" \
  "$ATLAS_CONF"

echo "➡️  [2/3] Nettoyage de l'état local Atlas (HBase/ZK/Kafka/Solr)..."
for state_dir in "${STATE_DIRS[@]}"; do
  mkdir -p "$state_dir"
  find "$state_dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
done

echo "✅ Réinitialisation Atlas terminée"
