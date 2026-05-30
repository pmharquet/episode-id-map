"""SIMKL — `source = "SIMKL"` · pivot cross-ID principal.

Auth : en-tête `simkl-api-key`. Pas de pagination (anime/episodes renvoie tout).
Cf. docs/apis/simkl.md.
"""

from __future__ import annotations

from typing import Any

from ..client import BaseClient
from ..config import Settings

# Services acceptés par /search/id.
SEARCH_SERVICES = {
    "simkl", "imdb", "tvdb", "tmdb", "mal", "anidb", "anilist",
    "hulu", "netflix", "crunchyroll",
}


class SimklClient(BaseClient):
    source = "SIMKL"

    def __init__(self, settings: Settings) -> None:
        if not settings.simkl_client_id:
            raise RuntimeError("SIMKL_CLIENT_ID manquant dans .env")
        super().__init__(
            settings.simkl_base_url,
            rate=4.0,
            burst=4,
            headers={"simkl-api-key": settings.simkl_client_id},
        )

    def search_id(self, **external_ids: Any) -> list[dict[str, Any]]:
        """Lookup par id externe, ex. `search_id(anidb=17617)` ou `mal=52991`.

        Pour `tmdb`, préciser `type="show"|"anime"|"movie"`.
        """
        unknown = set(external_ids) - SEARCH_SERVICES - {"type"}
        if unknown:
            raise ValueError(f"services /search/id inconnus : {sorted(unknown)}")
        return self.get_json("/search/id", params=external_ids)

    def get_anime(self, simkl_id: int) -> dict[str, Any]:
        """Fiche anime + bloc `ids` complet (mal/anidb/tmdb/tvdb/imdb/…)."""
        return self.get_json(f"/anime/{simkl_id}", params={"extended": "full"})

    def get_episodes(self, simkl_id: int) -> list[dict[str, Any]]:
        """Épisodes (numérotation AniDB) + mapping `tvdb:{season,episode}`."""
        return self.get_json(f"/anime/episodes/{simkl_id}")
