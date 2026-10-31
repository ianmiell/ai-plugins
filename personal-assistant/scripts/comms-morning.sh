#!/bin/bash
# comms-morning.sh: run by launchd every weekday morning (see com.ianmiell.comms-morning.plist and
# install-comms-morning.sh). Makes sure Chrome is running, since /comms reads LinkedIn through
# Claude in Chrome, then starts a background Claude Code session running
#   claude --bg --chrome '/personal-assistant:comms'
# The session gathers every channel, cross-checks and drafts, then stops at the numbered list
# and waits for Ian. It sends nothing, and it doesn't mark the Slack/WhatsApp windows until
# Ian has seen the list. It shows up in `claude agents`; `claude attach <id>` opens it. If
# the Mac was asleep at the time, launchd runs it on waking.

set -u

GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"

echo "$(date '+%F %T') starting a morning comms session"
open -g -a "Google Chrome" || echo "$(date '+%F %T') could not start Google Chrome" >&2

# launchd's PATH doesn't include ~/.local/bin, where the claude installer puts it.
export PATH="${HOME}/.local/bin:${PATH}"

(cd "${GTD_DIR}" && claude --bg --chrome --name "comms-$(date +%a-%d-%b)" '/personal-assistant:comms') \
  || echo "$(date '+%F %T') failed to start a background claude session" >&2
