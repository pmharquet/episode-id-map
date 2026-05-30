"""BaseClient : succès, retry sur 429/5xx, abandon, et 4xx non re-tenté."""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from episode_id_map.client import BaseClient, RetryableError


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    # Neutralise les attentes de backoff (tenacity + Retry-After).
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)


@respx.mock
def test_get_json_ok() -> None:
    respx.get("https://x.test/ping").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    with BaseClient("https://x.test", rate=1000) as c:
        assert c.get_json("/ping") == {"ok": True}


@respx.mock
def test_retries_then_succeeds() -> None:
    route = respx.get("https://x.test/ping").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": 1})]
    )
    with BaseClient("https://x.test", rate=1000) as c:
        assert c.get_json("/ping") == {"ok": 1}
    assert route.call_count == 2


@respx.mock
def test_gives_up_after_max_attempts() -> None:
    route = respx.get("https://x.test/ping").mock(return_value=httpx.Response(500))
    with BaseClient("https://x.test", rate=1000, max_attempts=3) as c:
        with pytest.raises(RetryableError):
            c.get_json("/ping")
    assert route.call_count == 3


@respx.mock
def test_4xx_not_retried() -> None:
    route = respx.get("https://x.test/ping").mock(return_value=httpx.Response(404))
    with BaseClient("https://x.test", rate=1000) as c:
        with pytest.raises(httpx.HTTPStatusError):
            c.get_json("/ping")
    assert route.call_count == 1
