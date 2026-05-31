"""ingest : câblage resolve→fetch→align→assign→upsert (DB et réseau simulés)."""

from __future__ import annotations

import pytest

from episode_id_map import ingest as ingest_mod
from episode_id_map.models import Cluster
from tests.test_align import CLUSTER, _fetched


class FakeCursor:
    def __init__(self) -> None:
        self.inserts: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def execute(self, sql: str, params=None) -> None:
        if sql.strip().upper().startswith("INSERT"):
            self.inserts.append(params)

    def fetchone(self):
        return None  # aucune ligne existante → tout est neuf


class FakeConn:
    def __init__(self) -> None:
        self.cur = FakeCursor()
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def cursor(self):
        return self.cur

    def commit(self) -> None:
        self.committed = True


@pytest.fixture
def fake_db(monkeypatch):
    conn = FakeConn()
    monkeypatch.setattr(ingest_mod.db, "connect", lambda _s: conn)
    monkeypatch.setattr(ingest_mod, "resolve_cluster", lambda _m, *, settings: CLUSTER)
    monkeypatch.setattr(ingest_mod, "fetch_all", lambda _c, *, settings: _fetched())
    return conn


def test_ingest_writes_one_absolute_per_group(fake_db, settings) -> None:
    stats = ingest_mod.ingest(52991, settings=settings)

    # 3 épisodes réels (5 sources) = 15 lignes écrites.
    # Les 2 singletons TVDB/TMDB (specials hors grille MAL) sont ignorés (skipped=2).
    assert stats["groups"] == 3
    assert stats["skipped"] == 2
    assert stats["rows"] == 15
    assert len(fake_db.cur.inserts) == 15
    assert fake_db.committed

    absolutes = {row[1] for row in fake_db.cur.inserts}
    assert len(absolutes) == 3  # un episode_absolute distinct par groupe réel
