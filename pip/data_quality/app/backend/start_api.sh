#!/bin/bash
cd /home/ashahi/PFE/pip/data_quality/app/backend || exit
# si tu as un environnement virtuel, active-le ici, ex :
# source /home/ashahi/PFE/venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
