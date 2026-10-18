#!/usr/bin/env bash
# Copy the working tree's integration to a Home Assistant instance over SSH and
# restart it, to try changes before committing. Needs the Terminal & SSH app with
# your public key, port 22 and the `rsync` package (see CLAUDE.md, "Local testing").
#
#   scripts/deploy_local.sh               copy, check the configuration, restart HA
#   scripts/deploy_local.sh --no-restart  copy only (card JS edits: then Cmd+Shift+R)
#
# Env: HA_SSH_HOST (default "ha", an ~/.ssh/config entry), HA_URL (default
# http://192.168.31.105) to wait for after the restart.
set -euo pipefail

HOST="${HA_SSH_HOST:-ha}"
URL="${HA_URL:-http://192.168.31.105}"
SRC="$(cd "$(dirname "$0")/.." && pwd)/custom_components/mykolaiv_outages/"
DEST="/config/custom_components/mykolaiv_outages/"
RESTART=1
[[ "${1:-}" == "--no-restart" ]] && RESTART=0

VERSION="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "${SRC}manifest.json")"
# A new version busts the card's browser cache (?v=) and updates its dashboard
# resource; PEP 440 dev versions are valid manifest versions.
DEV="${VERSION}.dev$(date +%s)"

echo "→ ${HOST}: mykolaiv_outages ${DEV}"
rsync -a --delete --exclude __pycache__ "$SRC" "${HOST}:${DEST}"
ssh "$HOST" "sed -i 's/\"version\": \"[^\"]*\"/\"version\": \"${DEV}\"/' ${DEST}manifest.json"

if (( RESTART == 0 )); then
  echo "Copied without restart: Python changes need a restart, card changes a hard reload."
  exit 0
fi

echo "→ checking the configuration"
ssh "$HOST" "ha core check"
echo "→ restarting Home Assistant"
ssh "$HOST" "ha core restart"
for _ in $(seq 1 60); do
  if curl -s -o /dev/null -m 3 -w '%{http_code}' "$URL/manifest.json" | grep -q 200; then
    echo "✓ Home Assistant is back: ${URL}"
    exit 0
  fi
  sleep 5
done
echo "Home Assistant did not answer within 5 minutes; check the logs." >&2
exit 1
