\c pfe_db;

CREATE TABLE IF NOT EXISTS dataset_signatures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    structure_hash TEXT NOT NULL,
    signature JSONB NOT NULL,
    columns_count INT,
    rows_count BIGINT,
    algo_version TEXT DEFAULT 'v1',
    created_at TIMESTAMP DEFAULT NOW()
);
