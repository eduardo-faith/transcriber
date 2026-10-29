"""Konfiguration aus Umgebungsvariablen (siehe .env.example)."""
import os
from pathlib import Path


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


DATA_DIR = Path(os.getenv("DATA_DIR", "/srv/transcriber"))
UPLOAD_DIR = DATA_DIR / "uploads"
RESULTS_DIR = DATA_DIR / "results"
DB_PATH = DATA_DIR / "transcriber.db"

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_URL = os.getenv("ELEVENLABS_URL", "https://api.elevenlabs.io/v1/speech-to-text")
STT_MODEL = os.getenv("STT_MODEL", "scribe_v2")

DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "deu")
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "2"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "1800"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024"))
DELETE_AUDIO_AFTER = _bool(os.getenv("DELETE_AUDIO_AFTER"), True)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))


def ensure_dirs():
    for directory in (DATA_DIR, UPLOAD_DIR, RESULTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
