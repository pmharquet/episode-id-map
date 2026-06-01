"""TMDB (The Movie Database) — `source = "TMDB"`.

Clé v3 en query (`api_key`). Pas de pagination au niveau épisode : une saison
renvoie tous ses épisodes d'un coup → on itère les saisons de `seasons[]`.
Cf. docs/apis/tmdb.md.
"""

from __future__ import annotations

from typing import Any, Iterator

from ..client import BaseClient
from ..config import Settings
from . import limiters


class TMDBClient(BaseClient):
    source = "TMDB"

    def __init__(self, settings: Settings, *, language: str = "fr-FR") -> None:
        if not settings.tmdb_api_key:
            raise RuntimeError("TMDB_API_KEY manquant dans .env")
        super().__init__(
            settings.tmdb_base_url,
            rate=4.0,   # TMDB limite à ~40 req/10s ; 4/s conservateur
            burst=8,
            params={"api_key": settings.tmdb_api_key, "language": language},
            limiter=limiters.tmdb,
        )

    def get_tv(self, tv_id: int) -> dict[str, Any]:
        return self.get_json(f"/tv/{tv_id}")

    def get_season(self, tv_id: int, season_number: int) -> dict[str, Any]:
        return self.get_json(f"/tv/{tv_id}/season/{season_number}")

    def get_tv_external_ids(self, tv_id: int) -> dict[str, Any]:
        return self.get_json(f"/tv/{tv_id}/external_ids")

    def get_episode_external_ids(
        self, tv_id: int, season_number: int, episode_number: int
    ) -> dict[str, Any]:
        """Cross-ids niveau épisode → contient `tvdb_id` (pont vers TVDB)."""
        return self.get_json(
            f"/tv/{tv_id}/season/{season_number}"
            f"/episode/{episode_number}/external_ids"
        )

    def get_movie(self, movie_id: int) -> dict[str, Any]:
        return self.get_json(f"/movie/{movie_id}")

    def iter_episodes(
        self, tv_id: int, *, include_specials: bool = False
    ) -> Iterator[dict[str, Any]]:
        """Tous les épisodes de la série, saison par saison.

        Chaque épisode est enrichi de `season_number` (la saison TMDB réelle).
        `season_number=0` = specials → exclus par défaut.
        """
        tv = self.get_tv(tv_id)
        for season in tv.get("seasons", []):
            n = season.get("season_number")
            if n is None or (n == 0 and not include_specials):
                continue
            for episode in self.get_season(tv_id, n).get("episodes", []):
                episode["season_number"] = n
                yield episode
