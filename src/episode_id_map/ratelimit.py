"""Limiteur de débit token-bucket, thread-safe.

`rate` jetons/seconde, capacité `burst`. `acquire()` bloque jusqu'à disposer d'un
jeton. Modélise un débit soutenu (rate) avec tolérance de pointe (burst) — exactement
ce que demandent les quotas des API (ex. Jikan 60/min = 1/s soutenu, pointe à 3).

`daily_limit` active un compteur par fenêtre de 24h glissante. Quand le quota est
atteint, `acquire()` lève `DailyLimitExceeded` (non-retryable) plutôt que de bloquer.
"""

from __future__ import annotations

import threading
import time

_DAY = 86400.0


class DailyLimitExceeded(Exception):
    def __init__(self, name: str, limit: int) -> None:
        super().__init__(f"Quota journalier {name} atteint ({limit} req/24h)")
        self.source = name
        self.limit = limit


class RateLimiter:
    def __init__(
        self,
        rate: float,
        burst: int | None = None,
        *,
        name: str = "",
        daily_limit: int | None = None,
    ) -> None:
        if rate <= 0:
            raise ValueError("rate doit être > 0")
        self.rate = rate
        self.capacity = burst if burst is not None else max(1, int(rate))
        self._tokens = float(self.capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

        self._name = name
        self._daily_limit = daily_limit
        self._daily_count = 0
        self._day_start = time.monotonic()

    # ── quota journalier ────────────────────────────────────────────────────────

    @property
    def daily_remaining(self) -> int | None:
        """Requêtes restantes dans la fenêtre de 24h courante, ou None si illimité."""
        if self._daily_limit is None:
            return None
        with self._lock:
            self._maybe_reset_day()
            return max(0, self._daily_limit - self._daily_count)

    @property
    def daily_used(self) -> int:
        with self._lock:
            self._maybe_reset_day()
            return self._daily_count

    def _maybe_reset_day(self) -> None:
        """Réinitialise le compteur si la fenêtre de 24h est écoulée (appelé sous lock)."""
        if time.monotonic() - self._day_start >= _DAY:
            self._daily_count = 0
            self._day_start = time.monotonic()

    # ── acquisition ─────────────────────────────────────────────────────────────

    def acquire(self) -> None:
        with self._lock:
            # Quota journalier : vérifier avant de consommer un jeton.
            if self._daily_limit is not None:
                self._maybe_reset_day()
                if self._daily_count >= self._daily_limit:
                    raise DailyLimitExceeded(self._name, self._daily_limit)
                self._daily_count += 1

            # Token-bucket per-seconde.
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
