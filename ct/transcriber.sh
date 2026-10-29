#!/usr/bin/env bash
# Läuft auf dem PROXMOX-HOST. Legt einen Debian-12-LXC an und installiert die App.
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/eduardo-faith/transcriber/main/ct/transcriber.sh)"
#
# Überschreibbare Variablen (vorweg exportieren): CTID HOSTNAME DISK CORES RAM
#   BRIDGE STORAGE TEMPLATE_STORAGE ELEVENLABS_API_KEY
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/eduardo-faith/transcriber/main"

CTID="${CTID:-$(pvesh get /cluster/nextid)}"
HOSTNAME="${HOSTNAME:-transcriber}"
DISK="${DISK:-8}"
CORES="${CORES:-2}"
RAM="${RAM:-2048}"
BRIDGE="${BRIDGE:-vmbr0}"
STORAGE="${STORAGE:-local-lvm}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local}"

command -v pct >/dev/null 2>&1 || { echo "Dieses Skript muss auf einem Proxmox-Host laufen (pct fehlt)." >&2; exit 1; }

echo ">>> Debian-12-Template sicherstellen…"
pveam update >/dev/null 2>&1 || true
TEMPLATE="$(pveam available --section system | awk '{print $2}' | grep '^debian-12-standard' | sort -V | tail -1)"
if [ -z "$TEMPLATE" ]; then
  echo "Kein Debian-12-Template verfügbar (pveam available)." >&2; exit 1
fi
if ! pveam list "$TEMPLATE_STORAGE" 2>/dev/null | grep -q "$TEMPLATE"; then
  echo ">>> Lade $TEMPLATE…"
  pveam download "$TEMPLATE_STORAGE" "$TEMPLATE"
fi

read -rsp "ElevenLabs API-Key: " ELEVENLABS_API_KEY; echo
export ELEVENLABS_API_KEY

echo ">>> Erstelle LXC $CTID ($HOSTNAME)…"
pct create "$CTID" "${TEMPLATE_STORAGE}:vztmpl/${TEMPLATE}" \
  --hostname "$HOSTNAME" \
  --cores "$CORES" \
  --memory "$RAM" \
  --rootfs "${STORAGE}:${DISK}" \
  --net0 "name=eth0,bridge=${BRIDGE},ip=dhcp" \
  --unprivileged 1 \
  --features nesting=1 \
  --onboot 1

pct start "$CTID"

echo ">>> Warte auf Netzwerk im Container…"
for _ in $(seq 1 30); do
  if pct exec "$CTID" -- bash -c "getent hosts github.com >/dev/null 2>&1"; then break; fi
  sleep 2
done

echo ">>> Installiere App im Container…"
pct exec "$CTID" -- bash -c "apt-get update -qq && apt-get install -y -qq curl >/dev/null"
pct exec "$CTID" -- bash -c "ELEVENLABS_API_KEY='${ELEVENLABS_API_KEY}' bash -c \"\$(curl -fsSL ${REPO_RAW}/install/transcriber-install.sh)\""

IP="$(pct exec "$CTID" -- hostname -I | awk '{print $1}')"
echo
echo "============================================================"
echo " Fertig. LXC $CTID ($HOSTNAME)"
echo " Web-UI:  http://${IP}:8000"
echo " Update:  pct exec $CTID -- update"
echo "============================================================"
