#!/usr/bin/env bash
# Läuft INNERHALB des Debian-LXC. Installiert/aktualisiert die Transcriber-App.
set -euo pipefail

REPO="${REPO:-https://github.com/eduardo-faith/transcriber.git}"
APP_DIR="/opt/transcriber"
DATA_DIR="/srv/transcriber"
ENV_FILE="/etc/transcriber.env"
SERVICE_FILE="/etc/systemd/system/transcriber.service"

echo ">>> Pakete installieren…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# python3-pip bewusst ausgelassen: dessen Abhängigkeiten (python3-wheel u.a.) sind auf
# manchen Debian-13-Container-Images nicht auflösbar. pip wird stattdessen unten direkt
# in der venv via get-pip.py installiert, unabhängig vom System-apt-Zustand.
apt-get install -y -qq python3 python3-venv ffmpeg git curl >/dev/null

id -u transcriber &>/dev/null || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin transcriber

echo ">>> Quellcode holen…"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone --depth 1 "$REPO" "$APP_DIR"
fi
git config --system --add safe.directory "$APP_DIR"

echo ">>> Python-Umgebung einrichten…"
python3 -m venv --without-pip "$APP_DIR/.venv"
curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
"$APP_DIR/.venv/bin/python" /tmp/get-pip.py -q
rm -f /tmp/get-pip.py
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

mkdir -p "$DATA_DIR/uploads" "$DATA_DIR/results"
chown -R transcriber:transcriber "$DATA_DIR" "$APP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  KEY="${ELEVENLABS_API_KEY:-}"
  if [ -z "$KEY" ]; then
    read -rsp "ElevenLabs API-Key: " KEY; echo
  fi
  cat > "$ENV_FILE" <<EOF
ELEVENLABS_API_KEY=$KEY
DATA_DIR=$DATA_DIR
HOST=0.0.0.0
PORT=8000
STT_MODEL=scribe_v2
DEFAULT_LANGUAGE=deu
DELETE_AUDIO_AFTER=true
MAX_CONCURRENCY=2
MAX_UPLOAD_MB=1024
REQUEST_TIMEOUT=1800
EOF
  chmod 600 "$ENV_FILE"
  echo ">>> $ENV_FILE angelegt."
else
  echo ">>> $ENV_FILE existiert bereits – unverändert."
fi

install -m 0755 "$APP_DIR/scripts/update.sh" /usr/local/bin/update

echo ">>> systemd-Dienst einrichten…"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Transcriber (ElevenLabs Speech-to-Text)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=transcriber
EnvironmentFile=$ENV_FILE
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now transcriber

IP="$(hostname -I | awk '{print $1}')"
echo
echo "============================================================"
echo " Transcriber läuft:  http://${IP}:8000"
echo " Update im Container:  update"
echo "============================================================"
