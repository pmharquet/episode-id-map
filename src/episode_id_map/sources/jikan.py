"""Jikan (MyAnimeList) — `source = "MAL"`.

Pas de clé. Quota : 60 req/min (= 1/s soutenu) + pointe ~3/s → token-bucket
rate=1, burst=3. Pagination via `pagination.has_next_page`.
Cf. docs/apis/jikan.md.
"""

from __future__ import annotations

from typing import Any, Iterator

from ..client import BaseClient
from ..config import Settings
from . import limiters


class JikanClient(BaseClient):
    source = "MAL"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings.jikan_base_url, rate=1.0, burst=3, limiter=limiters.jikan)

    def get_anime(self, mal_id: int) -> dict[str, Any]:
        """Fiche série (`data`)."""
        return self.get_json(f"/anime/{mal_id}")["data"]

    def iter_episodes(self, mal_id: int) -> Iterator[dict[str, Any]]:
        """Tous les épisodes, page par page (≈100/page).

        Rappel : `mal_id` d'un épisode = son NUMÉRO (1..N), pas l'id série.
        """
        page = 1
        while True:
            payload = self.get_json(
                f"/anime/{mal_id}/episodes", params={"page": page}
            )
            yield from payload.get("data", [])
            pagination = payload.get("pagination", {})
            if not pagination.get("has_next_page"):
                break
            page += 1

    def get_external(self, mal_id: int) -> list[dict[str, Any]]:
        """Liens externes (URLs) — seul cross-id exploitable = AniDB."""
        return self.get_json(f"/anime/{mal_id}/external")["data"]
