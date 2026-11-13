#!/bin/bash
# meeting-watch.sh: run by launchd whenever the recordings inbox or ~/git/gtd/meetings changes
# (see com.ianmiell.meeting-watch.plist and install-meeting-watch.sh).
#
# Starts one background Claude Code session running
#   claude --bg '/personal-assistant:meeting <stem> ...'
# for the new items, once they have stopped growing. It shows up in `claude agents` (and the
# agent list in Claude Code); `claude attach <id>` opens it. The items are:
#   - a recording in the inbox: OBS records YYYYMMDD_HHMM.mkv there and remuxes it to
#     YYYYMMDD_HHMM.mp4. /meeting names it and moves the .mp4 into the meetings folder, where
#     Whisper Transcription's Watch Folder transcribes it under its final name.
#   - a bare-stem transcript (YYYYMMDD_HHMM.txt) in the meetings folder, e.g. one exported from
#     Whisper Transcription by hand.
# Each stem is handled once: it's recorded in the seen file even if Ian skips it. Run
# /personal-assistant:meeting by hand to pick up anything left over.
#
# launchd fires on any change in either folder (OBS writing, remuxes, git pulls), so this must
# be quick and safe to run repeatedly, and it only logs when it finds something new.
#
# install-meeting-watch.sh copies this and launchd-common.sh to
# ~/.local/share/personal-assistant/launchd/, and the agent runs that copy.

set -u

MEETINGS_DIR="${MEETINGS_DIR:-${HOME}/git/gtd/meetings}"
INBOX_DIR="${INBOX_DIR:-${HOME}/Movies/meetings-inbox}"
GTD_DIR="$(dirname "${MEETINGS_DIR}")"
source "$(dirname "$0")/launchd-common.sh" \
  || { echo "$(date '+%F %T') cannot load launchd-common.sh next to $0" >&2; exit 1; }
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

# launchd's PATH is minimal and ~/.zshrc isn't read, so add claude (~/.local/bin), Homebrew
# (ffprobe for /meeting's .mkv check) and gtd (bin/gtd-push calls a bare `gtd`); the
# background session inherits it.
pa_path

shopt -s nullglob
new_stems=()
for file in "${INBOX_DIR}"/[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9].mp4 \
            "${MEETINGS_DIR}"/[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9].txt
do
  name=$(basename "${file}")
  stem=${name%.*}
  grep -qxF "${stem}" "${SEEN}" && continue
  if ! settled "${file}"
  then
    log "${name} is empty, gone or still growing; will retry on the next change"
    continue
  fi
  echo "${stem}" >> "${SEEN}"
  new_stems+=("${stem}")
done

(( ${#new_stems[@]} == 0 )) && exit 0

# Not logged on every run: launchd fires on every change in either folder.
log_start "meeting session for ${new_stems[*]}"
preflight || exit 1
start_claude --bg --name "meeting ${new_stems[*]}" "/personal-assistant:meeting ${new_stems[*]}"
