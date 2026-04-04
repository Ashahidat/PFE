SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'pfe_db'
  AND pid <> pg_backend_pid();

-- Supprimer la base si elle existe
DROP DATABASE IF EXISTS pfe_db;

-- Créer la base
CREATE DATABASE pfe_db;

-- Donner les droits sur la base à pfe_user
GRANT ALL PRIVILEGES ON DATABASE pfe_db TO pfe_user;

-- Se connecter à la base
\c pfe_db;

-- Donner les droits sur le schéma public
GRANT ALL ON SCHEMA public TO pfe_user;

-- Définir les privilèges par défaut pour toutes les futures tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pfe_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO pfe_user;

-- ======================================================
--  Création de la table USERS
-- ======================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    employee_id VARCHAR(50) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL,
    password_hash TEXT NOT NULL,
    department VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'DATA_OWNER',
    is_protected BOOLEAN DEFAULT FALSE     -- ← NOUVEAU
);

-- Donner tous les droits à pfe_user sur la table users
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO pfe_user;
GRANT USAGE, SELECT ON SEQUENCE users_id_seq TO pfe_user;