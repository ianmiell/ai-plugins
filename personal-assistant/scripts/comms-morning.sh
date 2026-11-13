#!/bin/bash
# comms-morning.sh: run by launchd every morning (see com.ianmiell.comms-morning.plist and
# install-comms-morning.sh, which copies this and launchd-common.sh to
# ~/.local/share/personal-assistant/launchd/). Starts a background Claude Code session running
#   claude --bg --chrome '/personal-assistant:comms morning'
# The session gathers every channel and cross-checks, then stops at the numbered list, notifies
# Ian that it's ready, and waits. It sends nothing, and it doesn't mark the Slack/WhatsApp
# windows until Ian has seen the list. It shows up in `claude agents`; `claude attach <id>`
# opens it.
#
# If the Mac was asleep at the time, launchd runs this on waking, often before Wi-Fi is back,
# so it waits for the network first. It keeps the Mac from idle-sleeping while it waits and
# for the first AWAKE_FOR seconds of the session (default 20 minutes), long enough for /comms
# to gather. Closing the lid on battery still sleeps the Mac; caffeinate can't stop that.
# If the Mac was shut down (or nobody was logged in), launchd doesn't run it at all, and the
# log has no line for that morning.

set -u

source "$(dirname "$0")/launchd-common.sh" \
  || { echo "$(date '+%F %T') cannot load launchd-common.sh next to $0" >&2; exit 1; }

AWAKE_FOR="${AWAKE_FOR:-1200}"

# First, so every run launchd starts leaves a line.
log_start "morning comms session"
stay_awake
wait_for_network
pa_path

# /comms reads LinkedIn through Claude in Chrome.
open -g -a "Google Chrome" || log "could not start Google Chrome" >&2

preflight || exit 1
if start_claude --bg --chrome --name "comms-$(date +%a-%d-%b)" '/personal-assistant:comms morning'
then
  # Stay awake while the session gathers; caffeinate exits with this script.
  sleep "${AWAKE_FOR}"
fi
