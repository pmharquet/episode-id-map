"""Fixtures partagées : un `Settings` factice pointant vers des hôtes *.test
(jamais de vrai réseau — respx intercepte tout)."""

from __future__ import annotations

import pytest

from episode_id_map.config import Settings


def make_settings(**overrides) -> Settings:
    base = dict(
        tmdb_api_key="TMDBKEY",
        tmdb_base_url="https://tmdb.test/3",
        tvdb_api_key="TVDBKEY",
        tvdb_pin=None,
        tvdb_base_url="https://tvdb.test/v4",
        simkl_client_id="SIMKLID",
        simkl_base_url="https://simkl.test",
        jikan_base_url="https://jikan.test/v4",
        anidb_client="testclient",
        anidb_clientver="1",
        anidb_base_url="http://anidb.test/httpapi",
        database_url=None,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def settings() -> Settings:
    return make_settings()
