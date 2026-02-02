#!/bin/bash

SQL_DIR="/home/ashahi/PFE/db_tables"
DEST_DIR="/tmp"
DB_NAME="pfe_db"

FILES=(
    "datasets.sql"
    "dag_runs.sql"
    "dataset_signatures.sql"
    "column_signatures.sql"
    "classifications_table.sql"
)

# Copier les fichiers vers /tmp avec l'utilisateur actuel
for FILE in "${FILES[@]}"; do
    cp "$SQL_DIR/$FILE" "$DEST_DIR/"
    if [ $? -eq 0 ]; then
        echo "Copié avec succès: $FILE"
    else
        echo "Erreur lors de la copie: $FILE"
        exit 1
    fi
done

# Passe en utilisateur postgres pour exécuter psql
sudo -i -u postgres bash <<'EOF'

DB_NAME="pfe_db"
DEST_DIR="/tmp"

# Liste des fichiers à exécuter (doit être redéfinie ici)
FILES=(
    "datasets.sql"
    "dag_runs.sql"
    "dataset_signatures.sql"
    "column_signatures.sql"
    "classifications_table.sql"
)

# Exécution des fichiers SQL
for FILE in "${FILES[@]}"; do
    echo "Exécution de $FILE sur la base $DB_NAME..."
    psql -d "$DB_NAME" -f "$DEST_DIR/$FILE"
    if [ $? -eq 0 ]; then
        echo "Exécution réussie: $FILE"
    else
        echo "Erreur lors de l'exécution: $FILE"
        exit 1
    fi
done

EOF

echo "Mise à jour des tables terminée avec succès."




# pour lancer ce script : bash db_tables/update_tables.sh
# faut d'abord le rendre exécutable : chmod +x db_tables/update_tables.sh
# puis l'éxuter : ./db_tables/update_tables.sh
