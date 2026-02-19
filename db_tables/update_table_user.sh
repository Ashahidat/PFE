#!/bin/bash

SQL_FILE="$HOME/PFE/db_tables/users_db_permissions.sql"
TMP_FILE="/tmp/users_db_permissions.sql"

echo "📁 Copie du fichier SQL vers /tmp..."
cp "$SQL_FILE" "$TMP_FILE"

echo "🐘 Exécution avec l'utilisateur postgres..."
sudo -u postgres psql -f "$TMP_FILE"

echo "✅ Terminé."

# chmod +x db_tables/update_table_user.sh
# ./db_tables/update_table_user.sh