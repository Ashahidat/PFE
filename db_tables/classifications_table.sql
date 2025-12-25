\c pfe_db;

CREATE TABLE entity_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    entity_type TEXT NOT NULL CHECK (entity_type IN ('DATASET', 'COLUMN')),
    entity_id UUID NOT NULL,

    atlas_guid TEXT NOT NULL,

    classification_name TEXT NOT NULL,
    classification_attributes JSONB,

    applied_by VARCHAR(50) NOT NULL,
    department VARCHAR(100) NOT NULL,
    business_unit VARCHAR(100) NOT NULL,

    applied_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- ✅ ICI, JUSTE APRÈS
CREATE UNIQUE INDEX one_active_classification
ON entity_classifications (entity_type, entity_id)
WHERE is_active = TRUE;
