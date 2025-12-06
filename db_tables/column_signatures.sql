\c pfe_db;

CREATE TABLE IF NOT EXISTS column_signatures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_signature_id UUID NOT NULL REFERENCES dataset_signatures(id) ON DELETE CASCADE,
    column_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    mean DOUBLE PRECISION,
    std DOUBLE PRECISION,
    distinct_count BIGINT,
    sample_hash TEXT
);
