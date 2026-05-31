"""assign_absolute : résolution de l'episode_absolute par fréquence."""

from __future__ import annotations

import uuid

from episode_id_map.mapping.anchor import assign_absolute
from episode_id_map.models import EpisodeView


class FakeCursor:
    """Mappe (source,id_series,id_season,id_episode) → episode_absolute."""

    def __init__(self, data: dict[tuple, str]) -> None:
        self.data = data
        self._params: tuple | None = None

    def execute(self, _sql: str, params: tuple) -> None:
        self._params = params

    def fetchone(self):
        value = self.data.get(tuple(self._params[0:4]))
        return [value] if value is not None else None


def _view(source: str, episode: str) -> EpisodeView:
    return EpisodeView(source, "S", None, episode)


def test_new_uuid_when_none_exist() -> None:
    cur = FakeCursor({})
    result = assign_absolute(cur, [_view("ANIDB", "1"), _view("MAL", "1")])
    assert uuid.UUID(result)  # UUID valide


def test_reuses_single_existing() -> None:
    cur = FakeCursor({("ANIDB", "S", None, "1"): "ABS-1"})
    result = assign_absolute(cur, [_view("ANIDB", "1"), _view("MAL", "1")])
    assert result == "ABS-1"  # le frère neuf hérite de l'ancre existante


def test_conflict_picks_most_frequent() -> None:
    # ANIDB+MAL+SIMKL ont EA-A (count=3), TVDB a EA-X (count=1), TMDB a EA-Z (count=1).
    # EA-A doit gagner : c'est l'ancre stable déjà partagée.
    cur = FakeCursor(
        {
            ("ANIDB", "S", None, "1"): "EA-A",
            ("MAL",   "S", None, "1"): "EA-A",
            ("SIMKL", "S", None, "1"): "EA-A",
            ("TVDB",  "S", None, "1"): "EA-X",
            ("TMDB",  "S", None, "1"): "EA-Z",
        }
    )
    group = [_view(s, "1") for s in ("ANIDB", "MAL", "SIMKL", "TVDB", "TMDB")]
    assert assign_absolute(cur, group) == "EA-A"


def test_conflict_equal_count_picks_smallest() -> None:
    # Deux singletons, aucun n'est plus fréquent → plus petit UUID déterministe.
    cur = FakeCursor(
        {
            ("TVDB", "S", None, "1"): "EA-b",
            ("TMDB", "S", None, "1"): "EA-a",
        }
    )
    group = [_view("ANIDB", "1"), _view("TVDB", "1"), _view("TMDB", "1")]
    result = assign_absolute(cur, group)
    assert result == "EA-a"  # plus petit parmi les deux singletons
