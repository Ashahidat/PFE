#!/bin/bash
cd /home/ashahi/PFE/pip/data_quality/app/backend || exit
# si tu as un environnement virtuel, active-le ici, ex :
# source /home/ashahi/PFE/venv/bin/activate

if command -v curl >/dev/null 2>&1 && curl -fsS http://127.0.0.1:8000/openapi.json >/dev/null 2>&1; then
  echo "Backend already responds on port 8000. Skipping second start."
  exit 0
fi

LOG_FILE=/tmp/pfe-backend.log
nohup uvicorn main:app --reload --host 0.0.0.0 --port 8000 >"$LOG_FILE" 2>&1 &
echo "Backend lancé sur le port 8000. Logs: $LOG_FILE"
