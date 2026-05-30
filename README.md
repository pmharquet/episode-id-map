# episode_id_map

Service de mapping des identifiants d'épisodes d'anime entre **5 sources**
(MAL · SIMKL · TMDB · TVDB · AniDB), ancrés sur un unique `episode_absolute`
(UUIDv4 persisté). Finalité : alimenter un bot Discord (n8n + LLM sur Supabase)
qui annonce les sorties traduites, sans doublon.

- **Documentation des API** : [`docs/apis/`](./docs/apis/) (livrable ÉTAPE 1).
- **Schéma de la table** : [`db/init/001_schema.sql`](./db/init/001_schema.sql) (figé).

## Socle (ÉTAPE 2)

Stack : Python 3.11+ (`httpx`, `tenacity`, `typer`, `structlog`, `psycopg`) +
PostgreSQL 15 (cible Supabase), le tout en Docker. Le code d'ingestion arrive à
l'ÉTAPE 3 — le projet Python est pour l'instant **vide** (seul un smoke test
vérifie connexion + présence de la table).

### Démarrer

```bash
cp .env.example .env   # puis remplir les clés API (les valeurs DB ont des défauts)
docker compose up --build
```

Au 1er lancement, Postgres exécute `db/init/001_schema.sql` puis le conteneur
`app` affiche `✅ connexion OK — table episode_id_map présente (0 lignes)`.

> ⚠ Le port `5432` est souvent déjà occupé sous Windows. En cas de conflit,
> définir `POSTGRES_PORT=5433` dans `.env`.

### Se connecter à la base

```bash
docker compose exec db psql -U episode_id_map -d episode_id_map
```

## Fetchers par source (ÉTAPE 3)

Un client par API dans `src/episode_id_map/sources/` (auth, pagination et rate-limit
propres à chaque source ; retry/backoff mutualisé sur `429`/`5xx`). Une CLI de test :

```bash
docker compose run --rm --no-deps app python -m episode_id_map.cli jikan 52991
docker compose run --rm --no-deps app python -m episode_id_map.cli tmdb  209867
docker compose run --rm --no-deps app python -m episode_id_map.cli simkl --anidb 17617
docker compose run --rm --no-deps app python -m episode_id_map.cli tvdb  424536
docker compose run --rm --no-deps app python -m episode_id_map.cli anidb 17617
```

| Source | Auth | Pagination | Débit appliqué |
|---|---|---|---|
| Jikan (MAL) | aucune | `pagination.has_next_page` | 1 req/s (burst 3) — 60/min |
| TMDB | `api_key` (query) | par saison (pas de pages) | 15 req/s |
| SIMKL | header `simkl-api-key` | aucune | 4 req/s |
| TVDB | `POST /login` → Bearer | `?page=N` + `links.next` | 8 req/s |
| AniDB | client+clientver | aucune (1 appel/anime) | **0,5 req/s + cache disque** |

> ⚠ **AniDB** a une politique de ban agressive : le cache (`cache/anidb/`) est
> **obligatoire** et sert toute requête déjà vue (TTL 7 j). Ne pas forcer `--force` en
> boucle.

## Tests

Tests unitaires (réseau **mocké** via `respx` — aucun appel réel) :

```bash
docker compose run --rm --no-deps app sh -c "pip install -q pytest respx && pytest"
```

Couverture : token-bucket (`ratelimit`), retry/backoff du client de base (429/5xx),
chargement de la config, et chaque fetcher (pagination, auth, parsing AniDB + cache + ban).
