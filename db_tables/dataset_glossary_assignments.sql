-- ======================================================
--  Table DATASET_GLOSSARY_ASSIGNMENTS
-- ======================================================
CREATE TABLE IF NOT EXISTS dataset_glossary_assignments (
    id SERIAL PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    glossary_term_id INTEGER NOT NULL REFERENCES glossary_terms(id) ON DELETE CASCADE,
    column_name VARCHAR(150),
    created_by VARCHAR(50) REFERENCES users(employee_id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(dataset_id, glossary_term_id, column_name)
);

GRANT SELECT, INSERT, UPDATE, DELETE ON dataset_glossary_assignments TO pfe_user;
GRANT USAGE, SELECT ON SEQUENCE dataset_glossary_assignments_id_seq TO pfe_user;
