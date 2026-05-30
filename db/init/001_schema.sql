-- ─────────────────────────────────────────────────────────────────────────────
-- episode_id_map — schéma FIGÉ (ÉTAPE 2)
-- Cible : Supabase / PostgreSQL 15+.  Dev local : Postgres en Docker.
-- Exécuté automatiquement au 1er démarrage du conteneur (docker-entrypoint-initdb.d).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS episode_id_map (
    uuid             CHAR(36) NOT NULL,            -- UUIDv4 persisté (PK)
    episode_absolute CHAR(36) NOT NULL,            -- UUIDv4 persisté : SEUL ancrage canonique
    source           TEXT     NOT NULL,            -- "MAL" | "TMDB" | "SIMKL" | "TVDB" | "ANIDB"
    id_franchise     TEXT,                         -- toujours NULL (réservé)
    id_series        TEXT,
    id_season        TEXT,
    id_episode       TEXT,
    extra            JSON,                          -- qualificatif minimal utile au mapping (cf. docs/apis)
    CONSTRAINT episode_id_map_pkey PRIMARY KEY (uuid)
);

-- Index (conformes à la DBML fournie — tous NON uniques).
CREATE INDEX IF NOT EXISTS idx_eim_episode_absolute             ON episode_id_map (episode_absolute);
CREATE INDEX IF NOT EXISTS idx_eim_source_franchise             ON episode_id_map (source, id_franchise);
CREATE INDEX IF NOT EXISTS idx_eim_source_series                ON episode_id_map (source, id_series);
CREATE INDEX IF NOT EXISTS idx_eim_source_season                ON episode_id_map (source, id_season);
CREATE INDEX IF NOT EXISTS idx_eim_source_episode               ON episode_id_map (source, id_episode);
CREATE INDEX IF NOT EXISTS idx_eim_source_series_episode        ON episode_id_map (source, id_series, id_episode);
CREATE INDEX IF NOT EXISTS idx_eim_source_season_episode        ON episode_id_map (source, id_season, id_episode);
CREATE INDEX IF NOT EXISTS idx_eim_source_series_season_episode ON episode_id_map (source, id_series, id_season, id_episode);

-- Idempotence : contrainte UNIQUE NULLS NOT DISTINCT (PG15+) sur la clé naturelle.
ALTER TABLE episode_id_map
    ADD CONSTRAINT uq_eim_source_series_season_episode
    UNIQUE NULLS NOT DISTINCT (source, id_series, id_season, id_episode);
