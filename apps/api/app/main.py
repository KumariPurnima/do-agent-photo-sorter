from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import BasicAuthMiddleware
from .config import get_settings
from .harness import create_job, get_job, job_status_payload, list_jobs, refresh_job
from .spaces import create_album_id, list_sorted, presign_get, presign_upload

ROOT = Path(__file__).resolve().parents[3]
WEB_DIST = ROOT / "apps" / "web"

app = FastAPI(title="Agent Photo Sorter", version="0.1.0")
app.add_middleware(BasicAuthMiddleware)


class AlbumCreate(BaseModel):
    name: str = "Untitled album"


class PresignRequest(BaseModel):
    album_id: str
    filename: str
    content_type: str | None = None


class SortRequest(BaseModel):
    album_id: str
    prompt: str | None = None


class MoveRequest(BaseModel):
    album_id: str
    key: str
    to_folder: str = Field(min_length=1)


@app.get("/api/health")
def health():
    settings = get_settings()
    return {
        "ok": True,
        "app": settings.app_name,
        "demo_mode": settings.demo_mode or not settings.digitalocean_token,
        "spaces_configured": bool(settings.spaces_bucket and settings.spaces_key),
    }


@app.get("/api/categories")
def categories():
    path = ROOT / "categories.json"
    return json.loads(path.read_text())


@app.post("/api/albums")
def create_album(body: AlbumCreate):
    album_id = create_album_id()
    return {"album_id": album_id, "name": body.name, "prefix": f"albums/{album_id}"}


@app.post("/api/uploads/presign")
def uploads_presign(body: PresignRequest):
    settings = get_settings()
    if settings.demo_mode and not (settings.spaces_bucket and settings.spaces_key):
        # Local demo without Spaces: client keeps files in-browser only.
        return {
            "demo": True,
            "upload_url": None,
            "key": f"albums/{body.album_id}/inbox/{body.filename}",
            "content_type": body.content_type or "application/octet-stream",
        }
    try:
        return {"demo": False, **presign_upload(body.album_id, body.filename, body.content_type)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sort")
def start_sort(body: SortRequest):
    job = create_job(body.album_id, body.prompt)
    return job_status_payload(job)


@app.get("/api/jobs")
def jobs():
    return {"jobs": list_jobs()}


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    found = get_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_status_payload(found)


@app.post("/api/jobs/{job_id}/refresh")
def job_refresh(job_id: str):
    found = refresh_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_status_payload(found)


@app.get("/api/albums/{album_id}/sorted")
def album_sorted(album_id: str):
    settings = get_settings()
    items = list_sorted(album_id)
    for item in items:
        if settings.spaces_bucket and settings.spaces_key:
            item["url"] = presign_get(item["key"])
        else:
            item["url"] = None
    folders: dict[str, list] = {}
    for item in items:
        folders.setdefault(item["folder"], []).append(item)
    return {"album_id": album_id, "folders": folders, "count": len(items)}


@app.get("/")
def index():
    index_path = WEB_DIST / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Web UI missing")
    return FileResponse(index_path)


if WEB_DIST.exists():
    assets = WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    app.mount("/static", StaticFiles(directory=WEB_DIST), name="static")
