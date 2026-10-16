#!/bin/bash
# install-linkedin-sync.sh: install (or with --uninstall, remove) the launchd agent that opens
# /personal-assistant:linkedin-sync in iTerm2 every Monday at 08:30. Run it now with
#   launchctl kickstart gui/$(id -u)/com.ianmiell.linkedin-sync
#
# The agent runs linkedin-sync.sh from this checkout, not from the installed plugin, whose folder
# name changes with each version. Re-run after moving the checkout.

set -euo pipefail

LABEL=com.ianmiell.linkedin-sync
HERE="$(cd "$(dirname "$0")" && pwd)"
GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"
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

if [[ ! -d ${GTD_DIR}/people ]]
then
  echo "No people folder in ${GTD_DIR}" >&2
  exit 1
fi

mkdir -p "$(dirname "${PLIST}")" "$(dirname "${LOG}")"
sed -e "s|__SCRIPT__|${HERE}/linkedin-sync.sh|" \
    -e "s|__GTD_DIR__|${GTD_DIR}|g" \
    -e "s|__LOG__|${LOG}|g" \
    "${HERE}/${LABEL}.plist" > "${PLIST}"
plutil -lint "${PLIST}"
launchctl bootstrap "${DOMAIN}" "${PLIST}"

echo "Installed ${LABEL}: Mondays at 08:30, logging to ${LOG}"
echo "The first time it opens iTerm2, macOS asks to allow control of iTerm2. Allow it."
