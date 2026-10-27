#!/bin/bash
# linkedin-sync.sh: run by launchd every Monday morning (see com.ianmiell.linkedin-sync.plist and
# install-linkedin-sync.sh). Makes sure Chrome is running, since the skill reads LinkedIn through
# Claude in Chrome, then starts a background Claude Code session running
#   claude --bg --chrome '/personal-assistant:linkedin-sync'
# It shows up in `claude agents` (and the agent list in Claude Code); `claude attach <id>` opens
# it. If the Mac was asleep at the time, launchd runs it on waking.

set -u

GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"

echo "$(date '+%F %T') starting a linkedin-sync session"
open -g -a "Google Chrome" || echo "$(date '+%F %T') could not start Google Chrome" >&2

# launchd's PATH doesn't include ~/.local/bin, where the claude installer puts it.
export PATH="${HOME}/.local/bin:${PATH}"

(cd "${GTD_DIR}" && claude --bg --chrome --name "linkedin-sync" '/personal-assistant:linkedin-sync') \
  || echo "$(date '+%F %T') failed to start a background claude session" >&2
