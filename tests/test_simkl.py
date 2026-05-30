"""SimklClient : en-tête simkl-api-key, validation des services, épisodes."""

from __future__ import annotations

import httpx
import pytest
import respx

from episode_id_map.sources.simkl import SimklClient


@respx.mock
def test_search_id_sends_api_key_header(settings) -> None:
    route = respx.get("https://simkl.test/search/id").mock(
        return_value=httpx.Response(200, json=[{"ids": {"simkl": 1990194}}])
    )
    with SimklClient(settings) as c:
        result = c.search_id(anidb=17617)
    assert result[0]["ids"]["simkl"] == 1990194
    assert route.calls.last.request.headers["simkl-api-key"] == "SIMKLID"
    assert route.calls.last.request.url.params["anidb"] == "17617"


def test_search_id_rejects_unknown_service(settings) -> None:
    with SimklClient(settings) as c:
        with pytest.raises(ValueError):
            c.search_id(bogus=1)


@respx.mock
def test_get_episodes(settings) -> None:
    respx.get("https://simkl.test/anime/episodes/1990194").mock(
        return_value=httpx.Response(
            200, json=[{"episode": 1, "tvdb": {"season": 1, "episode": 2}}]
        )
    )
    with SimklClient(settings) as c:
        episodes = c.get_episodes(1990194)
    assert episodes[0]["tvdb"] == {"season": 1, "episode": 2}
