"""assign_absolute : les 4 cas de résolution sans table auxiliaire."""

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


def test_conflict_picks_smallest_without_merging() -> None:
    cur = FakeCursor(
        {
            ("ANIDB", "S", None, "1"): "ABS-b",
            ("MAL", "S", None, "1"): "ABS-a",
        }
    )
    result = assign_absolute(cur, [_view("ANIDB", "1"), _view("MAL", "1")])
    assert result == "ABS-a"  # min ; pas de fusion destructive
