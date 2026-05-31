"""align_episodes : groupage des vues-source sur la grille AniDB."""

from __future__ import annotations

from episode_id_map.mapping.align import (
    aid_from_external,
    align_episodes,
    parse_aid_from_url,
)
from episode_id_map.models import Cluster, Fetched

CLUSTER = Cluster(
    mal_id=52991, aid=17617, simkl_id=1990194,
    tmdb_id=209867, tvdb_id=424536, work_type="tv",
)


def _fetched() -> Fetched:
    # 3 épisodes réels, tous diffusés le même jour (cas premiere Frieren) →
    # le fallback airdate est ambigu, l'alignement doit passer par les ponts d'id.
    return Fetched(
        anidb=[
            {"epno": "1", "airdate": "2023-09-29"},
            {"epno": "2", "airdate": "2023-09-29"},
            {"epno": "3", "airdate": "2023-09-29"},
        ],
        mal=[
            {"mal_id": 1, "aired": "2023-09-29T00:00:00+00:00"},
            {"mal_id": 2, "aired": "2023-09-29T00:00:00+00:00"},
            {"mal_id": 3, "aired": "2023-09-29T00:00:00+00:00"},
        ],
        simkl=[
            {"episode": 1, "date": "2023-09-29T23:00:00+09:00", "tvdb": {"season": 1, "episode": 1}},
            {"episode": 2, "date": "2023-09-29T23:00:00+09:00", "tvdb": {"season": 1, "episode": 2}},
            {"episode": 3, "date": "2023-09-29T23:00:00+09:00", "tvdb": {"season": 1, "episode": 3}},
        ],
        tvdb=[
            {"id": 9001, "seasonNumber": 1, "number": 1, "aired": "2023-09-29"},
            {"id": 9002, "seasonNumber": 1, "number": 2, "aired": "2023-09-29"},
            {"id": 9003, "seasonNumber": 1, "number": 3, "aired": "2023-09-29"},
            {"id": 9000, "seasonNumber": 0, "number": 1, "aired": "2023-01-01"},  # special
        ],
        tmdb=[
            {"season_number": 1, "episode_number": 1, "air_date": "2023-09-29", "tvdb_id": 9001},
            {"season_number": 1, "episode_number": 2, "air_date": "2023-09-29", "tvdb_id": 9002},
            {"season_number": 1, "episode_number": 3, "air_date": "2023-09-29", "tvdb_id": 9003},
            {"season_number": 0, "episode_number": 1, "air_date": "2022-01-01", "tvdb_id": None},  # special
        ],
    )


def test_real_episodes_group_all_five_sources() -> None:
    groups = align_episodes(CLUSTER, _fetched())
    full = [g for g in groups if len(g) == 5]
    assert len(full) == 3  # les 3 épisodes réels
    for g in full:
        assert {v.source for v in g} == {"ANIDB", "MAL", "SIMKL", "TVDB", "TMDB"}


def test_episode_one_shares_anchor_key() -> None:
    groups = align_episodes(CLUSTER, _fetched())
    g1 = next(g for g in groups if all(v.epno == 1 for v in g))
    by_source = {v.source: v for v in g1}
    assert by_source["MAL"].id_episode == "1"
    assert by_source["TVDB"].id_season == "1" and by_source["TVDB"].id_episode == "1"
    assert by_source["TMDB"].extra == {"type": "tv"}
    assert by_source["ANIDB"].extra == {"epno_type": 1}


def test_specials_are_unlinked_singletons() -> None:
    groups = align_episodes(CLUSTER, _fetched())
    singles = [g for g in groups if len(g) == 1]
    # 1 special TVDB (S0) + 1 special TMDB (sans tvdb_id, airdate isolée).
    assert len(singles) == 2
    assert {g[0].source for g in singles} == {"TVDB", "TMDB"}


def test_total_groups() -> None:
    groups = align_episodes(CLUSTER, _fetched())
    assert len(groups) == 5  # 3 réels + 2 specials isolés


def test_aid_parsing() -> None:
    assert parse_aid_from_url("https://anidb.net/perl-bin/animedb.pl?show=anime&aid=17617") == 17617
    assert parse_aid_from_url("https://anidb.net/anime/17617") == 17617
    assert parse_aid_from_url("https://example.com") is None
    assert aid_from_external([{"name": "AniDB", "url": "x?aid=42"}]) == 42
    assert aid_from_external([{"name": "ANN", "url": "x?id=1"}]) is None
