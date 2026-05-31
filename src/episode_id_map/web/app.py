"""Application FastAPI – interface de visualisation et de contrôle du mapping."""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import Settings
from ..db import connect
from ..ingest import ingest as run_ingest
from . import queries

log = structlog.get_logger()

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Episode ID Map")
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

_settings: Settings | None = None


def _get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def _r(request: Request, name: str, ctx: dict) -> HTMLResponse:
    """Wrapper pour la nouvelle signature TemplateResponse de Starlette 1.x."""
    return templates.TemplateResponse(request=request, name=name, context=ctx)


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    s = _get_settings()
    with connect(s) as conn:
        stats = queries.get_stats(conn)
        series_list = queries.get_series_list(conn)
    return _r(request, "index.html", {"stats": stats, "series_list": series_list})


@app.get("/episodes", response_class=HTMLResponse)
def episodes(request: Request, mal_series: str = "") -> HTMLResponse:
    s = _get_settings()
    with connect(s) as conn:
        series_list = queries.get_series_list(conn)
        groups = queries.get_episodes(conn, mal_series)
    return _r(request, "episodes.html", {
        "series_list": series_list,
        "selected": mal_series,
        "groups": groups,
    })


# ── Partials HTMX ──────────────────────────────────────────────────────────────

@app.get("/partials/episodes-table", response_class=HTMLResponse)
def episodes_table(request: Request, mal_series: str = "") -> HTMLResponse:
    s = _get_settings()
    with connect(s) as conn:
        groups = queries.get_episodes(conn, mal_series)
    return _r(request, "partials/episodes_table.html", {"groups": groups})


@app.get("/partials/series-list", response_class=HTMLResponse)
def series_list_partial(request: Request) -> HTMLResponse:
    s = _get_settings()
    with connect(s) as conn:
        series_list = queries.get_series_list(conn)
    return _r(request, "partials/series_list.html", {"series_list": series_list})


@app.post("/rows/delete-group", response_class=HTMLResponse)
def delete_group(episode_absolute: str = Form(...)) -> HTMLResponse:
    s = _get_settings()
    with connect(s) as conn:
        queries.delete_group(conn, episode_absolute)
    return HTMLResponse("")   # la <tr> est remplacée par rien → disparaît


@app.post("/rows/delete", response_class=HTMLResponse)
def delete_row(
    request: Request,
    uuid: str = Form(...),
    episode_absolute: str = Form(...),
) -> HTMLResponse:
    s = _get_settings()
    with connect(s) as conn:
        queries.delete_row(conn, uuid)
        group = queries.get_group(conn, episode_absolute)
    if group is None:
        # Toutes les lignes du groupe supprimées → ligne vide
        return HTMLResponse(
            f'<tr id="r-{episode_absolute[:8]}">'
            '<td colspan="8" style="color:var(--pico-muted-color);font-style:italic">'
            "Groupe supprimé</td></tr>"
        )
    return _r(request, "partials/row.html", {"g": group})


@app.post("/ingest", response_class=HTMLResponse)
def do_ingest(request: Request, mal_id: int = Form(...)) -> HTMLResponse:
    s = _get_settings()
    try:
        stats = run_ingest(mal_id, settings=s)
        log.info("web.ingest.ok", mal_id=mal_id, **stats)
        return _r(request, "partials/ingest_result.html",
                  {"success": True, "stats": stats, "mal_id": mal_id})
    except Exception as exc:  # noqa: BLE001
        log.warning("web.ingest.error", mal_id=mal_id, error=str(exc))
        return templates.TemplateResponse(
            request=request,
            name="partials/ingest_result.html",
            context={"success": False, "error": str(exc), "mal_id": mal_id},
            status_code=422,
        )
