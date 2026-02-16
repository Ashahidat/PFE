\c pfe_db;

CREATE TABLE IF NOT EXISTS data_quality_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    dag_run_uuid UUID NOT NULL REFERENCES dag_runs(id) ON DELETE CASCADE,
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,

    validator_name TEXT NOT NULL,
    check_type TEXT NOT NULL,
    column_name TEXT,

    status TEXT NOT NULL,
    error_count INT,
    ratio DOUBLE PRECISION,
    alert BOOLEAN,
    examples JSONB,

    created_at TIMESTAMP DEFAULT NOW()
);
