# Transcriber

Selbst gehostete App zur **Gesprächstranskription mit Sprecherzuordnung**.
Audiodatei hochladen → ElevenLabs Speech-to-Text (Scribe v2, Diarisierung) →
Transkript mit zugeordneten Sprechern, abrufbar über **Web-Oberfläche** und **REST-API**.

Gedacht für einen Debian-LXC auf Proxmox, Betrieb **nur im LAN** (keine Authentifizierung).

## Installation auf Proxmox (eine Zeile)

Auf dem **Proxmox-Host** ausführen – legt einen Debian-12-LXC an und installiert alles:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/eduardo-faith/transcriber/main/ct/transcriber.sh)"
```

Das Skript fragt den ElevenLabs-API-Key ab und zeigt am Ende die URL `http://<container-ip>:8000`.

Anpassbar durch vorheriges Exportieren von Variablen, z. B.:

```bash
CORES=4 RAM=4096 DISK=16 bash -c "$(curl -fsSL .../ct/transcriber.sh)"
```

## Aktualisieren

Im Container einfach:

```bash
update
```

(holt die neueste Version, installiert Abhängigkeiten, startet den Dienst neu). Vom Host aus: `pct exec <CTID> -- update`.

## Nutzung

- **Web:** `http://<container-ip>:8000` – Datei hochladen, optional Sprache und Sprecheranzahl wählen (leer = automatisch), Ergebnis mit farblich getrennten Sprechern ansehen, Sprecher umbenennen, Downloads als TXT/JSON/SRT/VTT.
- **API-Doku (Swagger):** `http://<container-ip>:8000/docs`

### REST-API

| Methode | Pfad | Zweck |
|---|---|---|
| `POST` | `/api/transcriptions` | Multipart-Upload (`file`, optional `language`, `num_speakers`) → `{id, status}` |
| `GET` | `/api/transcriptions` | Jobs auflisten |
| `GET` | `/api/transcriptions/{id}` | Status + Metadaten |
| `GET` | `/api/transcriptions/{id}/result?format=json\|txt\|srt\|vtt\|raw&download=1` | Ergebnis |
| `POST` | `/api/transcriptions/{id}/speakers` | Sprecher umbenennen (JSON `{ "speaker_0": "Anna" }`) |
| `DELETE` | `/api/transcriptions/{id}` | Job + Dateien löschen |
| `GET` | `/health` | Health-Check |

Beispiel:

```bash
curl -F "file=@gespraech.mp3" -F "language=deu" -F "num_speakers=2" \
  http://<container-ip>:8000/api/transcriptions
```

## Konfiguration

Über `/etc/transcriber.env` (siehe `.env.example`): API-Key, Datenpfad, Modell,
Standardsprache, Audio-Löschung nach Transkription, Upload-Limit, Timeout, Parallelität.

## Lokal starten (Entwicklung)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export ELEVENLABS_API_KEY=... DATA_DIR=./data
uvicorn app.main:app --reload
```

## Hinweise

- Audios werden nach **erfolgreicher** Transkription gelöscht (`DELETE_AUDIO_AFTER=true`); nur die Transkripte bleiben.
- ElevenLabs rechnet pro Audiostunde ab (auch Stille zählt). Grenzen: bis 10 h / 3 GB pro Datei.
