#!/bin/bash
# comms-morning.sh: run by launchd every weekday morning (see com.ianmiell.comms-morning.plist and
# install-comms-morning.sh). Starts a background Claude Code session running
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

set -u

GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"
AWAKE_FOR="${AWAKE_FOR:-1200}"
NETWORK_WAIT="${NETWORK_WAIT:-300}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

log() { echo "$(date '+%F %T') $*"; }

# Hold an idle-sleep assertion for as long as this script runs.
caffeinate -i -w $$ &

log "starting a morning comms session"

# Wait for the network, up to NETWORK_WAIT seconds, then start anyway: /comms reports any
# channel it couldn't reach.
waited=0
until curl -s -o /dev/null --max-time 5 https://www.google.com/generate_204
do
  if (( waited >= NETWORK_WAIT ))
  then
    log "no network after ${NETWORK_WAIT}s; starting anyway" >&2
    waited=-1
    break
  fi
  sleep 5
  waited=$((waited + 5))
done
(( waited > 0 )) && log "network up after ${waited}s"

# /comms reads LinkedIn through Claude in Chrome.
open -g -a "Google Chrome" || log "could not start Google Chrome" >&2

# launchd's PATH doesn't include ~/.local/bin, where the claude installer puts it.
export PATH="${HOME}/.local/bin:${PATH}"

if (cd "${GTD_DIR}" && "${CLAUDE_BIN}" --bg --chrome --name "comms-$(date +%a-%d-%b)" \
      '/personal-assistant:comms morning')
then
  # Stay awake while the session gathers; caffeinate exits with this script.
  sleep "${AWAKE_FOR}"
else
  log "failed to start a background claude session" >&2
fi
