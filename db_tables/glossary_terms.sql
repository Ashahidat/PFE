-- ======================================================
--  Table GLOSSARY_TERMS
-- ======================================================
CREATE TABLE IF NOT EXISTS glossary_terms (
    id SERIAL PRIMARY KEY,
    glossary_id INTEGER REFERENCES glossaries(id) ON DELETE CASCADE NOT NULL,
    category_id INTEGER REFERENCES glossary_categories(id) ON DELETE SET NULL,
    term VARCHAR(100) NOT NULL,
    description TEXT,
    atlas_guid VARCHAR(100),
    created_by VARCHAR(50) REFERENCES users(employee_id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Donner les droits à pfe_user
GRANT SELECT, INSERT, UPDATE, DELETE ON glossary_terms TO pfe_user;
GRANT USAGE, SELECT ON SEQUENCE glossary_terms_id_seq TO pfe_user;
