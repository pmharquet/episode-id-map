"""AniDB (httpapi) — `source = "ANIDB"`.

⚠ Politique de ban agressive : ≤ 1 req / 2 s, CACHE DISQUE OBLIGATOIRE, ~200 req/24h.
Les erreurs reviennent en HTTP 200 dans `<error code=…>` → on parse le corps. Un ban
(`<error>banned</error>`) est FATAL : on ne retente pas (cela aggraverait le ban).
Réponses XML (parfois gzip, décompressé par httpx). Cf. docs/apis/anidb.md.
"""

from __future__ import annotations

import time
from pathlib import Path
from xml.etree import ElementTree as ET

from ..client import BaseClient
from ..config import Settings
from . import limiters


class AniDBError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"AniDB error {code}: {message}")
        self.code = code
        self.message = message


class AniDBBanned(AniDBError):
    """Ban détecté → arrêter immédiatement toute requête AniDB."""


class AniDBClient(BaseClient):
    source = "ANIDB"

    def __init__(
        self,
        settings: Settings,
        *,
        cache_dir: str | Path = "cache/anidb",
        cache_ttl_days: float = 7.0,
    ) -> None:
        if not settings.anidb_client or not settings.anidb_clientver:
            raise RuntimeError("ANIDB_CLIENT / ANIDB_CLIENTVER manquants dans .env")
        # ≤ 1 req / 2 s → rate=0.5, aucune pointe.
        super().__init__(settings.anidb_base_url, rate=0.5, burst=1, max_attempts=2,
                         limiter=limiters.anidb)
        self._name = settings.anidb_client
        self._ver = settings.anidb_clientver
        self._cache = Path(cache_dir)
        self._cache.mkdir(parents=True, exist_ok=True)
        self._ttl = cache_ttl_days * 86400.0

    def _cache_path(self, aid: int) -> Path:
        return self._cache / f"anime-{aid}.xml"

    def get_anime_xml(self, aid: int, *, force: bool = False) -> str:
        """XML brut d'un anime, servi depuis le cache si frais (anti-ban)."""
        path = self._cache_path(aid)
        if (
            not force
            and path.exists()
            and (time.time() - path.stat().st_mtime) < self._ttl
        ):
            self._log.info("anidb.cache_hit", aid=aid)
            return path.read_text(encoding="utf-8")

        params = {
            "request": "anime",
            "client": self._name,
            "clientver": self._ver,
            "protover": 1,
            "aid": aid,
        }
        text = self.request("GET", "", params=params).text
        root = ET.fromstring(text)
        if root.tag == "error":
            message = (root.text or "").strip()
            if "ban" in message.lower():
                raise AniDBBanned(root.attrib.get("code", "?"), message)
            raise AniDBError(root.attrib.get("code", "?"), message)

        path.write_text(text, encoding="utf-8")
        self._log.info("anidb.fetched", aid=aid)
        return text

    def get_anime(self, aid: int, *, force: bool = False) -> ET.Element:
        return ET.fromstring(self.get_anime_xml(aid, force=force))

    @staticmethod
    def regular_episodes(root: ET.Element) -> list[dict[str, str]]:
        """Épisodes réguliers (`epno type=1`) : epid / epno / airdate / titres."""
        out: list[dict[str, str]] = []
        for ep in root.findall("./episodes/episode"):
            epno = ep.find("epno")
            if epno is None or epno.get("type") != "1":
                continue
            titles = {t.get("{http://www.w3.org/XML/1998/namespace}lang"): (t.text or "")
                      for t in ep.findall("title")}
            airdate = ep.find("airdate")
            out.append(
                {
                    "epid": ep.get("id", ""),
                    "epno": epno.text or "",
                    "airdate": airdate.text if airdate is not None else "",
                    "title_en": titles.get("en", ""),
                    "title_fr": titles.get("fr", ""),
                }
            )
        return out
