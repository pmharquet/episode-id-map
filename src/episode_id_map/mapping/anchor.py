"""Attribution de l'`episode_absolute` à un groupe, SANS table auxiliaire.

Stratégie en cas de conflit (plusieurs EAs distincts trouvés en base) :
- on choisit l'EA le plus fréquent (ANIDB/MAL/SIMKL partagent souvent le même après
  un premier ingest, ce qui donne count=3 vs count=1 pour les singletons TVDB/TMDB) ;
- en cas d'égalité parfaite (singletons), le plus petit UUID alphanumérique est utilisé
  pour un comportement déterministe.
- L'upsert met alors à jour `episode_absolute` pour les lignes "perdantes", ce qui
  résout le problème des singletons TVDB/TMDB créés lors de l'ingest d'une saison
  précédente.
"""

from __future__ import annotations

import uuid as uuidlib
from collections import Counter

import structlog

from ..db import fetch_episode_absolute
from ..models import EpisodeView

log = structlog.get_logger()


def assign_absolute(cur, group: list[EpisodeView]) -> str:
    ea_counts: Counter[str] = Counter()
    for view in group:
        existing = fetch_episode_absolute(
            cur, view.source, view.id_series, view.id_season, view.id_episode
        )
        if existing:
            ea_counts[existing] += 1

    if not ea_counts:
        return str(uuidlib.uuid4())

    # EA le plus fréquent gagne ; à fréquence égale : plus petit UUID (déterminisme).
    best_ea = sorted(ea_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    if len(ea_counts) > 1:
        log.warning(
            "anchor.conflict",
            sources=[v.source for v in group],
            chosen=best_ea,
            counts=dict(ea_counts),
        )

    return best_ea
