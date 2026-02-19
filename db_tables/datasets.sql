CREATE TABLE datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    hash TEXT NOT NULL,
    columns_list TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    owner_employee_id VARCHAR(50),
    atlas_guid TEXT,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL
);

-- Index pour les recherches fréquentes
CREATE INDEX idx_datasets_project ON datasets(project_id);
CREATE INDEX idx_projects_owner ON projects(owner_employee_id);