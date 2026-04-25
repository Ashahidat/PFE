-- ======================================================
--  Table USER_DEPARTMENT_SCOPES (délégation admin_glossaire)
-- ======================================================
CREATE TABLE IF NOT EXISTS user_department_scopes (
    id SERIAL PRIMARY KEY,
    employee_id VARCHAR(50) NOT NULL REFERENCES users(employee_id) ON DELETE CASCADE,
    department_code VARCHAR(100) NOT NULL REFERENCES departments(code) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_user_dept_scope UNIQUE (employee_id, department_code)
);

GRANT SELECT, INSERT, UPDATE, DELETE ON user_department_scopes TO pfe_user;
GRANT USAGE, SELECT ON SEQUENCE user_department_scopes_id_seq TO pfe_user;
