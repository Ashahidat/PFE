-- ======================================================
--  Table GLOSSARY_TERMS
-- ======================================================
-- Exécuter cette commande dans PostgreSQL
\c pfe_db;

CREATE TABLE IF NOT EXISTS glossary_terms (
    id SERIAL PRIMARY KEY,
    glossary_id INTEGER REFERENCES glossaries(id) ON DELETE CASCADE NOT NULL,
    category_id INTEGER REFERENCES glossary_categories(id) ON DELETE SET NULL,
    term VARCHAR(100) NOT NULL,
    qualified_name VARCHAR(200),
    description TEXT,
    atlas_guid VARCHAR(100),
    created_by VARCHAR(50) REFERENCES users(employee_id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Ajout colonne qualified_name si la table existait déjà
ALTER TABLE glossary_terms
    ADD COLUMN IF NOT EXISTS qualified_name VARCHAR(200);

-- Backfill (si besoin) : garder l'ancien pattern pour les termes déjà poussés vers Atlas
UPDATE glossary_terms gt
SET qualified_name = (
    regexp_replace(
        regexp_replace(lower(gt.term), '[^a-z0-9]+', '_', 'g'),
        '_+', '_', 'g'
    ) || '@' || g.qualified_name
)
FROM glossaries g
WHERE gt.glossary_id = g.id
  AND gt.qualified_name IS NULL
  AND gt.atlas_guid IS NOT NULL;

-- Backfill (si besoin) : pour les termes non poussés, suffixer avec l'id pour éviter les collisions de slug
UPDATE glossary_terms gt
SET qualified_name = (
    regexp_replace(
        regexp_replace(lower(gt.term), '[^a-z0-9]+', '_', 'g'),
        '_+', '_', 'g'
    ) || '_' || gt.id::text || '@' || g.qualified_name
)
FROM glossaries g
WHERE gt.glossary_id = g.id
  AND gt.qualified_name IS NULL
  AND gt.atlas_guid IS NULL;

-- Donner les droits à pfe_user
GRANT SELECT, INSERT, UPDATE, DELETE ON glossary_terms TO pfe_user;
GRANT USAGE, SELECT ON SEQUENCE glossary_terms_id_seq TO pfe_user;
