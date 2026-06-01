"""TheTVDB v4 — `source = "TVDB"` · pivot cross-ID secondaire.

Auth : `POST /login {apikey[, pin]}` → JWT Bearer (valable ~1 mois).
Pagination : `?page=N` (départ 0), suivre `links.next`. Re-login auto sur 401.
La liste `official` inclut la saison 0 (specials) → filtrer `seasonNumber`.
Cf. docs/apis/tvdb.md.
"""

from __future__ import annotations

from typing import Any, Iterator

import httpx

from ..client import BaseClient
from ..config import Settings
from . import limiters


class TVDBClient(BaseClient):
    source = "TVDB"

    def __init__(self, settings: Settings) -> None:
        if not settings.tvdb_api_key:
            raise RuntimeError("TVDB_API_KEY manquant dans .env")
        super().__init__(settings.tvdb_base_url, rate=8.0, burst=8, limiter=limiters.tvdb)
        self._api_key = settings.tvdb_api_key
        self._pin = settings.tvdb_pin
        self._token: str | None = None

    def login(self) -> None:
        body: dict[str, str] = {"apikey": self._api_key}
        if self._pin:
            body["pin"] = self._pin
        data = self.request("POST", "/login", json=body).json()
        self._token = data["data"]["token"]
        self._client.headers["Authorization"] = f"Bearer {self._token}"
        self._log.info("tvdb.login_ok")

    def _get(self, path: str, **kwargs: Any) -> Any:
        if self._token is None:
            self.login()
        try:
            return self.get_json(path, **kwargs)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:  # token expiré → re-login une fois
                self.login()
                return self.get_json(path, **kwargs)
            raise

    def get_series_extended(self, series_id: int) -> dict[str, Any]:
        return self._get(f"/series/{series_id}/extended")["data"]

    def iter_episodes(
        self, series_id: int, season_type: str = "official"
    ) -> Iterator[dict[str, Any]]:
        page = 0
        while True:
            payload = self._get(
                f"/series/{series_id}/episodes/{season_type}",
                params={"page": page},
            )
            data = payload.get("data", {})
            episodes = data.get("episodes", [])
            yield from episodes
            if not payload.get("links", {}).get("next"):
                break
            page += 1

    def get_episode_extended(self, episode_id: int) -> dict[str, Any]:
        return self._get(f"/episodes/{episode_id}/extended")["data"]

    def search_remote_id(self, remote_id: str) -> list[dict[str, Any]]:
        return self._get(f"/search/remoteid/{remote_id}")["data"]
