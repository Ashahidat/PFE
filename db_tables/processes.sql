CREATE TABLE processes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atlas_process_guid TEXT UNIQUE NOT NULL,
    process_name TEXT NOT NULL,
    operation_type TEXT NOT NULL, -- 'REUPLOAD', 'TRANSFORMATION', 'FILTER', etc.
    input_dataset_version_id UUID REFERENCES dataset_versions(id),
    output_dataset_version_id UUID REFERENCES dataset_versions(id) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(50) REFERENCES users(employee_id),
    execution_time_ms INT,
    status TEXT DEFAULT 'SUCCESS',
    metadata JSONB -- pour stocker paramètres supplémentaires
);