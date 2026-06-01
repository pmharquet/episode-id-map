"""Orchestrateur d'ingestion (ÉTAPE 4) : resolve → fetch → align → assign → upsert.

L'ingestion se fait TOUJOURS par cluster complet (re-fetch des 5 sources) pour que
l'alignement puisse s'ancrer sur ce qui est déjà en base (cf. plan, choix « sans table »).
"""

from __future__ import annotations

import uuid as uuidlib
from collections import Counter

import httpx
import structlog

from . import db
from .config import Settings
from .mapping.align import align_episodes, detect_tvdb_season_type
from .mapping.anchor import assign_absolute
from .mapping.cluster import resolve_cluster
from .models import Cluster, Fetched, Row
from .sources.anidb import AniDBBanned, AniDBClient, AniDBError
from .sources.jikan import JikanClient
from .sources.simkl import SimklClient
from .sources.tmdb import TMDBClient
from .sources.tvdb import TVDBClient

log = structlog.get_logger()


def fetch_all(cluster: Cluster, *, settings: Settings) -> Fetched:
    f = Fetched()

    if cluster.aid:
        try:
            with AniDBClient(settings) as anidb:
                f.anidb = anidb.regular_episodes(anidb.get_anime(cluster.aid))
        except (AniDBBanned, AniDBError) as exc:
            log.warning("anidb.skip", aid=cluster.aid, reason=str(exc))

    if cluster.mal_id:
        with JikanClient(settings) as jikan:
            f.mal = list(jikan.iter_episodes(cluster.mal_id))

    if cluster.simkl_id:
        with SimklClient(settings) as simkl:
            f.simkl = simkl.get_episodes(cluster.simkl_id)

    if cluster.tvdb_id and cluster.work_type != "movie":
        # L'ordering TVDB utilisé par SIMKL peut être "official" (S1,S2…) ou "absolute"
        # (tous les épisodes en S0Exx). On détecte depuis le mapping SIMKL pour que les
        # coordonnées (saison, épisode) soient cohérentes entre les deux sources.
        # Filet de sécurité 404 : SIMKL peut renvoyer un tvdb_id de type "movie"
        # même pour work_type="tv" (données SIMKL imprécises ou ID partagé).
        try:
            tvdb_type = detect_tvdb_season_type(f.simkl)
            f.tvdb_season_type = tvdb_type
            log.info("tvdb.season_type", season_type=tvdb_type)
            with TVDBClient(settings) as tvdb:
                f.tvdb = list(tvdb.iter_episodes(cluster.tvdb_id, season_type=tvdb_type))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                log.warning("tvdb.skip_not_series", tvdb_id=cluster.tvdb_id,
                            work_type=cluster.work_type)
            else:
                raise

    if cluster.tmdb_id and cluster.work_type != "movie":
        # Filet de sécurité 404 : l'ID TMDB fourni par SIMKL peut pointer sur un
        # movie TMDB (namespace distinct du TV) même si work_type="tv".
        try:
            with TMDBClient(settings) as tmdb:
                episodes = list(tmdb.iter_episodes(cluster.tmdb_id))

                # Stratégie external_ids :
                #   ≤ 200 eps  → appel pour TOUS les épisodes (fiable, coût acceptable).
                #                Nécessaire car TMDB peut avoir des dates décalées vs AniDB
                #                pour le même épisode (ex. double-diffusion = 2 eps AniDB,
                #                1 seul TMDB) : le pont airdate seul lierait au mauvais ep.
                #   > 200 eps  → appel sélectif : uniquement dates absentes/non-uniques dans
                #                AniDB ou dupliquées côté TMDB (évite 1000+ appels sur OP).
                _EXT_THRESHOLD = 200
                if len(episodes) <= _EXT_THRESHOLD:
                    for ep in episodes:
                        try:
                            ext = tmdb.get_episode_external_ids(
                                cluster.tmdb_id, ep["season_number"], ep["episode_number"]
                            )
                            ep["tvdb_id"] = ext.get("tvdb_id")
                        except Exception:  # noqa: BLE001
                            ep["tvdb_id"] = None
                    log.info("tmdb.ext_ids.full", episodes=len(episodes))
                else:
                    anidb_date_count: Counter[str] = Counter(
                        e["airdate"] for e in f.anidb if e.get("airdate")
                    )
                    tmdb_date_count: Counter[str] = Counter(
                        (ep.get("air_date") or "")[:10]
                        for ep in episodes if (ep.get("air_date") or "")[:10]
                    )
                    ext_ids_called = 0
                    for ep in episodes:
                        air = (ep.get("air_date") or "")[:10]
                        needs = (
                            not air
                            or anidb_date_count.get(air, 0) != 1
                            or tmdb_date_count.get(air, 0) > 1
                        )
                        if needs:
                            try:
                                ext = tmdb.get_episode_external_ids(
                                    cluster.tmdb_id, ep["season_number"], ep["episode_number"]
                                )
                                ep["tvdb_id"] = ext.get("tvdb_id")
                                ext_ids_called += 1
                            except Exception:  # noqa: BLE001
                                ep["tvdb_id"] = None
                    log.info("tmdb.ext_ids.selective", calls=ext_ids_called, episodes=len(episodes))
                f.tmdb = episodes
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                log.warning("tmdb.skip_not_series", tmdb_id=cluster.tmdb_id,
                            work_type=cluster.work_type)
            else:
                raise

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

    stats = {"groups": 0, "skipped": 0, "rows": 0}
    with db.connect(settings) as conn:
        with conn.cursor() as cur:
            for group in groups:
                # Ne mapper que les épisodes présents sur MAL : on part d'un mal_id,
                # donc seul MAL définit le périmètre. Les épisodes sans contrepartie MAL
                # (futurs épisodes pas encore sortis, arcs d'un autre MAL, specials…)
                # seront écrits lors de l'ingest du MAL approprié.
                if not any(v.source == "MAL" for v in group):
                    stats["skipped"] += 1
                    continue
                stats["groups"] += 1
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
