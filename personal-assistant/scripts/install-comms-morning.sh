#!/bin/bash
# install-comms-morning.sh: install (or with --uninstall, remove) the launchd agent that starts
# /personal-assistant:comms as a background Claude Code session every weekday morning, so the
# triage list and drafts are waiting when Ian sits down.
#   install-comms-morning.sh            # weekdays at 07:45
#   install-comms-morning.sh 08:15      # weekdays at another time
#   install-comms-morning.sh --uninstall
# Run it now with
#   launchctl kickstart gui/$(id -u)/com.ianmiell.comms-morning
#
# The agent runs comms-morning.sh from this checkout, not from the installed plugin, whose folder
# name changes with each version. Re-run after moving the checkout.

set -euo pipefail

LABEL=com.ianmiell.comms-morning
HERE="$(cd "$(dirname "$0")" && pwd)"
GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG="${HOME}/Library/Logs/${LABEL}.log"
DOMAIN="gui/$(id -u)"
AT="${1:-07:45}"

launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true

if [[ ${AT} == --uninstall ]]
then
  rm -f "${PLIST}"
  echo "Removed ${LABEL}. The log (${LOG}) is left in place."
  exit 0
fi

if [[ ! ${AT} =~ ^([01]?[0-9]|2[0-3]):([0-5][0-9])$ ]]
then
  echo "Give the time as HH:MM, e.g. 07:45" >&2
  exit 1
fi
HOUR=$((10#${BASH_REMATCH[1]}))
MINUTE=$((10#${BASH_REMATCH[2]}))

if [[ ! -d ${GTD_DIR} ]]
then
  echo "No gtd checkout at ${GTD_DIR}" >&2
  exit 1
fi

mkdir -p "$(dirname "${PLIST}")" "$(dirname "${LOG}")"
sed -e "s|__SCRIPT__|${HERE}/comms-morning.sh|" \
    -e "s|__GTD_DIR__|${GTD_DIR}|g" \
    -e "s|__LOG__|${LOG}|g" \
    -e "s|__HOUR__|${HOUR}|g" \
    -e "s|__MINUTE__|${MINUTE}|g" \
    "${HERE}/${LABEL}.plist" > "${PLIST}"
plutil -lint "${PLIST}"
launchctl bootstrap "${DOMAIN}" "${PLIST}"

printf 'Installed %s: weekdays at %02d:%02d, logging to %s\n' "${LABEL}" "${HOUR}" "${MINUTE}" "${LOG}"
echo "Each run starts a background session: list them with 'claude agents', open one with 'claude attach <id>'."
