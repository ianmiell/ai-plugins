#!/bin/bash
# weekly-plan.sh: run by launchd every Sunday evening (see com.ianmiell.weekly-plan.plist and
# install-weekly-plan.sh, which copies this and launchd-common.sh to
# ~/.local/share/personal-assistant/launchd/). Starts a background Claude Code session running
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

source "$(dirname "$0")/launchd-common.sh" \
  || { echo "$(date '+%F %T') cannot load launchd-common.sh next to $0" >&2; exit 1; }

AWAKE_FOR="${AWAKE_FOR:-600}"

# First, so every run launchd starts leaves a line.
log_start "weekly plan session"
stay_awake
wait_for_network
pa_path

preflight || exit 1
# The = form matters: --allowed-tools takes a list and would swallow the prompt otherwise.
if start_claude --bg --name "weekly-plan-$(date +%d-%b)" \
     --allowed-tools="mcp__claude_ai_Gmail__send_message,Bash(tail *),Bash(python3 *weekly-plan-gather.py *),Bash(python3 *calendar-events.py *),Bash(python3 *gtd-list.py *),Bash(python3 *pa-mail-html.py *)" \
     '/personal-assistant:weekly-plan sunday'
then
  sleep "${AWAKE_FOR}"
fi
