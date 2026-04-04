#!/bin/bash

SQL_DIR="/home/ashahi/PFE/db_tables"
DEST_DIR="/tmp"
DB_NAME="pfe_db"

FILES=(
    "add_projects_table.sql"
    "datasets.sql"
    "dag_runs.sql"
    "dataset_signatures.sql"
    "column_signatures.sql"
    "classifications_table.sql"
    "dataset_versions.sql"
    "column_lineage.sql"
    "processes.sql"
    "push_history.sql"
    "data_quality_results.sql"
    "column_descriptions.sql"
    "glossary_terms.sql"
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

FILES=(
    "add_projects_table.sql"
    "datasets.sql"
    "dag_runs.sql"
    "dataset_signatures.sql"
    "column_signatures.sql"
    "classifications_table.sql"
    "dataset_versions.sql"
    "column_lineage.sql"
    "processes.sql"
    "push_history.sql"
    "data_quality_results.sql"
    "column_descriptions.sql"
    "glossary_terms.sql"
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


# chmod +x db_tables/update_tables.sh
# ./db_tables/update_tables.sh
