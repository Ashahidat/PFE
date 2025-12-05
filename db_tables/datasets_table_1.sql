\c pfe_db;

-- ======================================================
--  TABLE datasets (version ultra minimale pour upload)
-- ======================================================
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    hash TEXT NOT NULL,
    columns_list TEXT[]
);
