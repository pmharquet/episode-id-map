"""Alignement épisode-à-épisode (en mémoire, à partir des données live).

Ossature = grille AniDB (`epno type=1`). Chaque source est rattachée à un `epno`
par un pont fort, avec fallback `airdate` UNIQUE. Sans pont fiable → `epno=None`
→ l'épisode formera son propre groupe (nouvel `episode_absolute`).
"""

from __future__ import annotations

import re
from datetime import date

from ..models import Cluster, EpisodeView, Fetched

_AID_RE = re.compile(r"aid=(\d+)")
_ANIME_RE = re.compile(r"/anime/(\d+)")


def parse_aid_from_url(url: str) -> int | None:
    m = _AID_RE.search(url) or _ANIME_RE.search(url)
    return int(m.group(1)) if m else None


def aid_from_external(external: list[dict]) -> int | None:
    for entry in external:
        if entry.get("name") == "AniDB":
            aid = parse_aid_from_url(entry.get("url", ""))
            if aid:
                return aid
    return None


def detect_tvdb_season_type(simkl_episodes: list[dict]) -> str:
    """Renvoie 'absolute' si la majorité des épisodes réguliers SIMKL pointent vers
    la saison 0 de TVDB (ordering absolu), sinon 'official'.

    Certains anime (One Piece, Naruto, ...) utilisent l'ordering absolu TVDB où tous
    les épisodes sont en S0Exx ; d'autres (Frieren, ...) utilisent l'ordering officiel
    (S1, S2, ...). SIMKL indique lequel via le champ tvdb.season de chaque épisode.
    """
    regular = [
        e for e in simkl_episodes
        if e.get("type", "episode") == "episode" and e.get("tvdb")
    ]
    if not regular:
        return "official"
    season_0 = sum(1 for e in regular if e["tvdb"].get("season") == 0)
    return "absolute" if season_0 / len(regular) > 0.5 else "official"


