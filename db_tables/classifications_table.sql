\c pfe_db;

-- Créer la table si elle n'existe pas déjà
CREATE TABLE IF NOT EXISTS entity_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    entity_type TEXT NOT NULL CHECK (entity_type IN ('DATASET', 'COLUMN')),
    entity_id UUID NOT NULL,

    atlas_guid TEXT NOT NULL,

    classification_name TEXT NOT NULL,
    classification_attributes JSONB,

    applied_by VARCHAR(50) NOT NULL,
    department VARCHAR(100) NOT NULL,

    applied_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,

    column_name TEXT  -- ajouté directement ici
);

-- Créer l'index unique partiel si il n'existe pas déjà
CREATE UNIQUE INDEX IF NOT EXISTS one_active_classification
ON entity_classifications (entity_type, entity_id, column_name)
WHERE is_active = TRUE;

-- Ajouter à entity_classifications existante
-- ALTER TABLE entity_classifications 
-- ADD COLUMN IF NOT EXISTS validated_by VARCHAR(50) REFERENCES users(employee_id),
-- ADD COLUMN IF NOT EXISTS validated_at TIMESTAMP,
-- ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
