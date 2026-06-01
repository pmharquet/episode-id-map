"""Rate limiters partagés — un singleton par source, thread-safe.

Sans ce module, chaque ingest() crée de nouveaux clients avec un token bucket
neuf (plein), ce qui ne garantit aucun débit agrégé entre appels successifs.
Ces singletons s'assurent que le débit imposé par chaque API est respecté
même quand plusieurs ingests se succèdent (batch ou appels rapides).
"""

from ..ratelimit import RateLimiter

anidb = RateLimiter(0.5, burst=1)   # ≤ 1 req/2 s, ~200 req/24h
simkl = RateLimiter(4.0, burst=4)
jikan = RateLimiter(1.0, burst=3)
tvdb  = RateLimiter(8.0, burst=8)
tmdb  = RateLimiter(4.0, burst=8)
