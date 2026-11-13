#!/bin/bash
# install-meeting-watch.sh: install (or with --uninstall, remove) the launchd agent that starts
# /personal-assistant:meeting as a background Claude Code session when a new recording lands in
# the inbox (~/Movies/meetings-inbox, where OBS records) or a new bare-stem transcript lands in
# ~/git/gtd/meetings.
#
# It copies meeting-watch.sh and launchd-common.sh from this checkout to
# ~/.local/share/personal-assistant/launchd/ and the agent runs that copy, so it doesn't
# depend on the branch the checkout is on. Re-run it after changing either script.
#
# Any inbox recordings and bare-stem transcripts already there are marked as seen so installing
# doesn't start a session for each; process those with /personal-assistant:meeting.

set -euo pipefail
source "$(dirname "$0")/install-common.sh"

MEETINGS_DIR="${MEETINGS_DIR:-${HOME}/git/gtd/meetings}"
INBOX_DIR="${INBOX_DIR:-${HOME}/Movies/meetings-inbox}"
SEEN="${XDG_STATE_HOME:-${HOME}/.local/state}/personal-assistant/meeting-seen"

install_init com.ianmiell.meeting-watch
[[ ${1:-} == --uninstall ]] && install_uninstall "The seen list (${SEEN}) and log (${LOG}) are left in place."

if [[ ! -d ${MEETINGS_DIR} ]]
then
  echo "No such folder: ${MEETINGS_DIR}" >&2
  exit 1
fi

mkdir -p "$(dirname "${SEEN}")" "${INBOX_DIR}"
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

install_copy meeting-watch.sh launchd-common.sh
install_plist -e "s|__SCRIPT__|${DEST}/meeting-watch.sh|" \
              -e "s|__MEETINGS_DIR__|${MEETINGS_DIR}|g" \
              -e "s|__INBOX_DIR__|${INBOX_DIR}|g"

echo "Installed ${LABEL}: watching ${INBOX_DIR} and ${MEETINGS_DIR}, logging to ${LOG}"
echo "It runs ${DEST}/meeting-watch.sh: re-run this installer after changing the script."
echo "Point OBS's recording path at ${INBOX_DIR}."
echo "New meetings start background sessions: list them with 'claude agents', open one with 'claude attach <id>'."
