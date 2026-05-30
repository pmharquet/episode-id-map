"""Settings.load() : valeurs d'env, défauts, et "" traité comme absent."""

from __future__ import annotations

import pytest

from episode_id_map import config
from episode_id_map.config import Settings

_ALL_KEYS = [
    "TMDB_API_KEY", "TMDB_BASE_URL", "TVDB_API_KEY", "TVDB_PIN", "TVDB_BASE_URL",
    "SIMKL_CLIENT_ID", "SIMKL_BASE_URL", "JIKAN_BASE_URL",
    "ANIDB_CLIENT", "ANIDB_CLIENTVER", "ANIDB_BASE_URL", "DATABASE_URL",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    # Ne pas lire le vrai .env, et partir d'un environnement vierge.
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    for key in _ALL_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_when_unset() -> None:
    s = Settings.load()
    assert s.tmdb_base_url == "https://api.themoviedb.org/3"
    assert s.jikan_base_url == "https://api.jikan.moe/v4"
    assert s.anidb_base_url == "http://api.anidb.net:9001/httpapi"
    assert s.tmdb_api_key is None
    assert s.database_url is None


def test_reads_values(monkeypatch) -> None:
    monkeypatch.setenv("TMDB_API_KEY", "abc")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    s = Settings.load()
    assert s.tmdb_api_key == "abc"
    assert s.database_url == "postgresql://x/y"


def test_empty_string_is_none(monkeypatch) -> None:
    monkeypatch.setenv("TVDB_PIN", "")
    s = Settings.load()
    assert s.tvdb_pin is None
