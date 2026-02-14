-- Crée la table
CREATE TABLE IF NOT EXISTS column_lineage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    logical_column_id TEXT NOT NULL,
    column_name TEXT NOT NULL,
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id),
    parent_column_id UUID REFERENCES column_lineage(id),
    data_type TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Crée l'index après la table
CREATE INDEX IF NOT EXISTS idx_logical_id ON column_lineage(logical_column_id);
