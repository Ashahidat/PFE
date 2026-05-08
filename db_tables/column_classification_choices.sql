-- Column classification choices saved during "describe" (pre-push)
-- Missing row means "none".

CREATE TABLE IF NOT EXISTS column_classification_choices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    column_name VARCHAR(255) NOT NULL,
    classification_name TEXT NOT NULL CHECK (classification_name IN ('PII', 'SENSITIVE')),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    updated_by TEXT,
    UNIQUE(dataset_version_id, column_name)
);

