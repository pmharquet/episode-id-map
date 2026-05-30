"""AniDBClient : parsing épisodes type=1, erreurs en HTTP 200, ban, cache disque."""

from __future__ import annotations

import httpx
import pytest
import respx

from episode_id_map.sources.anidb import AniDBBanned, AniDBClient, AniDBError

_XML = """<?xml version="1.0" encoding="UTF-8"?>
<anime id="17617">
  <episodes>
    <episode id="271418">
      <epno type="1">1</epno>
      <airdate>2023-09-29</airdate>
      <title xml:lang="en">The Journey's End</title>
      <title xml:lang="fr">La fin de l'aventure</title>
    </episode>
    <episode id="999">
      <epno type="2">S1</epno>
      <airdate>2023-01-01</airdate>
      <title xml:lang="en">A Special</title>
    </episode>
  </episodes>
</anime>"""


@respx.mock
def test_regular_episodes_filters_and_parses(settings, tmp_path) -> None:
    respx.get(url__startswith="http://anidb.test/httpapi").mock(
        return_value=httpx.Response(200, text=_XML)
    )
    with AniDBClient(settings, cache_dir=tmp_path) as c:
        root = c.get_anime(17617)
        episodes = c.regular_episodes(root)
    assert len(episodes) == 1  # le special type=2 est exclu
    ep = episodes[0]
    assert ep["epid"] == "271418"
    assert ep["epno"] == "1"
    assert ep["airdate"] == "2023-09-29"
    assert ep["title_fr"] == "La fin de l'aventure"
    assert ep["title_en"] == "The Journey's End"


@respx.mock
def test_cache_avoids_second_request(settings, tmp_path) -> None:
    route = respx.get(url__startswith="http://anidb.test/httpapi").mock(
        return_value=httpx.Response(200, text=_XML)
    )
    with AniDBClient(settings, cache_dir=tmp_path) as c:
        c.get_anime_xml(17617)
        c.get_anime_xml(17617)  # 2e appel → servi par le cache
    assert route.call_count == 1
    assert (tmp_path / "anime-17617.xml").exists()


@respx.mock
def test_error_in_200_body(settings, tmp_path) -> None:
    respx.get(url__startswith="http://anidb.test/httpapi").mock(
        return_value=httpx.Response(
            200, text='<error code="302">client version missing or invalid</error>'
        )
    )
    with AniDBClient(settings, cache_dir=tmp_path) as c:
        with pytest.raises(AniDBError) as exc:
            c.get_anime_xml(17617)
    assert exc.value.code == "302"
    assert not (tmp_path / "anime-17617.xml").exists()  # erreur → pas de cache


@respx.mock
def test_ban_is_fatal(settings, tmp_path) -> None:
    respx.get(url__startswith="http://anidb.test/httpapi").mock(
        return_value=httpx.Response(200, text="<error>banned</error>")
    )
    with AniDBClient(settings, cache_dir=tmp_path) as c:
        with pytest.raises(AniDBBanned):
            c.get_anime_xml(17617)


def test_missing_client_raises(tmp_path) -> None:
    from tests.conftest import make_settings

    with pytest.raises(RuntimeError):
        AniDBClient(make_settings(anidb_client=None), cache_dir=tmp_path)
