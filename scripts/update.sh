#!/usr/bin/env bash
# Im Container als 'update' aufrufbar. Holt die neueste Version und startet neu.
set -euo pipefail

APP_DIR="/opt/transcriber"

if [ ! -d "$APP_DIR/.git" ]; then
  echo "Keine Installation unter $APP_DIR gefunden." >&2
  exit 1
fi

echo ">>> Aktualisiere Transcriber…"
CURRENT="$(git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || echo '?')"
git -C "$APP_DIR" fetch --quiet origin
git -C "$APP_DIR" pull --ff-only --quiet
NEW="$(git -C "$APP_DIR" rev-parse --short HEAD)"

if [ "$CURRENT" = "$NEW" ]; then
  echo ">>> Bereits aktuell ($CURRENT)."
else
  echo ">>> Update: $CURRENT -> $NEW"
fi

"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
chown -R transcriber:transcriber "$APP_DIR"
systemctl restart transcriber
echo ">>> Dienst neu gestartet."
systemctl --no-pager --lines=0 status transcriber | head -3 || true
