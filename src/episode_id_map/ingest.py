"""Orchestrateur d'ingestion (ÉTAPE 4) : resolve → fetch → align → assign → upsert.

L'ingestion se fait TOUJOURS par cluster complet (re-fetch des 5 sources) pour que
l'alignement puisse s'ancrer sur ce qui est déjà en base (cf. plan, choix « sans table »).
"""

from __future__ import annotations

import uuid as uuidlib

import structlog

from . import db
from .config import Settings
from .mapping.align import align_episodes
from .mapping.anchor import assign_absolute
from .mapping.cluster import resolve_cluster
from .models import Cluster, Fetched, Row
from .sources.anidb import AniDBClient
from .sources.jikan import JikanClient
from .sources.simkl import SimklClient
from .sources.tmdb import TMDBClient
from .sources.tvdb import TVDBClient

log = structlog.get_logger()


def fetch_all(cluster: Cluster, *, settings: Settings) -> Fetched:
    f = Fetched()

    if cluster.aid:
        with AniDBClient(settings) as anidb:
            f.anidb = anidb.regular_episodes(anidb.get_anime(cluster.aid))

    if cluster.mal_id:
        with JikanClient(settings) as jikan:
            f.mal = list(jikan.iter_episodes(cluster.mal_id))

    if cluster.simkl_id:
        with SimklClient(settings) as simkl:
            f.simkl = simkl.get_episodes(cluster.simkl_id)

    if cluster.tvdb_id:
        with TVDBClient(settings) as tvdb:
            f.tvdb = list(tvdb.iter_episodes(cluster.tvdb_id))

    if cluster.tmdb_id:
        with TMDBClient(settings) as tmdb:
            episodes = list(tmdb.iter_episodes(cluster.tmdb_id))
            for ep in episodes:
                # Pont fort TMDB→TVDB : id épisode TVDB via external_ids (1 appel/ép.).
                try:
                    ext = tmdb.get_episode_external_ids(
                        cluster.tmdb_id, ep["season_number"], ep["episode_number"]
                    )
                    ep["tvdb_id"] = ext.get("tvdb_id")
                except Exception:  # noqa: BLE001 — épisode sans external_ids → fallback airdate
                    ep["tvdb_id"] = None
            f.tmdb = episodes

    log.info(
        "fetch.done",
        anidb=len(f.anidb), mal=len(f.mal), simkl=len(f.simkl),
        tvdb=len(f.tvdb), tmdb=len(f.tmdb),
    )
    return f


def ingest(mal_id: int, *, settings: Settings) -> dict[str, int]:
    cluster = resolve_cluster(mal_id, settings=settings)
    fetched = fetch_all(cluster, settings=settings)
    groups = align_episodes(cluster, fetched)

    stats = {"groups": len(groups), "rows": 0}
    with db.connect(settings) as conn:
        with conn.cursor() as cur:
            for group in groups:
                episode_absolute = assign_absolute(cur, group)
                for view in group:
                    db.upsert_row(
                        cur,
                        Row(
                            uuid=str(uuidlib.uuid4()),
                            episode_absolute=episode_absolute,
                            source=view.source,
                            id_series=view.id_series,
                            id_season=view.id_season,
                            id_episode=view.id_episode,
                            extra=view.extra,
                        ),
                    )
                    stats["rows"] += 1
        conn.commit()

    log.info("ingest.done", mal_id=mal_id, **stats)
    return stats
