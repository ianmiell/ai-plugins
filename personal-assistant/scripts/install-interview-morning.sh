#!/bin/bash
# install-interview-morning.sh: install (or with --uninstall, remove) the launchd agent that starts
# /personal-assistant:interview as a background Claude Code session on weekday mornings when
# there is an interview that day, so the prep is in Ian's inbox before the first one.
#   install-interview-morning.sh            # Monday to Friday at 07:00
#   install-interview-morning.sh 06:30      # weekdays at another time
#   install-interview-morning.sh --uninstall
# Run it now with
#   launchctl kickstart gui/$(id -u)/com.ianmiell.interview-morning
#
# The agent runs interview-morning.sh from this checkout, not from the installed plugin, whose folder
# name changes with each version. Re-run after moving the checkout.

set -euo pipefail

LABEL=com.ianmiell.interview-morning
HERE="$(cd "$(dirname "$0")" && pwd)"
GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG="${HOME}/Library/Logs/${LABEL}.log"
DOMAIN="gui/$(id -u)"
AT="${1:-07:00}"

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
sed -e "s|__SCRIPT__|${HERE}/interview-morning.sh|" \
    -e "s|__GTD_DIR__|${GTD_DIR}|g" \
    -e "s|__LOG__|${LOG}|g" \
    -e "s|__HOUR__|${HOUR}|g" \
    -e "s|__MINUTE__|${MINUTE}|g" \
    "${HERE}/${LABEL}.plist" > "${PLIST}"
plutil -lint "${PLIST}"
launchctl bootstrap "${DOMAIN}" "${PLIST}"

printf 'Installed %s: Monday to Friday at %02d:%02d, logging to %s\n' "${LABEL}" "${HOUR}" "${MINUTE}" "${LOG}"
echo "Days with an interview start a background session: list them with 'claude agents', open one with 'claude attach <id>'."
