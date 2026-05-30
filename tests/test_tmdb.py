"""TMDBClient : clé en query, itération des saisons, exclusion des specials."""

from __future__ import annotations

import httpx
import pytest
import respx

from episode_id_map.sources.tmdb import TMDBClient


def _mock_tv_and_seasons() -> None:
    respx.get("https://tmdb.test/3/tv/209867").mock(
        return_value=httpx.Response(
            200,
            json={"seasons": [{"season_number": 0}, {"season_number": 1}]},
        )
    )
    respx.get("https://tmdb.test/3/tv/209867/season/0").mock(
        return_value=httpx.Response(200, json={"episodes": [{"episode_number": 1}]})
    )
    respx.get("https://tmdb.test/3/tv/209867/season/1").mock(
        return_value=httpx.Response(
            200,
            json={"episodes": [{"episode_number": 1}, {"episode_number": 2}]},
        )
    )


@respx.mock
def test_iter_episodes_excludes_specials(settings) -> None:
    _mock_tv_and_seasons()
    with TMDBClient(settings) as c:
        episodes = list(c.iter_episodes(209867))
    # Saison 0 exclue par défaut → seulement les 2 épisodes de la saison 1.
    assert len(episodes) == 2
    assert all(e["season_number"] == 1 for e in episodes)


@respx.mock
def test_iter_episodes_with_specials(settings) -> None:
    _mock_tv_and_seasons()
    with TMDBClient(settings) as c:
        episodes = list(c.iter_episodes(209867, include_specials=True))
    assert len(episodes) == 3


@respx.mock
def test_api_key_in_query(settings) -> None:
    route = respx.get("https://tmdb.test/3/tv/209867/external_ids").mock(
        return_value=httpx.Response(200, json={"tvdb_id": 424536})
    )
    with TMDBClient(settings) as c:
        assert c.get_tv_external_ids(209867)["tvdb_id"] == 424536
    assert route.calls.last.request.url.params["api_key"] == "TMDBKEY"


def test_missing_key_raises() -> None:
    from tests.conftest import make_settings

    with pytest.raises(RuntimeError):
        TMDBClient(make_settings(tmdb_api_key=None))
