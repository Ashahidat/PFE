#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <start|stop|restart|status>"
  exit 1
fi

ACTION="$1"

SYSTEMCTL_PATH="$(command -v systemctl || true)"
if [[ -n "$SYSTEMCTL_PATH" ]]; then
  sudo "$SYSTEMCTL_PATH" "$ACTION" grafana-server
  exit $?
fi

# Fallback pour environnements sans systemd (ex: WSL2 legacy)
case "$ACTION" in
  start)
    sudo /usr/sbin/grafana-server --config /etc/grafana/grafana.ini --homepath /usr/share/grafana &
    echo "Grafana démarré en arrière-plan (sans systemd)."
    ;;
  stop)
    sudo pkill grafana-server || true
    echo "Grafana arrêté (signal envoyé)."
    ;;
  restart)
    sudo pkill grafana-server || true
    sudo /usr/sbin/grafana-server --config /etc/grafana/grafana.ini --homepath /usr/share/grafana &
    ;;
  status)
    pgrep -fl grafana-server || echo "Grafana non trouvé en cours."
    ;;
  *)
    echo "Action inconnue : $ACTION"
    exit 1
    ;;
esac
