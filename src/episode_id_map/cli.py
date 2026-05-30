"""CLI de test des fetchers (ÉTAPE 3).

Chaque commande exerce un client sur un cas réel et affiche un résumé + un extrait.
Exemples :
    python -m episode_id_map.cli jikan 52991
    python -m episode_id_map.cli tmdb 209867
    python -m episode_id_map.cli simkl --anidb 17617
    python -m episode_id_map.cli tvdb 424536
    python -m episode_id_map.cli anidb 17617
"""

from __future__ import annotations

import json
from typing import Any

import typer

from . import logging as logmod
from .config import Settings
from .sources.anidb import AniDBClient
from .sources.jikan import JikanClient
from .sources.simkl import SimklClient
from .sources.tmdb import TMDBClient
from .sources.tvdb import TVDBClient

app = typer.Typer(add_completion=False, help="Fetchers episode_id_map (ÉTAPE 3).")


def _dump(obj: Any, limit: int | None = 3) -> None:
    if isinstance(obj, list) and limit is not None:
        typer.echo(f"({len(obj)} éléments — extrait des {min(limit, len(obj))} premiers)")
        obj = obj[:limit]
    typer.echo(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


@app.command()
def jikan(mal_id: int, resource: str = "episodes") -> None:
    """resource = episodes | anime | external"""
    logmod.configure()
    with JikanClient(Settings.load()) as c:
        if resource == "episodes":
            _dump(list(c.iter_episodes(mal_id)))
        elif resource == "anime":
            _dump(c.get_anime(mal_id), limit=None)
        elif resource == "external":
            _dump(c.get_external(mal_id), limit=None)
        else:
            raise typer.BadParameter("resource ∈ {episodes, anime, external}")


@app.command()
def tmdb(tv_id: int, resource: str = "episodes") -> None:
    """resource = episodes | tv | external"""
    logmod.configure()
    with TMDBClient(Settings.load()) as c:
        if resource == "episodes":
            _dump(list(c.iter_episodes(tv_id)))
        elif resource == "tv":
            _dump(c.get_tv(tv_id), limit=None)
        elif resource == "external":
            _dump(c.get_tv_external_ids(tv_id), limit=None)
        else:
            raise typer.BadParameter("resource ∈ {episodes, tv, external}")


@app.command()
def simkl(
    simkl_id: int = typer.Argument(0),
    anidb: int = typer.Option(0),
    mal: int = typer.Option(0),
) -> None:
    """Soit un simkl_id (épisodes), soit --anidb/--mal (lookup)."""
    logmod.configure()
    with SimklClient(Settings.load()) as c:
        if anidb:
            _dump(c.search_id(anidb=anidb), limit=None)
        elif mal:
            _dump(c.search_id(mal=mal), limit=None)
        elif simkl_id:
            _dump(c.get_episodes(simkl_id))
        else:
            raise typer.BadParameter("fournir simkl_id, --anidb ou --mal")


@app.command()
def tvdb(series_id: int, resource: str = "episodes") -> None:
    """resource = episodes | series"""
    logmod.configure()
    with TVDBClient(Settings.load()) as c:
        if resource == "episodes":
            _dump(list(c.iter_episodes(series_id)))
        elif resource == "series":
            _dump(c.get_series_extended(series_id), limit=None)
        else:
            raise typer.BadParameter("resource ∈ {episodes, series}")


@app.command()
def anidb(aid: int, force: bool = False) -> None:
    """Anime AniDB (servi depuis le cache si frais)."""
    logmod.configure()
    with AniDBClient(Settings.load()) as c:
        root = c.get_anime(aid, force=force)
        episodes = c.regular_episodes(root)
        typer.echo(f"{len(episodes)} épisodes réguliers (type=1)")
        _dump(episodes)


if __name__ == "__main__":
    app()
