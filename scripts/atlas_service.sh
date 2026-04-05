#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR"/.. && pwd)"

ATLAS_HOME="$PROJECT_ROOT/pip/data_governance/apache-atlas-2.4.0"
HBASE_DIR="$ATLAS_HOME/hbase"
BIN_DIR="$ATLAS_HOME/bin"
LOG_DIR="$ATLAS_HOME/logs"
PID_FILE="$LOG_DIR/atlas.pid"
STDOUT_FILE="$LOG_DIR/atlas-stdout.log"

function ensure_dirs() {
  mkdir -p "$LOG_DIR"
}

function is_running() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid=$(<"$PID_FILE")
    if kill -0 "$pid" &>/dev/null; then
      return 0
    fi
  fi
  return 1
}

function start() {
  ensure_dirs
  if is_running; then
    echo "Atlas est déjà démarré (PID $(<"$PID_FILE"))." >&2
    return 0
  fi

  echo "➡️ Démarrage de HBase..."
  "$HBASE_DIR/bin/start-hbase.sh"
  sleep 2

  echo "➡️ Démarrage d'Apache Atlas (logs -> $STDOUT_FILE)..."
  nohup python3 "$BIN_DIR/atlas_start.py" >"$STDOUT_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  echo "✅ Atlas démarré (PID $(<"$PID_FILE"))."
}

function stop() {
  ensure_dirs
  if is_running; then
    echo "➡️ Arrêt d'Apache Atlas..."
    python3 "$BIN_DIR/atlas_stop.py"
    rm -f "$PID_FILE"
    echo "➡️ Arrêt de HBase..."
    "$HBASE_DIR/bin/stop-hbase.sh"
    echo "✅ Atlas arrêté."
  else
    echo "Atlas n'était pas en cours."
  fi
}

function status() {
  if is_running; then
    echo "Atlas en cours (PID $(<"$PID_FILE"))."
  else
    echo "Atlas n’est pas démarré."
  fi
}

function restart() {
  stop
  start
}

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <start|stop|restart|status>"
  exit 1
fi

case "$1" in
  start) start ;;
  stop) stop ;;
  restart) restart ;;
  status) status ;;
  *) echo "Action inconnue : $1" >&2; exit 1 ;;
esac
