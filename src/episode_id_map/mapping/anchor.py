"""Attribution de l'`episode_absolute` à un groupe, SANS table auxiliaire.

Résolution depuis `episode_id_map` seul (cf. décision utilisateur) :
0 trouvé → nouvel UUID ; 1 valeur → réutilisée ; conflit → pas de fusion, on logue.
"""

from __future__ import annotations

import uuid as uuidlib

import structlog

from ..db import fetch_episode_absolute
from ..models import EpisodeView

log = structlog.get_logger()


def assign_absolute(cur, group: list[EpisodeView]) -> str:
    found: list[str] = []
    for view in group:
        existing = fetch_episode_absolute(
            cur, view.source, view.id_series, view.id_season, view.id_episode
        )
        if existing:
            found.append(existing)

    distinct = sorted(set(found))
    if not distinct:
        return str(uuidlib.uuid4())
    if len(distinct) == 1:
        return distinct[0]

    # Conflit : plusieurs épisodes réels déjà distincts visent ce groupe. On ne
    # fusionne PAS (romprait l'anti-doublon du bot) ; on adopte le plus petit pour
    # les membres encore sans UUID, et on logue pour revue.
    log.warning(
        "anchor.conflict",
        sources=[v.source for v in group],
        episode_absolutes=distinct,
    )
    return distinct[0]
