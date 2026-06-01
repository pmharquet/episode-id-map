"""Rate limiters partagés — un singleton par source, thread-safe.

Sans ce module, chaque ingest() crée de nouveaux clients avec un token bucket
neuf (plein), ce qui ne garantit aucun débit agrégé entre appels successifs.
Ces singletons s'assurent que le débit imposé par chaque API est respecté
même quand plusieurs ingests se succèdent (batch ou appels rapides).
"""

from ..ratelimit import RateLimiter

anidb = RateLimiter(0.5, burst=1, name="AniDB", daily_limit=200)
simkl = RateLimiter(4.0, burst=4, name="SIMKL", daily_limit=1000)
jikan = RateLimiter(1.0, burst=3, name="Jikan")
tvdb  = RateLimiter(8.0, burst=8, name="TVDB")
tmdb  = RateLimiter(4.0, burst=8, name="TMDB")
