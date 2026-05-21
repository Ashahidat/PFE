#!/bin/bash
# 🚀 Script pour réinitialiser Apache Atlas

ATLAS_HOME="/home/ashahi/PFE/pip/data_governance/apache-atlas-2.4.0"
ATLAS_CONF="$ATLAS_HOME/conf/atlas-application.properties"
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
HBASE_DIR="$ATLAS_HOME/hbase"
SOLR_DIR="$ATLAS_HOME/solr/data"
ATLAS_HTTP_PORT="21002"

echo "➡️  [0/5] Arrêt du stack Atlas/Nginx..."
"${ROOT_DIR}/pip/data_governance/stop_atlas_readonly_stack.sh" || true

echo "➡️  [1/5] Mise à jour de la configuration Atlas (port ${ATLAS_HTTP_PORT})..."
sed -i \
  -e "s|^#*atlas.server.http.port=.*|atlas.server.http.port=${ATLAS_HTTP_PORT}|" \
  -e "s|^atlas.rest.address=http://[^:]*:[0-9][0-9]*|atlas.rest.address=http://127.0.0.1:${ATLAS_HTTP_PORT}|" \
  -e "s|^#*atlas.server.address.id1=[^:]*:[0-9][0-9]*|#atlas.server.address.id1=localhost:${ATLAS_HTTP_PORT}|" \
  -e "s|^#*atlas.server.bind.address=.*|atlas.server.bind.address=127.0.0.1|" \
  "$ATLAS_CONF"

echo "➡️  [2/5] Démarrage de HBase..."
$HBASE_DIR/bin/start-hbase.sh
sleep 5

echo "➡️  [3/5] Suppression des tables HBase..."
$HBASE_DIR/bin/hbase shell <<EOF
disable 'apache_atlas_janus'
drop 'apache_atlas_janus'
disable 'apache_atlas_entity_audit'
drop 'apache_atlas_entity_audit'
exit
EOF

echo "➡️  [4/5] Arrêt de HBase..."
$HBASE_DIR/bin/stop-hbase.sh

echo "➡️  [5/5] Nettoyage Solr..."
rm -rf "$SOLR_DIR"/*

echo "✅ Réinitialisation Atlas terminée"
