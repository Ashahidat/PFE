\c pfe_db;

-- ======================================================
--  TABLE datasets
-- ======================================================
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY,
    qualified_name TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    version_comment TEXT,
    signature JSONB,
    columns_count INT,
    columns_list TEXT[],
    file_path TEXT,
    parent_qualified_name TEXT,
    owner_employee_id VARCHAR(50) NOT NULL,
    classification TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (owner_employee_id)
        REFERENCES users(employee_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- ======================================================
--  TABLE columns
-- ======================================================
CREATE TABLE IF NOT EXISTS columns (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    data_type TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ======================================================
--  TABLE dataset_versioning
-- ======================================================
CREATE TABLE IF NOT EXISTS dataset_versioning (
    previous_id UUID REFERENCES datasets(id) ON DELETE CASCADE,
    next_id UUID REFERENCES datasets(id) ON DELETE CASCADE,
    PRIMARY KEY (previous_id, next_id)
);
