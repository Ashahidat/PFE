-- ======================================================
--  Table DEPARTMENTS (référentiel dynamique)
-- ======================================================
CREATE TABLE IF NOT EXISTS departments (
    code VARCHAR(100) PRIMARY KEY,
    label VARCHAR(200) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON departments TO pfe_user;
