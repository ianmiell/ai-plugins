#!/bin/bash
# linkedin-sync.sh: run by launchd every Monday morning (see com.ianmiell.linkedin-sync.plist and
# install-linkedin-sync.sh, which copies this and launchd-common.sh to
# ~/.local/share/personal-assistant/launchd/). Makes sure Chrome is running, since the skill
# reads LinkedIn through Claude in Chrome, then starts a background Claude Code session running
#   claude --bg --chrome '/personal-assistant:linkedin-sync'
# It shows up in `claude agents` (and the agent list in Claude Code); `claude attach <id>` opens
# it.
#
# If the Mac was asleep at the time, launchd runs it on waking, often before Wi-Fi is back, so
# it waits for the network first, and keeps the Mac from idle-sleeping while it waits and for
# the first AWAKE_FOR seconds of the session (default 20 minutes).

set -u

source "$(dirname "$0")/launchd-common.sh" \
  || { echo "$(date '+%F %T') cannot load launchd-common.sh next to $0" >&2; exit 1; }

AWAKE_FOR="${AWAKE_FOR:-1200}"

# First, so every run launchd starts leaves a line.
log_start "linkedin-sync session"
stay_awake
wait_for_network
pa_path

open -g -a "Google Chrome" || log "could not start Google Chrome" >&2

preflight || exit 1
if start_claude --bg --chrome --name "linkedin-sync-$(date +%d-%b)" '/personal-assistant:linkedin-sync'
then
  sleep "${AWAKE_FOR}"
fi
