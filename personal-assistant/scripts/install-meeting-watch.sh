#!/bin/bash
# install-meeting-watch.sh: install (or with --uninstall, remove) the launchd agent that starts
# /personal-assistant:meeting as a background Claude Code session when a new recording lands in
# the inbox (~/Movies/meetings-inbox, where OBS records) or a new bare-stem transcript lands in
# ~/git/gtd/meetings.
#
# The agent runs meeting-watch.sh from this checkout, not from the installed plugin, whose
# folder name changes with each version. Re-run after moving the checkout.
#
# Any inbox recordings and bare-stem transcripts already there are marked as seen so installing
# doesn't start a session for each; process those with /personal-assistant:meeting.

set -euo pipefail

LABEL=com.ianmiell.meeting-watch
HERE="$(cd "$(dirname "$0")" && pwd)"
MEETINGS_DIR="${MEETINGS_DIR:-${HOME}/git/gtd/meetings}"
INBOX_DIR="${INBOX_DIR:-${HOME}/Movies/meetings-inbox}"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG="${HOME}/Library/Logs/${LABEL}.log"
SEEN="${XDG_STATE_HOME:-${HOME}/.local/state}/personal-assistant/meeting-seen"
DOMAIN="gui/$(id -u)"

launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true

if [[ ${1:-} == --uninstall ]]
then
  rm -f "${PLIST}"
  echo "Removed ${LABEL}. The seen list (${SEEN}) and log (${LOG}) are left in place."
  exit 0
fi

if [[ ! -d ${MEETINGS_DIR} ]]
then
  echo "No such folder: ${MEETINGS_DIR}" >&2
  exit 1
fi

mkdir -p "$(dirname "${PLIST}")" "$(dirname "${LOG}")" "$(dirname "${SEEN}")" "${INBOX_DIR}"
touch "${SEEN}"

shopt -s nullglob
for file in "${INBOX_DIR}"/[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9].mp4 \
            "${MEETINGS_DIR}"/[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9].txt
do
  name=$(basename "${file}")
  stem=${name%.*}
  grep -qxF "${stem}" "${SEEN}" && continue
  echo "Marking ${name} as seen; run /personal-assistant:meeting to process it"
  echo "${stem}" >> "${SEEN}"
done

sed -e "s|__SCRIPT__|${HERE}/meeting-watch.sh|" \
    -e "s|__MEETINGS_DIR__|${MEETINGS_DIR}|g" \
    -e "s|__INBOX_DIR__|${INBOX_DIR}|g" \
    -e "s|__LOG__|${LOG}|g" \
    "${HERE}/${LABEL}.plist" > "${PLIST}"
plutil -lint "${PLIST}"
launchctl bootstrap "${DOMAIN}" "${PLIST}"

echo "Installed ${LABEL}: watching ${INBOX_DIR} and ${MEETINGS_DIR}, logging to ${LOG}"
echo "Point OBS's recording path at ${INBOX_DIR}."
echo "New meetings start background sessions: list them with 'claude agents', open one with 'claude attach <id>'."
