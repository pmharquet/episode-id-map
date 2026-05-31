"""Modèles de données du mapping (ÉTAPE 4).

`EpisodeView` = vue normalisée d'un épisode pour UNE source. Les champs persistés
(source/id_series/id_season/id_episode/extra) deviennent une ligne `episode_id_map` ;
`epno` et `airdate` ne servent qu'à l'alignement en mémoire (non persistés).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class Cluster:
    """Identifiants d'une même œuvre à travers les sources."""

    mal_id: int | None = None
    aid: int | None = None
    simkl_id: int | None = None
    tmdb_id: int | None = None
    tvdb_id: int | None = None
    work_type: str = "tv"  # "tv" | "movie"
    mal_ids: list[int] = field(default_factory=list)


@dataclass
class Fetched:
    """Réponses brutes (déjà normalisées en listes de dicts) des 5 fetchers."""

    anidb: list[dict] = field(default_factory=list)  # AniDBClient.regular_episodes
    mal: list[dict] = field(default_factory=list)
    simkl: list[dict] = field(default_factory=list)
    tvdb: list[dict] = field(default_factory=list)
    tmdb: list[dict] = field(default_factory=list)


@dataclass
class EpisodeView:
    source: str
    id_series: str | None
    id_season: str | None
    id_episode: str | None
    extra: dict[str, Any] | None = None
    # --- aides au matching, NON persistées ---
    epno: int | None = None
    airdate: date | None = None


@dataclass
class Row:
    """Ligne prête à écrire dans `episode_id_map`."""

    uuid: str
    episode_absolute: str
    source: str
    id_series: str | None
    id_season: str | None
    id_episode: str | None
    extra: dict[str, Any] | None
