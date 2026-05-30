"""TVDBClient : login→Bearer, pagination links.next, re-login auto sur 401."""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from episode_id_map.sources.tvdb import TVDBClient


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)


@respx.mock
def test_login_and_pagination(settings) -> None:
    login = respx.post("https://tvdb.test/v4/login").mock(
        return_value=httpx.Response(200, json={"data": {"token": "JWT123"}})
    )
    respx.get("https://tvdb.test/v4/series/424536/episodes/official").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"data": {"episodes": [{"id": 1}, {"id": 2}]},
                      "links": {"next": "page2"}},
            ),
            httpx.Response(
                200,
                json={"data": {"episodes": [{"id": 3}]}, "links": {"next": None}},
            ),
        ]
    )
    with TVDBClient(settings) as c:
        episodes = list(c.iter_episodes(424536))
    assert [e["id"] for e in episodes] == [1, 2, 3]
    assert login.called
    # Le Bearer est bien posé après login.
    assert c._client.headers["Authorization"] == "Bearer JWT123"


@respx.mock
def test_relogin_on_401(settings) -> None:
    login = respx.post("https://tvdb.test/v4/login").mock(
        side_effect=[
            httpx.Response(200, json={"data": {"token": "OLD"}}),
            httpx.Response(200, json={"data": {"token": "NEW"}}),
        ]
    )
    respx.get("https://tvdb.test/v4/series/1/extended").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json={"data": {"id": 1}}),
        ]
    )
    with TVDBClient(settings) as c:
        data = c.get_series_extended(1)
    assert data["id"] == 1
    assert login.call_count == 2  # login initial + re-login après 401


def test_missing_key_raises() -> None:
    from tests.conftest import make_settings

    with pytest.raises(RuntimeError):
        TVDBClient(make_settings(tvdb_api_key=None))
