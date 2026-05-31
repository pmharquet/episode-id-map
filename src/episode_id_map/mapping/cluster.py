"""Résolution d'œuvre (niveau cluster) : un id source → tous les id sources.

Chaîne : MAL → AniDB (Jikan /external) → SIMKL (search/id puis anime) → ids complets.
"""

from __future__ import annotations

import structlog

from ..config import Settings
from ..models import Cluster
from ..sources.jikan import JikanClient
from ..sources.simkl import SimklClient
from .align import aid_from_external

log = structlog.get_logger()


def resolve_cluster(mal_id: int, *, settings: Settings) -> Cluster:
    with JikanClient(settings) as jikan:
        external = jikan.get_external(mal_id)
    aid = aid_from_external(external)

    with SimklClient(settings) as simkl:
        hits = simkl.search_id(anidb=aid) if aid else simkl.search_id(mal=mal_id)
        if not hits:
            raise RuntimeError(f"SIMKL ne connaît pas mal={mal_id} / anidb={aid}")
        simkl_id = int(hits[0]["ids"]["simkl"])
        anime = simkl.get_anime(simkl_id)

    ids = anime.get("ids", {})
    cluster = Cluster(
        mal_id=mal_id,
        aid=aid,
        simkl_id=simkl_id,
        tmdb_id=_int(ids.get("tmdb")),
        tvdb_id=_int(ids.get("tvdb")),
        work_type="movie" if anime.get("anime_type") == "movie" else "tv",
        mal_ids=[mal_id],
    )
    log.info("cluster.resolved", **vars(cluster))
    return cluster


def _int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