def to_date(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _close(d1: date | None, d2: date | None) -> bool:
    """airdates compatibles : tolérance ±1 j (fuseaux), ou inconnue d'un côté."""
    if d1 is None or d2 is None:
        return True
    return abs((d1 - d2).days) <= 1


def _int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def align_episodes(cluster: Cluster, f: Fetched) -> list[list[EpisodeView]]:
    """Retourne des groupes de vues ; chaque groupe = un épisode réel."""
    # 1. Grille AniDB : epno -> airdate
    grid: dict[int, date | None] = {}
    anidb_views: list[EpisodeView] = []
    for ep in f.anidb:
        n = _int(ep.get("epno"))
        if n is None:
            continue
        ad = to_date(ep.get("airdate"))
        grid[n] = ad
        anidb_views.append(
            EpisodeView("ANIDB", _s(cluster.aid), None, str(n),
                        {"epno_type": 1}, epno=n, airdate=ad)
        )

    airdate_to_epnos: dict[date, list[int]] = {}
    for n, ad in grid.items():
        if ad:
            airdate_to_epnos.setdefault(ad, []).append(n)

    # 2. SIMKL : numérotation AniDB plate + mapping tvdb {season,episode}
    # id_episode = simkl_id de l'épisode (unique même entre réguliers et specials qui
    # partagent parfois le même numéro d'épisode) ; fallback sur episode number pour les
    # données de test sans ids block.
    se_to_epno: dict[tuple[int, int], int] = {}
    simkl_views: list[EpisodeView] = []
    for ep in f.simkl:
        n = _int(ep.get("episode"))
        if n is None:
            continue
        ep_type = ep.get("type", "episode")
        simkl_ep_id = ep.get("ids", {}).get("simkl_id") if ep.get("ids") else None
        id_ep = str(simkl_ep_id) if simkl_ep_id is not None else str(n)
        ad = to_date(ep.get("date"))
        tv = ep.get("tvdb") or {}
        s, e = _int(tv.get("season")), _int(tv.get("episode"))
        # Le mapping TVDB n'est fiable que pour les épisodes réguliers.
        if ep_type == "episode" and s is not None and e is not None:
            se_to_epno[(s, e)] = n
        # Seuls les épisodes réguliers suivent la numérotation AniDB.
        epno = n if ep_type == "episode" and n in grid and _close(ad, grid.get(n)) else None
        simkl_views.append(
            EpisodeView("SIMKL", _s(cluster.simkl_id), None, id_ep,
                        None, epno=epno, airdate=ad)
        )

    # 3. MAL : numéro d'épisode == epno AniDB (1:1)
    mal_views: list[EpisodeView] = []
    for ep in f.mal:
        n = _int(ep.get("mal_id"))
        if n is None:
            continue
        ad = to_date(ep.get("aired"))
        epno = n if n in grid and _close(ad, grid.get(n)) else None
        mal_views.append(
            EpisodeView("MAL", _s(cluster.mal_id), None, str(n),
                        None, epno=epno, airdate=ad)
        )

    # 4. TVDB : (saison, numéro) -> epno via le mapping SIMKL, fallback airdate unique.
    # Pour les grandes séries (One Piece…), SIMKL ne couvre que les premiers arcs ;
    # le fallback airdate prend le relais pour les autres épisodes.
    tvdbid_to_se: dict[str, tuple[int, int]] = {}
    tvdb_views: list[EpisodeView] = []
    tvdb_season_type = f.tvdb_season_type
    for ep in f.tvdb:
        s, num = _int(ep.get("seasonNumber")), _int(ep.get("number"))
        se = (s, num) if s is not None and num is not None else None
        if se is not None and ep.get("id") is not None:
            tvdbid_to_se[str(ep["id"])] = se
        ad = to_date(ep.get("aired"))
        epno = se_to_epno.get(se) if se is not None else None
        # Ordering absolu : `number` = numéro séquentiel global = epno AniDB.
        # Ce fallback est prioritaire sur l'airdate car TVDB et AniDB peuvent
        # avoir des dates décalées de plusieurs jours/semaines pour le même épisode
        # (ex. : one-piece ep 101 : AniDB=2002-02-17, TVDB=2002-03-17).
        if epno is None and tvdb_season_type == "absolute" and num is not None and num in grid:
            epno = num
        # Fallback airdate pour l'ordering officiel (ou si number hors grille).
        if epno is None and ad and len(airdate_to_epnos.get(ad, [])) == 1:
            epno = airdate_to_epnos[ad][0]
        tvdb_views.append(
            EpisodeView("TVDB", _s(cluster.tvdb_id),
                        _s(s), _s(num),
                        {"season_type": tvdb_season_type}, epno=epno, airdate=ad)
        )

    # 5. TMDB : tvdb_id (episode external_ids) -> TVDB (s,e) -> epno ; sinon airdate unique
    tmdb_views: list[EpisodeView] = []
    for ep in f.tmdb:
        s, num = _int(ep.get("season_number")), _int(ep.get("episode_number"))
        ad = to_date(ep.get("air_date"))
        epno = None
        tvid = ep.get("tvdb_id")
        if tvid is not None:
            se = tvdbid_to_se.get(str(tvid))
            if se is not None:
                epno = se_to_epno.get(se)
                # Ordering absolu : si se_to_epno échoue, le numéro d'épisode
                # dans le couple (saison, numéro) de TVDB est le numéro global.
                if epno is None and tvdb_season_type == "absolute" and se[1] in grid:
                    epno = se[1]
        if epno is None and ad and len(airdate_to_epnos.get(ad, [])) == 1:
            epno = airdate_to_epnos[ad][0]
        tmdb_views.append(
            EpisodeView("TMDB", _s(cluster.tmdb_id),
                        _s(s), _s(num),
                        {"type": cluster.work_type}, epno=epno, airdate=ad)
        )

    # 6. Groupage par epno ; les non-rattachés forment chacun leur groupe.
    groups: dict[int, list[EpisodeView]] = {}
    singles: list[EpisodeView] = []
    for view in anidb_views + mal_views + simkl_views + tvdb_views + tmdb_views:
        if view.epno is not None and view.epno in grid:
            groups.setdefault(view.epno, []).append(view)
        else:
            singles.append(view)

    # 7. Rattachement par numéro pour les singletons MAL (et SIMKL) :
    #    AniDB utilise les dates de diffusion japonaises, MAL/SIMKL parfois les dates
    #    internationales avec des écarts de plusieurs semaines (ex. : One Piece ep 156 :
    #    AniDB=2003-05-25, MAL=2003-06-08, diff=14 j → hors tolérance ±1 j).
    #    Si le numéro MAL/SIMKL correspond à un groupe AniDB existant, on l'y rattache
    #    car la numérotation est une preuve forte de correspondance.
    remaining_singles: list[EpisodeView] = []
    for view in singles:
        if view.source in ("MAL", "SIMKL") and view.id_episode:
            n = _int(view.id_episode)
            if n is not None and n in groups:
                groups[n].append(view)
                continue
        remaining_singles.append(view)

    return [groups[k] for k in sorted(groups)] + [[v] for v in remaining_singles]


def _s(value: object) -> str | None:
    return None if value is None else str(value)
