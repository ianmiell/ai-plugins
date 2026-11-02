#!/bin/bash
# weekly-plan.sh: run by launchd every Sunday evening (see com.ianmiell.weekly-plan.plist and
# install-weekly-plan.sh). Starts a background Claude Code session running
#   claude --bg '/personal-assistant:weekly-plan sunday'
# which plans the coming Monday to Friday from both calendars and the open gtd tasks and
# emails the plan to Ian's work address. It shows up in `claude agents`; `claude attach <id>`
# opens it.
#
# Sending email needs Gmail's send_message, which the global settings don't allow, so this
# session alone gets it through --allowed-tools. The skill only ever sends to Ian himself.
#
# If the Mac was asleep at the time, launchd runs this on waking, often before Wi-Fi is back,
# so it waits for the network first, and keeps the Mac from idle-sleeping while it waits and
# for the first AWAKE_FOR seconds of the session (default 10 minutes).

set -u

GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"
AWAKE_FOR="${AWAKE_FOR:-600}"
NETWORK_WAIT="${NETWORK_WAIT:-300}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

log() { echo "$(date '+%F %T') $*"; }

# Hold an idle-sleep assertion for as long as this script runs.
caffeinate -i -w $$ &

log "starting a weekly plan session"

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

# launchd's PATH doesn't include ~/.local/bin (claude) or /opt/homebrew/bin (gog).
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:${PATH}"

# The = form matters: --allowed-tools takes a list and would swallow the prompt otherwise.
if (cd "${GTD_DIR}" && "${CLAUDE_BIN}" --bg --name "weekly-plan-$(date +%d-%b)" \
      --allowed-tools="mcp__claude_ai_Gmail__send_message,Bash(tail *)" \
      '/personal-assistant:weekly-plan sunday')
then
  sleep "${AWAKE_FOR}"
else
  log "failed to start a background claude session" >&2
fi
