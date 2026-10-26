#!/bin/bash
# install-obs-auto-record.sh: install (or with --uninstall, remove) the launchd agent that starts
# an OBS recording whenever a Zoom, Google Meet, Teams or similar call is live (see
# obs-auto-record.py).
#
# The agent runs obs-auto-record.py from this checkout, not from the installed plugin, whose
# folder name changes with each version. Re-run after moving the checkout.

set -euo pipefail

LABEL=com.ianmiell.obs-auto-record
HERE="$(cd "$(dirname "$0")" && pwd)"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG="${HOME}/Library/Logs/${LABEL}.log"
DOMAIN="gui/$(id -u)"

launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true

if [[ ${1:-} == --uninstall ]]
then
  rm -f "${PLIST}"
  echo "Removed ${LABEL}. The log (${LOG}) is left in place."
  exit 0
fi

mkdir -p "$(dirname "${PLIST}")" "$(dirname "${LOG}")"
sed -e "s|__SCRIPT__|${HERE}/obs-auto-record.py|" \
    -e "s|__LOG__|${LOG}|g" \
    "${HERE}/${LABEL}.plist" > "${PLIST}"
plutil -lint "${PLIST}"
launchctl bootstrap "${DOMAIN}" "${PLIST}"

echo "Installed ${LABEL}: checking for live calls every 20 seconds, logging to ${LOG}"
echo "OBS needs obs-websocket enabled on port 4455 without authentication."
echo "The first time it checks each browser, macOS asks to allow control of it. Allow it."
