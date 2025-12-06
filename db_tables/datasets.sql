\c pfe_db;

-- ======================================================
--  TABLE datasets (version renforcée)
-- ======================================================
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    hash TEXT NOT NULL,
    columns_list TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),       
    owner_employee_id VARCHAR(50) DEFAULT NULL,
    atlas_guid TEXT DEFAULT NULL  
);
