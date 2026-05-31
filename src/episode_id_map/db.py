"""Accès PostgreSQL : connexion, lookup de l'`episode_absolute`, upsert idempotent."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Json

from .config import Settings
from .models import Row


def connect(settings: Settings) -> psycopg.Connection:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL manquant dans .env")
    return psycopg.connect(settings.database_url)


def fetch_episode_absolute(
    cur: psycopg.Cursor,
    source: str,
    id_series: str | None,
    id_season: str | None,
    id_episode: str | None,
) -> str | None:
    """episode_absolute d'une ligne existante (clé unique), ou None."""
    cur.execute(
        """
        SELECT episode_absolute FROM episode_id_map
        WHERE source = %s
          AND id_series  IS NOT DISTINCT FROM %s
          AND id_season  IS NOT DISTINCT FROM %s
          AND id_episode IS NOT DISTINCT FROM %s
        """,
        (source, id_series, id_season, id_episode),
    )
    row = cur.fetchone()
    return row[0] if row else None


def upsert_row(cur: psycopg.Cursor, row: Row) -> None:
    """Insère la ligne ; si la clé unique existe déjà, ne met à jour QUE `extra`
    (on ne réécrit jamais `uuid` ni `episode_absolute` → stabilité)."""
    cur.execute(
        """
        INSERT INTO episode_id_map
            (uuid, episode_absolute, source, id_franchise,
             id_series, id_season, id_episode, extra)
        VALUES (%s, %s, %s, NULL, %s, %s, %s, %s)
        ON CONFLICT (source, id_series, id_season, id_episode)
        DO UPDATE SET extra = EXCLUDED.extra
        """,
        (
            row.uuid,
            row.episode_absolute,
            row.source,
            row.id_series,
            row.id_season,
            row.id_episode,
            Json(row.extra) if row.extra is not None else None,
        ),
    )
