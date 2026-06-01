"""Requêtes de lecture (et mutation delete) pour l'interface web."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Stats:
    total_rows: int
    total_absolutes: int
    per_source: dict[str, int]


@dataclass
class SeriesSummary:
    mal_series: str
    total_episodes: int
    full_groups: int


@dataclass
class SourceRow:
    """Ligne brute de la DB pour une source donnée."""
    uuid: str
    source: str
    id_franchise: str | None
    id_series: str | None
    id_season: str | None
    id_episode: str | None
    extra: str | None      # JSON sérialisé en texte
    episode_absolute: str


@dataclass
class EpisodeGroup:
    episode_absolute: str
    source_count: int
    anidb_ep: str | None
    mal_ep: str | None
    simkl_ep: str | None
    tvdb_ep: str | None
    tmdb_ep: str | None
    # Lignes brutes par source (None si la source est absente du groupe)
    rows: dict[str, SourceRow] = field(default_factory=dict)


def get_stats(conn) -> Stats:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT episode_absolute) FROM episode_id_map")
        total_rows, total_abs = cur.fetchone()
        cur.execute(
            "SELECT source, COUNT(*) FROM episode_id_map GROUP BY source ORDER BY source"
        )
        per_source = {row[0]: row[1] for row in cur.fetchall()}
    return Stats(total_rows=total_rows, total_absolutes=total_abs, per_source=per_source)


def get_series_list(conn) -> list[SeriesSummary]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                m.id_series AS mal_series,
                COUNT(DISTINCT m.episode_absolute) AS total_episodes,
                COUNT(DISTINCT CASE WHEN src.n = 4 THEN m.episode_absolute END) AS full_groups
            FROM episode_id_map m
            JOIN (
                SELECT episode_absolute,
                       COUNT(DISTINCT CASE WHEN source != 'ANIDB' THEN source END) AS n
                FROM episode_id_map GROUP BY episode_absolute
            ) src USING (episode_absolute)
            WHERE m.source = 'MAL'
            GROUP BY m.id_series
            ORDER BY m.id_series::bigint
            """
        )
        return [SeriesSummary(*row) for row in cur.fetchall()]


def _build_group(r) -> EpisodeGroup:
    """Construit un EpisodeGroup depuis une ligne de résultat SQL."""
    episode_absolute = r[0]
    source_data: dict = r[8] or {}  # JSON de json_object_agg
    rows: dict[str, SourceRow] = {}
    for src, d in source_data.items():
        rows[src] = SourceRow(
            uuid=d["uuid"],
            source=src,
            id_franchise=d.get("id_franchise"),
            id_series=d.get("id_series"),
            id_season=d.get("id_season"),
            id_episode=d.get("id_episode"),
            extra=json.dumps(d["extra"], ensure_ascii=False) if d.get("extra") else None,
            episode_absolute=episode_absolute,
        )
    return EpisodeGroup(
        episode_absolute=episode_absolute,
        source_count=r[1],
        anidb_ep=r[2],
        mal_ep=r[3],
        simkl_ep=r[4],
        tvdb_ep=r[5],
        tmdb_ep=r[6],
        rows=rows,
    )


_PIVOT_SQL = """
    SELECT
        episode_absolute,
        COUNT(DISTINCT CASE WHEN source != 'ANIDB' THEN source END)        AS source_count,
        MAX(CASE WHEN source = 'ANIDB' THEN id_episode END)                AS anidb_ep,
        MAX(CASE WHEN source = 'MAL'   THEN id_episode END)                AS mal_ep,
        MAX(CASE WHEN source = 'SIMKL' THEN id_episode END)                AS simkl_ep,
        MAX(CASE WHEN source = 'TVDB'
            THEN 'S' || COALESCE(id_season,'?') || 'E' || id_episode END)  AS tvdb_ep,
        MAX(CASE WHEN source = 'TMDB'
            THEN 'S' || COALESCE(id_season,'?') || 'E' || id_episode END)  AS tmdb_ep,
        MAX(CASE WHEN source = 'ANIDB' AND id_episode ~ '^[0-9]+$'
            THEN id_episode::int END)                                       AS sort_key,
        json_object_agg(
            source,
            json_build_object(
                'uuid',         uuid,
                'id_franchise', id_franchise,
                'id_series',    id_series,
                'id_season',    id_season,
                'id_episode',   id_episode,
                'extra',        extra
            )
        )                                                                   AS source_data
    FROM episode_id_map
    {where}
    GROUP BY episode_absolute
    ORDER BY sort_key NULLS LAST, episode_absolute
"""


def get_episodes(conn, mal_series: str = "") -> list[EpisodeGroup]:
    where, params = "", []
    if mal_series:
        where = """
            WHERE episode_absolute IN (
                SELECT episode_absolute FROM episode_id_map
                WHERE source = 'MAL' AND id_series = %s
            )
        """
        params = [mal_series]
    with conn.cursor() as cur:
        cur.execute(_PIVOT_SQL.format(where=where), params)
        return [_build_group(r) for r in cur.fetchall()]


def get_group(conn, episode_absolute: str) -> EpisodeGroup | None:
    """Récupère un seul groupe (après delete) pour mettre à jour la <tr>."""
    with conn.cursor() as cur:
        cur.execute(
            _PIVOT_SQL.format(where="WHERE episode_absolute = %s"),
            [episode_absolute],
        )
        row = cur.fetchone()
    return _build_group(row) if row else None


def delete_row(conn, uuid: str) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM episode_id_map WHERE uuid = %s", (uuid,))
    conn.commit()


def delete_group(conn, episode_absolute: str) -> None:
    """Supprime toutes les lignes d'un groupe (tous les sources)."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM episode_id_map WHERE episode_absolute = %s",
            (episode_absolute,),
        )
    conn.commit()


def get_mapped_mal_ids(conn) -> set[int]:
    """Retourne les MAL id_series déjà présents en base."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT id_series FROM episode_id_map WHERE source = 'MAL'")
        rows = cur.fetchall()
    result: set[int] = set()
    for (val,) in rows:
        try:
            result.add(int(val))
        except (ValueError, TypeError):
            pass
    return result
