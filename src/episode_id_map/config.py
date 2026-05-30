"""Chargement des variables d'environnement (.env) en un objet `Settings`.

Les clés API ne sont pas exigées au chargement : chaque client valide ce dont il a
besoin à sa construction (un fetcher TMDB n'a pas besoin de la clé TVDB, etc.).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _env(key: str, default: str | None = None) -> str | None:
    value = os.environ.get(key, default)
    return value if value not in ("", None) else default


@dataclass(frozen=True)
class Settings:
    tmdb_api_key: str | None
    tmdb_base_url: str
    tvdb_api_key: str | None
    tvdb_pin: str | None
    tvdb_base_url: str
    simkl_client_id: str | None
    simkl_base_url: str
    jikan_base_url: str
    anidb_client: str | None
    anidb_clientver: str | None
    anidb_base_url: str
    database_url: str | None

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        return cls(
            tmdb_api_key=_env("TMDB_API_KEY"),
            tmdb_base_url=_env("TMDB_BASE_URL", "https://api.themoviedb.org/3"),
            tvdb_api_key=_env("TVDB_API_KEY"),
            tvdb_pin=_env("TVDB_PIN"),
            tvdb_base_url=_env("TVDB_BASE_URL", "https://api4.thetvdb.com/v4"),
            simkl_client_id=_env("SIMKL_CLIENT_ID"),
            simkl_base_url=_env("SIMKL_BASE_URL", "https://api.simkl.com"),
            jikan_base_url=_env("JIKAN_BASE_URL", "https://api.jikan.moe/v4"),
            anidb_client=_env("ANIDB_CLIENT"),
            anidb_clientver=_env("ANIDB_CLIENTVER"),
            anidb_base_url=_env("ANIDB_BASE_URL", "http://api.anidb.net:9001/httpapi"),
            database_url=_env("DATABASE_URL"),
        )
