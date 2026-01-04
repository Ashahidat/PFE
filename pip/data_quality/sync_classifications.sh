#!/bin/bash
# sync_classifications.sh

# Chemin vers votre application
APP_PATH="/home/ashahi/PFE/pip/data_quality"
LOG_FILE="/tmp/atlas_sync.log"

echo "=== Début synchronisation $(date) ===" >> $LOG_FILE

# Vérifier si Atlas est en ligne (port 21000 par défaut)
ATLAS_HOST="localhost"
ATLAS_PORT=21000

if nc -z $ATLAS_HOST $ATLAS_PORT; then
    echo "Atlas détecté sur $ATLAS_HOST:$ATLAS_PORT, lancement de la synchro..." >> $LOG_FILE
else
    echo "Atlas NON disponible sur $ATLAS_HOST:$ATLAS_PORT. Synchronisation annulée." >> $LOG_FILE
    exit 0
fi

# Activer l'environnement virtuel si nécessaire
VENV_PATH="$APP_PATH/env/bin/activate"
if [ -f "$VENV_PATH" ]; then
    source $VENV_PATH
fi

# Lancer la synchro
cd $APP_PATH
python3 sync_atlas_classifications.py >> $LOG_FILE 2>&1

echo "=== Fin synchronisation $(date) ===" >> $LOG_FILE
