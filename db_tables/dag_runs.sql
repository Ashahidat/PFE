\c pfe_db;

CREATE TABLE IF NOT EXISTS dag_runs (
    id UUID PRIMARY KEY,
    dataset_id UUID REFERENCES datasets(id) ON DELETE CASCADE,
    dag_run_id TEXT NOT NULL,
    rules JSONB,
    status TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
