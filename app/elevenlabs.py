"""Client für die ElevenLabs Speech-to-Text-API (Scribe) mit Diarisierung."""
import httpx

from . import config


class TranscriptionError(Exception):
    """Fehler beim Transkribieren über ElevenLabs."""


def transcribe(audio_path, language=None, num_speakers=None):
    if not config.ELEVENLABS_API_KEY:
        raise TranscriptionError("ELEVENLABS_API_KEY ist nicht gesetzt.")

    data = {
        "model_id": config.STT_MODEL,
        "diarize": "true",
        "timestamps_granularity": "word",
        "tag_audio_events": "true",
    }
    if language and str(language).strip().lower() not in ("", "auto"):
        data["language_code"] = str(language).strip()
    if num_speakers:
        data["num_speakers"] = str(int(num_speakers))

    headers = {"xi-api-key": config.ELEVENLABS_API_KEY}

    try:
        with open(audio_path, "rb") as handle:
            files = {"file": (audio_path.name, handle, "application/octet-stream")}
            response = httpx.post(
                config.ELEVENLABS_URL,
                headers=headers,
                data=data,
                files=files,
                timeout=config.REQUEST_TIMEOUT,
            )
    except httpx.HTTPError as exc:
        raise TranscriptionError(f"Netzwerkfehler bei ElevenLabs: {exc}") from exc

    if response.status_code >= 400:
        raise TranscriptionError(
            f"ElevenLabs antwortete mit {response.status_code}: {response.text[:500]}"
        )
    return response.json()
