"""Limiteur de débit token-bucket, thread-safe.

`rate` jetons/seconde, capacité `burst`. `acquire()` bloque jusqu'à disposer d'un
jeton. Modélise un débit soutenu (rate) avec tolérance de pointe (burst) — exactement
ce que demandent les quotas des API (ex. Jikan 60/min = 1/s soutenu, pointe à 3).
"""

from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, rate: float, burst: int | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate doit être > 0")
        self.rate = rate
        self.capacity = burst if burst is not None else max(1, int(rate))
        self._tokens = float(self.capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            while True:
                now = time.monotonic()
                self._tokens = min(
                    self.capacity, self._tokens + (now - self._last) * self.rate
                )
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                time.sleep((1.0 - self._tokens) / self.rate)
