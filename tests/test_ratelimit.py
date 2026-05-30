"""RateLimiter : test déterministe via une horloge factice (pas de vraie attente)."""

from __future__ import annotations

import pytest

from episode_id_map import ratelimit
from episode_id_map.ratelimit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(ratelimit, "time", fake)
    return fake


def test_burst_is_instant(clock: FakeClock) -> None:
    limiter = RateLimiter(rate=10.0, burst=3)
    for _ in range(3):
        limiter.acquire()
    assert clock.t == 0.0  # 3 jetons disponibles d'emblée


def test_throttles_after_burst(clock: FakeClock) -> None:
    limiter = RateLimiter(rate=10.0, burst=3)
    for _ in range(4):
        limiter.acquire()
    # Le 4e jeton nécessite (1/10) s d'attente.
    assert clock.t == pytest.approx(0.1)


def test_sustained_rate(clock: FakeClock) -> None:
    limiter = RateLimiter(rate=2.0, burst=1)
    for _ in range(5):
        limiter.acquire()
    # 1 instant + 4 attentes de 0,5 s = 2,0 s pour 5 acquisitions à 2/s.
    assert clock.t == pytest.approx(2.0)


def test_invalid_rate() -> None:
    with pytest.raises(ValueError):
        RateLimiter(rate=0)
