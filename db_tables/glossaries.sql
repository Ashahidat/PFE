-- ======================================================
--  Table GLOSSARIES
-- ======================================================
CREATE TABLE IF NOT EXISTS glossaries (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    qualified_name VARCHAR(150) UNIQUE NOT NULL,
    description TEXT,
    department VARCHAR(50),
    created_by VARCHAR(50) REFERENCES users(employee_id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON glossaries TO pfe_user;
GRANT USAGE, SELECT ON SEQUENCE glossaries_id_seq TO pfe_user;
