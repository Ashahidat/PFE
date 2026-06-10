#!/bin/bash
cd /home/ashahi/PFE/pip/data_quality/app/backend || exit
# si tu as un environnement virtuel, active-le ici, ex :
# source /home/ashahi/PFE/venv/bin/activate

LOG_FILE=/tmp/pfe-backend.log
nohup uvicorn main:app --reload --host 0.0.0.0 --port 8000 >"$LOG_FILE" 2>&1 &
echo "Backend lancé sur le port 8000. Logs: $LOG_FILE"
