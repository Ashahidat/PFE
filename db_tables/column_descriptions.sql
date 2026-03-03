-- Exécuter cette commande dans PostgreSQL
\c pfe_db;

-- 🔧 MODIFICATION : Rendre atlas_guid nullable dans dataset_versions
ALTER TABLE dataset_versions ALTER COLUMN atlas_guid DROP NOT NULL;

-- 🆕 CRÉATION : Table column_descriptions
CREATE TABLE IF NOT EXISTS column_descriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    column_name TEXT NOT NULL,
    description TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    updated_by TEXT,
    UNIQUE(dataset_version_id, column_name)
);

-- Index pour les recherches par version
CREATE INDEX IF NOT EXISTS idx_column_descriptions_version 
ON column_descriptions(dataset_version_id);

-- Commentaire sur la table
COMMENT ON TABLE column_descriptions IS 'Descriptions des colonnes par version de dataset';