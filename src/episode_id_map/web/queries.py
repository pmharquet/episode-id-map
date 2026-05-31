"""Requêtes de lecture pour l'interface web (lecture seule, pas de mutations)."""

from __future__ import annotations

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
    full_groups: int  # groupes ayant les 5 sources


@dataclass
class EpisodeGroup:
    episode_absolute: str
    source_count: int
    anidb_ep: str | None
    mal_ep: str | None
    simkl_ep: str | None
    tvdb_ep: str | None
    tmdb_ep: str | None


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
    """Liste des anime ingérés, identifiés par leur MAL id_series."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                m.id_series AS mal_series,
                COUNT(DISTINCT m.episode_absolute) AS total_episodes,
                COUNT(DISTINCT CASE WHEN src.n = 5 THEN m.episode_absolute END) AS full_groups
            FROM episode_id_map m
            JOIN (
                SELECT episode_absolute, COUNT(DISTINCT source) AS n
                FROM episode_id_map
                GROUP BY episode_absolute
            ) src USING (episode_absolute)
            WHERE m.source = 'MAL'
            GROUP BY m.id_series
            ORDER BY m.id_series
            """
        )
        return [SeriesSummary(*row) for row in cur.fetchall()]


def get_episodes(conn, mal_series: str = "") -> list[EpisodeGroup]:
    """Tableau pivoté : une ligne par episode_absolute, colonnes = sources."""
    where = ""
    params: list = []
    if mal_series:
        where = """
            WHERE episode_absolute IN (
                SELECT episode_absolute FROM episode_id_map
                WHERE source = 'MAL' AND id_series = %s
            )
        """
        params = [mal_series]

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                episode_absolute,
                COUNT(DISTINCT source)                                          AS source_count,
                MAX(CASE WHEN source = 'ANIDB' THEN id_episode END)            AS anidb_ep,
                MAX(CASE WHEN source = 'MAL'   THEN id_episode END)            AS mal_ep,
                MAX(CASE WHEN source = 'SIMKL' THEN id_episode END)            AS simkl_ep,
                MAX(CASE WHEN source = 'TVDB'
                    THEN 'S' || COALESCE(id_season,'?') || 'E' || id_episode END) AS tvdb_ep,
                MAX(CASE WHEN source = 'TMDB'
                    THEN 'S' || COALESCE(id_season,'?') || 'E' || id_episode END) AS tmdb_ep,
                MAX(CASE WHEN source = 'ANIDB'
                         AND id_episode ~ '^[0-9]+$'
                    THEN id_episode::int END)                                   AS sort_key
            FROM episode_id_map
            {where}
            GROUP BY episode_absolute
            ORDER BY sort_key NULLS LAST, episode_absolute
            """,
            params,
        )
        rows = cur.fetchall()

    return [
        EpisodeGroup(
            episode_absolute=r[0],
            source_count=r[1],
            anidb_ep=r[2],
            mal_ep=r[3],
            simkl_ep=r[4],
            tvdb_ep=r[5],
            tmdb_ep=r[6],
        )
        for r in rows
    ]
