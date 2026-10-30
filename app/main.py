"""FastAPI-App: Web-Oberfläche + REST-API für Gesprächstranskription."""
import asyncio
import json
import os
import re
import shutil
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__, config, db, worker

BASE_DIR = Path(__file__).resolve().parent

ALLOWED_EXT = {
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".webm", ".aac", ".aiff", ".aif",
    ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".mpeg", ".mpg", ".3gp",
}

RESULT_FILES = {
    "json": ("transcript.json", "application/json"),
    "txt": ("transcript.txt", "text/plain; charset=utf-8"),
    "srt": ("transcript.srt", "application/x-subrip"),
    "vtt": ("transcript.vtt", "text/vtt; charset=utf-8"),
    "raw": ("transcript.raw.json", "application/json"),
}

app = FastAPI(title="Transcriber", version=__version__)
_background_tasks = set()
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["mmss"] = lambda s: f"{int(s or 0) // 60:02d}:{int(s or 0) % 60:02d}"


@app.on_event("startup")
def _startup():
    db.init_db()


def _safe_name(name):
    name = os.path.basename(name or "audio")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name or "audio"


async def _handle_upload(file: UploadFile, language, num_speakers):
    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in ALLOWED_EXT:
        raise HTTPException(400, f"Nicht unterstütztes Format: {extension or 'unbekannt'}")

    job_id = uuid.uuid4().hex
    upload_dir = config.UPLOAD_DIR / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_name(file.filename)
    destination = upload_dir / filename

    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    with open(destination, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                out.close()
                shutil.rmtree(upload_dir, ignore_errors=True)
                raise HTTPException(413, f"Datei größer als erlaubt ({config.MAX_UPLOAD_MB} MB).")
            out.write(chunk)

    language = (language or "").strip()
    speakers = None
    if num_speakers is not None and str(num_speakers).strip():
        try:
            speakers = max(1, min(32, int(num_speakers)))
        except ValueError:
            speakers = None

    result_dir = str(config.RESULTS_DIR / job_id)
    db.create_job(job_id, filename, language, speakers, result_dir)
    task = asyncio.create_task(worker.process_job(job_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return job_id


def _require_job(job_id):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job nicht gefunden.")
    return job


# ---------------------------------------------------------------- Web-UI

@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "jobs": db.list_jobs(),
            "default_language": config.DEFAULT_LANGUAGE,
            "version": __version__,
        },
    )


@app.post("/ui/upload")
async def ui_upload(
    file: UploadFile = File(...),
    language: str = Form(""),
    num_speakers: str = Form(""),
):
    job_id = await _handle_upload(file, language, num_speakers)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.get("/jobs/{job_id}")
def job_page(request: Request, job_id: str):
    job = _require_job(job_id)
    transcript = None
    segments = []
    speakers = []
    if job["status"] == "done":
        data = json.loads((Path(job["result_dir"]) / "transcript.json").read_text(encoding="utf-8"))
        order = []
        for segment in data["segments"]:
            if segment["speaker_id"] not in order:
                order.append(segment["speaker_id"])
        color = {sid: idx % 8 for idx, sid in enumerate(order)}
        segments = [{**s, "color_idx": color[s["speaker_id"]]} for s in data["segments"]]
        names = data.get("speakers", {})
        speakers = [
            {"id": sid, "name": names.get(sid, sid), "color_idx": color[sid]} for sid in order
        ]
        transcript = data
    return templates.TemplateResponse(
        request,
        "job.html",
        {
            "job": job,
            "transcript": transcript,
            "segments": segments,
            "speakers": speakers,
        },
    )


@app.post("/ui/jobs/{job_id}/speakers")
async def ui_rename(request: Request, job_id: str):
    job = _require_job(job_id)
    form = await request.form()
    overrides = {
        key[len("name_"):]: value.strip()
        for key, value in form.items()
        if key.startswith("name_") and value.strip()
    }
    worker.regenerate(job, overrides)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.post("/ui/jobs/{job_id}/delete")
def ui_delete(job_id: str):
    _delete(job_id)
    return RedirectResponse("/", status_code=303)


# ---------------------------------------------------------------- REST-API

@app.post("/api/transcriptions", status_code=201)
async def api_create(
    file: UploadFile = File(...),
    language: str = Form(""),
    num_speakers: str = Form(""),
):
    job_id = await _handle_upload(file, language, num_speakers)
    return {"id": job_id, "status": "queued"}


@app.get("/api/transcriptions")
def api_list():
    return db.list_jobs()


@app.get("/api/transcriptions/{job_id}")
def api_get(job_id: str):
    return _require_job(job_id)


@app.get("/api/transcriptions/{job_id}/result")
def api_result(job_id: str, format: str = "json", download: bool = False):
    job = _require_job(job_id)
    if job["status"] != "done":
        raise HTTPException(409, f"Job ist nicht fertig (Status: {job['status']}).")
    if format not in RESULT_FILES:
        raise HTTPException(400, f"Unbekanntes Format: {format}")
    filename, media_type = RESULT_FILES[format]
    path = Path(job["result_dir"]) / filename
    if not path.exists():
        raise HTTPException(404, "Ergebnisdatei nicht gefunden.")
    headers = {}
    if download:
        suffix = "raw.json" if format == "raw" else format
        headers["Content-Disposition"] = f'attachment; filename="{job_id}.{suffix}"'
    return FileResponse(path, media_type=media_type, headers=headers)


@app.post("/api/transcriptions/{job_id}/speakers")
def api_rename(job_id: str, overrides: dict = Body(...)):
    job = _require_job(job_id)
    if job["status"] != "done":
        raise HTTPException(409, "Job ist noch nicht fertig.")
    clean = {str(k): str(v) for k, v in overrides.items() if str(v).strip()}
    return JSONResponse(worker.regenerate(job, clean))


def _delete(job_id):
    job = _require_job(job_id)
    shutil.rmtree(config.UPLOAD_DIR / job_id, ignore_errors=True)
    shutil.rmtree(Path(job["result_dir"]), ignore_errors=True)
    db.delete_job(job_id)


@app.delete("/api/transcriptions/{job_id}")
def api_delete(job_id: str):
    _delete(job_id)
    return {"deleted": job_id}


@app.get("/health")
def health():
    return {"status": "ok", "version": __version__, "api_key_configured": bool(config.ELEVENLABS_API_KEY)}
