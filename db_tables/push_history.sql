CREATE TABLE push_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES datasets(id),
    pushed_at TIMESTAMP DEFAULT NOW(),
    pushed_by VARCHAR(50) REFERENCES users(employee_id),
    status TEXT, -- 'SUCCESS', 'FAILED'
    error_message TEXT,
    execution_time_ms INT,
    columns_count INT,
    rows_count BIGINT,
    parent_found BOOLEAN, -- si un parent a été trouvé
    similarity_score FLOAT, -- score de similarité avec le parent
    propagated_columns_count INT -- nb de colonnes avec logicalId propagé
);