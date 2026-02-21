-- ======================================================
--  TABLE USERS (version complète avec rôles)
-- ======================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    employee_id VARCHAR(50) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL,
    password_hash TEXT NOT NULL,
    department VARCHAR(100) NOT NULL,
    business_unit VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'DATA_OWNER',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Index pour les recherches fréquentes
CREATE INDEX idx_users_employee_id ON users(employee_id);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_department ON users(department);

-- Donner les droits
GRANT ALL PRIVILEGES ON TABLE users TO pfe_user;
GRANT USAGE, SELECT ON SEQUENCE users_id_seq TO pfe_user;