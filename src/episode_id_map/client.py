"""Client HTTP de base : httpx + rate-limit + retry/backoff (429 / 5xx).

Tous les fetchers de `sources/` en héritent. Le retry ne couvre QUE les erreurs
transitoires (429, 5xx) ; les 4xx « définitives » remontent immédiatement.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .ratelimit import RateLimiter

log = structlog.get_logger()


class RetryableError(Exception):
    """Erreur transitoire (429 / 5xx) → re-tentée avec backoff."""


class BaseClient:
    source = "BASE"

    def __init__(
        self,
        base_url: str,
        *,
        rate: float,
        burst: int | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
        max_attempts: int = 5,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._limiter = limiter if limiter is not None else RateLimiter(rate, burst)
        self._client = httpx.Client(
            base_url=base_url,
            headers=headers or {},
            params=params or {},
            timeout=timeout,
            follow_redirects=True,
        )
        self._max_attempts = max_attempts
        self._log = log.bind(source=self.source)

    # -- gestion du cycle de vie --------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BaseClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- requête bas niveau --------------------------------------------------
    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        def _do() -> httpx.Response:
            self._limiter.acquire()
            resp = self._client.request(method, path, **kwargs)
            if resp.status_code == 429 or resp.status_code >= 500:
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        time.sleep(float(retry_after))
                    except ValueError:
                        pass
                self._log.warning(
                    "http.retryable", status=resp.status_code, path=path
                )
                raise RetryableError(f"{resp.status_code} sur {path}")
            resp.raise_for_status()
            return resp

        runner = retry(
            reraise=True,
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential_jitter(initial=1.0, max=30.0),
            retry=retry_if_exception_type(RetryableError),
        )(_do)
        return runner()

    def get_json(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs).json()
