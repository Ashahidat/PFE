CREATE TABLE dataset_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES datasets(id),
    version_number INT NOT NULL,
    atlas_guid TEXT NOT NULL,
    parent_version_id UUID REFERENCES dataset_versions(id),
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(50) REFERENCES users(employee_id),
    change_comment TEXT,
    source_file TEXT, -- fichier source original
    UNIQUE(dataset_id, version_number)
);