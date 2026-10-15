#!/bin/bash
# meeting-watch.sh: run by launchd whenever ~/git/gtd/meetings changes (see
# com.ianmiell.meeting-watch.plist and install-meeting-watch.sh).
#
# Looks for new bare-stem transcripts (YYYYMMDD_HHMM.txt, written by Whisper Transcription),
# waits until each has stopped growing, and opens one iTerm2 window running
#   claude '/personal-assistant:meeting <stem> ...'
# Each stem is handled once: it's recorded in the seen file even if Ian skips it. Run
# /personal-assistant:meeting by hand to pick up anything left over.
#
# launchd fires on any change in the folder (OBS writing, remuxes, git pulls), so this must
# be quick and safe to run repeatedly.

set -u

MEETINGS_DIR="${MEETINGS_DIR:-${HOME}/git/gtd/meetings}"
GTD_DIR="$(dirname "${MEETINGS_DIR}")"
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/personal-assistant"
SEEN="${STATE_DIR}/meeting-seen"
SETTLE_SECONDS=10   # the file must keep the same size for this long
MAX_TRIES=60        # ...checked up to this many times before giving up until the next run

mkdir -p "${STATE_DIR}"
touch "${SEEN}"

# Wait until the file's size holds steady. Returns 1 if it's empty (writing it will fire
# launchd again) or never settles.
settled() {
  local file="$1" before after tries=0
  before=$(/usr/bin/stat -f %z "${file}" 2>/dev/null) || return 1
  while (( tries < MAX_TRIES ))
  do
    (( before == 0 )) && return 1
    sleep "${SETTLE_SECONDS}"
    after=$(/usr/bin/stat -f %z "${file}" 2>/dev/null) || return 1
    if (( after == before ))
    then
      return 0
    fi
    before=${after}
    tries=$((tries + 1))
  done
  return 1
}

open_iterm() {
  local cmd="cd '${GTD_DIR}' && claude '/personal-assistant:meeting $*'"
  osascript - "${cmd}" <<'EOF'
on run argv
  tell application "iTerm2"
    activate
    set newWindow to (create window with default profile)
    tell current session of newWindow to write text (item 1 of argv)
  end tell
end run
EOF
}

shopt -s nullglob
new_stems=()
for txt in "${MEETINGS_DIR}"/[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9].txt
do
  stem=$(basename "${txt}" .txt)
  grep -qxF "${stem}" "${SEEN}" && continue
  if ! settled "${txt}"
  then
    echo "$(date '+%F %T') ${stem}.txt is empty, gone or still growing; will retry on the next change"
    continue
  fi
  echo "${stem}" >> "${SEEN}"
  new_stems+=("${stem}")
done

(( ${#new_stems[@]} == 0 )) && exit 0

echo "$(date '+%F %T') new transcript(s): ${new_stems[*]}"
open_iterm "${new_stems[@]}" || echo "$(date '+%F %T') failed to open iTerm2 (check Automation permission)" >&2
