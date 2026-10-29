#!/usr/bin/env bash
# Im Container als 'update' aufrufbar. Aktualisiert Debian-Pakete UND die App.
set -euo pipefail

APP_DIR="/opt/transcriber"

echo ">>> Debian-Pakete aktualisieren…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get -y -qq full-upgrade
apt-get -y -qq autoremove

if [ ! -d "$APP_DIR/.git" ]; then
  echo "Keine App-Installation unter $APP_DIR gefunden." >&2
  exit 1
fi

echo ">>> App aktualisieren…"
CURRENT="$(git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || echo '?')"
git -C "$APP_DIR" fetch --quiet origin
git -C "$APP_DIR" pull --ff-only --quiet
NEW="$(git -C "$APP_DIR" rev-parse --short HEAD)"

if [ "$CURRENT" = "$NEW" ]; then
  echo ">>> App bereits aktuell ($CURRENT)."
else
  echo ">>> App-Update: $CURRENT -> $NEW"
fi

"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
chown -R transcriber:transcriber "$APP_DIR"

systemctl restart transcriber
echo ">>> Dienst neu gestartet."
systemctl --no-pager --lines=0 status transcriber | head -3 || true
