"""Asynchrone Job-Verarbeitung: ruft ElevenLabs auf und schreibt die Ergebnisse."""
import asyncio
import json
import shutil
from pathlib import Path

from . import config, db, elevenlabs, formats, segmentation

_semaphore = None


def _get_semaphore():
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY)
    return _semaphore


def _write_all(result_dir, segments, labels, overrides, meta):
    result_path = Path(result_dir)
    result_path.mkdir(parents=True, exist_ok=True)
    structured = formats.to_structured(segments, labels, overrides, meta)
    (result_path / "transcript.json").write_text(
        json.dumps(structured, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (result_path / "transcript.txt").write_text(
        formats.to_txt(segments, labels, overrides), encoding="utf-8"
    )
    (result_path / "transcript.srt").write_text(
        formats.to_srt(segments, labels, overrides), encoding="utf-8"
    )
    (result_path / "transcript.vtt").write_text(
        formats.to_vtt(segments, labels, overrides), encoding="utf-8"
    )
    (result_path / "overrides.json").write_text(
        json.dumps(overrides, ensure_ascii=False), encoding="utf-8"
    )
    return structured


def _do_job(job):
    job_id = job["id"]
    audio_path = config.UPLOAD_DIR / job_id / job["filename"]
    api_response = elevenlabs.transcribe(
        audio_path, language=job.get("language"), num_speakers=job.get("num_speakers")
    )

    result_path = Path(job["result_dir"])
    result_path.mkdir(parents=True, exist_ok=True)
    (result_path / "transcript.raw.json").write_text(
        json.dumps(api_response, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    duration = api_response.get("audio_duration_secs")
    meta = {
        "job_id": job_id,
        "filename": job["filename"],
        "model": config.STT_MODEL,
        "language_requested": job.get("language") or "auto",
        "language_detected": api_response.get("language_code"),
        "duration_secs": duration,
    }
    segments, labels = segmentation.build_segments(api_response)
    _write_all(job["result_dir"], segments, labels, {}, meta)

    db.update_job(job_id, status="done", duration_secs=duration, error_message=None)

    if config.DELETE_AUDIO_AFTER:
        shutil.rmtree(config.UPLOAD_DIR / job_id, ignore_errors=True)


async def process_job(job_id):
    async with _get_semaphore():
        job = db.get_job(job_id)
        if not job:
            return
        db.update_job(job_id, status="processing")
        try:
            await asyncio.to_thread(_do_job, job)
        except Exception as exc:  # noqa: BLE001 - Fehler landet im Job-Status
            db.update_job(job_id, status="error", error_message=str(exc))


def regenerate(job, overrides):
    """Erzeugt alle Formate neu, z. B. nach dem Umbenennen von Sprechern."""
    result_path = Path(job["result_dir"])
    api_response = json.loads((result_path / "transcript.raw.json").read_text(encoding="utf-8"))
    existing = json.loads((result_path / "transcript.json").read_text(encoding="utf-8"))
    meta = existing.get("metadata", {})
    segments, labels = segmentation.build_segments(api_response)
    return _write_all(job["result_dir"], segments, labels, overrides or {}, meta)
