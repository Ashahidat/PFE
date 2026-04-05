-- ======================================================
--  Table GLOSSARY_CATEGORIES
-- ======================================================
CREATE TABLE IF NOT EXISTS glossary_categories (
    id SERIAL PRIMARY KEY,
    glossary_id INTEGER NOT NULL REFERENCES glossaries(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    qualified_name VARCHAR(200) UNIQUE NOT NULL,
    description TEXT,
    atlas_guid VARCHAR(100),
    created_by VARCHAR(50) REFERENCES users(employee_id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON glossary_categories TO pfe_user;
GRANT USAGE, SELECT ON SEQUENCE glossary_categories_id_seq TO pfe_user;
