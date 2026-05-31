# episode-id-map

Mapping of anime episode identifiers across **5 databases** into a single stable UUID (`episode_absolute`) shared by all source representations of the same episode.

---

## Sources

| Source | ID used | Auth | Rate applied |
|---|---|---|---|
| **MAL** (via Jikan) | `mal_id` | none | 1 req/s |
| **AniDB** | `aid` | `client` + `clientver` | 0.5 req/s · mandatory disk cache |
| **SIMKL** | `simkl_id` | `simkl-api-key` header | 4 req/s |
| **TVDB** | `tvdb_id` | `POST /login` → Bearer JWT | 8 req/s |
| **TMDB** | `tmdb_id` | `api_key` query param | 4 req/s |

---

## How it works

Ingestion starts from a **MAL ID**:

1. **Resolve cluster** — chains MAL → AniDB (via Jikan) → SIMKL → TMDB/TVDB IDs.
2. **Fetch all 5 sources** and align episodes against AniDB's episode grid as the canonical reference.
3. **Assign `episode_absolute`** — a stable UUIDv4 shared across all source rows for the same real episode. Pre-existing rows anchor the UUID; conflicts are logged, never silently merged.
4. **Upsert idempotently** — re-running the same ingest is safe; UUIDs never change.

Only episodes present on MAL are written. TVDB/TMDB episodes with no MAL counterpart are skipped.

---

## Stack

```
Python 3.11+   httpx · tenacity · typer · structlog · psycopg[binary]
PostgreSQL 15
Docker         postgres:15-alpine + python:3.11-slim
FastAPI + HTMX (web UI)
```

---

## Getting started

```bash
cp .env.example .env      # fill in API keys — DB defaults work out of the box
docker compose up --build
```

On first boot Postgres runs `db/init/001_schema.sql` automatically. The web UI starts on **http://localhost:8000**.

> **Windows** — port `5432` is often taken. Set `POSTGRES_PORT=5433` in `.env` if needed.

### Connect to the database

```bash
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB
```

---

## Ingest

```bash
docker compose run --rm app python -m episode_id_map.cli ingest 52991
# {"groups": 28, "skipped": 73, "rows": 140}
```

`groups` = episode groups written, `skipped` = episodes with no MAL counterpart, `rows` = total DB rows written.

---

## Web UI

```bash
docker compose up web   # → http://localhost:8000
```

- **Dashboard** — live stats, ingest form.
- **Comparison table** — pivoted view per anime; hover any ID to see the raw DB row; delete a single source row or an entire group.

---

## CLI (source inspection)

```bash
docker compose run --rm --no-deps app python -m episode_id_map.cli jikan 52991
docker compose run --rm --no-deps app python -m episode_id_map.cli tmdb  209867
docker compose run --rm --no-deps app python -m episode_id_map.cli simkl --anidb 17617
docker compose run --rm --no-deps app python -m episode_id_map.cli tvdb  424536
docker compose run --rm --no-deps app python -m episode_id_map.cli anidb 17617
```

---

## Schema (frozen)

```sql
CREATE TABLE episode_id_map (
    uuid             CHAR(36) NOT NULL,
    episode_absolute CHAR(36) NOT NULL,
    source           TEXT     NOT NULL,   -- ANIDB | MAL | SIMKL | TVDB | TMDB
    id_franchise     TEXT,
    id_series        TEXT,
    id_season        TEXT,
    id_episode       TEXT,
    extra            JSON,
    PRIMARY KEY (uuid),
    UNIQUE NULLS NOT DISTINCT (source, id_series, id_season, id_episode)
);
```

`episode_absolute` is the only cross-source key. It is assigned once and never rewritten on upsert.

---

## Tests

```bash
docker compose run --rm --no-deps app sh -c "pip install -q pytest respx && pytest"
```

38 unit tests, network fully mocked via `respx`.

---

## AniDB notice

AniDB enforces aggressive ban policies. The disk cache (`cache/anidb/`) is **mandatory** — every response is cached for 7 days. Do not use `--force` in a loop.

---

## Project layout

```
src/episode_id_map/
├── sources/      # one client per API (auth, pagination, rate-limit)
├── mapping/      # cluster resolution, episode alignment, UUID anchoring
├── web/          # FastAPI app + HTMX partials
├── templates/    # Jinja2 templates (Tailwind CSS)
├── db.py         # connect, fetch_episode_absolute, upsert_row
├── ingest.py     # orchestrator: resolve → fetch → align → assign → upsert
└── cli.py        # typer commands

db/init/001_schema.sql   # frozen schema, auto-run on first Postgres boot
docs/apis/               # per-source API notes
```
