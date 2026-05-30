"""JikanClient : pagination via has_next_page, extraction des liens externes."""

from __future__ import annotations

import httpx
import respx

from episode_id_map.sources.jikan import JikanClient


@respx.mock
def test_iter_episodes_paginates(settings) -> None:
    respx.get("https://jikan.test/v4/anime/52991/episodes").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"data": [{"mal_id": 1}, {"mal_id": 2}],
                      "pagination": {"has_next_page": True}},
            ),
            httpx.Response(
                200,
                json={"data": [{"mal_id": 3}], "pagination": {"has_next_page": False}},
            ),
        ]
    )
    with JikanClient(settings) as c:
        episodes = list(c.iter_episodes(52991))
    assert [e["mal_id"] for e in episodes] == [1, 2, 3]


@respx.mock
def test_get_external(settings) -> None:
    respx.get("https://jikan.test/v4/anime/52991/external").mock(
        return_value=httpx.Response(
            200, json={"data": [{"name": "AniDB", "url": "...aid=17617"}]}
        )
    )
    with JikanClient(settings) as c:
        external = c.get_external(52991)
    assert external[0]["name"] == "AniDB"
