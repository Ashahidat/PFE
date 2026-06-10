#!/bin/bash
cd /home/ashahi/PFE/pip/data_quality/app/frontend-react || exit
LOG_FILE=/tmp/pfe-frontend.log
nohup npm run dev >"$LOG_FILE" 2>&1 &
echo "Frontend lancé. Logs: $LOG_FILE"
