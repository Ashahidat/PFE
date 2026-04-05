#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔐 Ajout de la clé Grafana et du dépôt officiel..."

sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://apt.grafana.com/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/grafana.gpg
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list >/dev/null

sudo apt update
sudo apt install -y grafana

echo "✅ Grafana installé."
echo "Tu peux maintenant lancer le service avec :"
echo "  scripts/grafana_service.sh start"
echo "Et l’arrêter avec :"
echo "  scripts/grafana_service.sh stop"
