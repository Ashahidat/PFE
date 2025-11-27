#!/bin/bash
# 🚀 Script pour réinitialiser les données Apache Atlas (HBase + Solr)

ATLAS_HOME="/home/ashahi/PFE/pip/data_governance/apache-atlas-sources-2.4.0/distro/target/apache-atlas-2.4.0"
HBASE_DIR="$ATLAS_HOME/hbase"
SOLR_DIR="$ATLAS_HOME/solr/data"

echo "➡️  [1/4] Démarrage de HBase..."
$HBASE_DIR/bin/start-hbase.sh
sleep 5

echo "➡️  [2/4] Suppression des tables HBase..."
$HBASE_DIR/bin/hbase shell <<EOF
disable 'apache_atlas_janus'
drop 'apache_atlas_janus'
disable 'apache_atlas_entity_audit'
drop 'apache_atlas_entity_audit'
exit
EOF

echo "➡️  [3/4] Arrêt de HBase..."
$HBASE_DIR/bin/stop-hbase.sh

echo "➡️  [4/4] Nettoyage des données Solr..."
rm -rf $SOLR_DIR/*

echo "✅ Réinitialisation Atlas terminée !"
