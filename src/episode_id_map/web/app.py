"""Application FastAPI – interface de visualisation et de contrôle du mapping."""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid as uuidlib
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue

import structlog
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import Settings
from ..db import connect
from ..ingest import ingest as run_ingest
from ..sources.anidb import AniDBBanned
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


# ── Batch import ────────────────────────────────────────────────────────────────

@dataclass
class _BatchJob:
    job_id: str
    mal_ids: list[int]
    total: int
    queue: Queue = field(default_factory=Queue)


_jobs: dict[str, _BatchJob] = {}


_BATCH_INTER_DELAY = 3.0  # secondes entre chaque ingest pour ménager SIMKL


def _run_batch(job: _BatchJob, settings: Settings) -> None:
    """Exécuté dans un thread daemon ; pousse des événements dans job.queue."""
    for idx, mal_id in enumerate(job.mal_ids, start=1):
        if idx > 1:
            time.sleep(_BATCH_INTER_DELAY)
        try:
            stats = run_ingest(mal_id, settings=settings)
            job.queue.put({
                "type": "progress",
                "mal_id": mal_id,
                "status": "ok",
                "processed": idx,
                "total": job.total,
                "percent": round(idx / job.total * 100, 1),
                "groups": stats.get("groups", 0),
                "rows": stats.get("rows", 0),
            })
        except AniDBBanned as exc:
            log.error("batch.anidb_banned", mal_id=mal_id)
            job.queue.put({
                "type": "progress",
                "mal_id": mal_id,
                "status": "error",
                "processed": idx,
                "total": job.total,
                "percent": round(idx / job.total * 100, 1),
                "error": str(exc),
            })
            job.queue.put({"type": "banned", "source": "AniDB", "processed": idx, "total": job.total})
            return
        except Exception as exc:  # noqa: BLE001
            job.queue.put({
                "type": "progress",
                "mal_id": mal_id,
                "status": "error",
                "processed": idx,
                "total": job.total,
                "percent": round(idx / job.total * 100, 1),
                "error": str(exc),
            })
    job.queue.put({"type": "done", "total": job.total})


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
        return _r(request, "partials/ingest_result.html",
                  {"success": False, "error": str(exc), "mal_id": mal_id})


# ── Import JSON (batch) ─────────────────────────────────────────────────────────

@app.post("/ingest/json")
async def ingest_json(file: UploadFile = File(...)) -> JSONResponse:
    content = await file.read()
    try:
        data = json.loads(content)
        mal_ids_raw = data.get("mal_ids")
        if not isinstance(mal_ids_raw, list):
            raise ValueError('"mal_ids" doit être une liste')
        mal_ids = [int(x) for x in mal_ids_raw]
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    s = _get_settings()
    with connect(s) as conn:
        already = queries.get_mapped_mal_ids(conn)

    to_process = [x for x in mal_ids if x not in already]
    already_mapped = len(mal_ids) - len(to_process)

    if not to_process:
        return JSONResponse({
            "job_id": None,
            "total": len(mal_ids),
            "to_process": 0,
            "already_mapped": already_mapped,
        })

    job_id = str(uuidlib.uuid4())
    job = _BatchJob(job_id=job_id, mal_ids=to_process, total=len(to_process))
    _jobs[job_id] = job

    threading.Thread(target=_run_batch, args=(job, s), daemon=True).start()
    log.info("batch.started", job_id=job_id, to_process=len(to_process), skipped=already_mapped)

    return JSONResponse({
        "job_id": job_id,
        "total": len(mal_ids),
        "to_process": len(to_process),
        "already_mapped": already_mapped,
    })


@app.get("/ingest/batch/{job_id}/stream")
async def stream_batch(job_id: str) -> StreamingResponse:
    job = _jobs.get(job_id)
    if job is None:
        return JSONResponse({"error": "Job introuvable"}, status_code=404)

    async def event_gen():
        try:
            while True:
                try:
                    event = job.queue.get_nowait()
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") in ("done", "banned"):
                        _jobs.pop(job_id, None)
                        return
                except Empty:
                    await asyncio.sleep(0.3)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
