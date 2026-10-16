#!/bin/bash
# linkedin-sync.sh: run by launchd every Monday morning (see com.ianmiell.linkedin-sync.plist and
# install-linkedin-sync.sh). Makes sure Chrome is running, since the skill reads LinkedIn through
# Claude in Chrome, then opens an iTerm2 window running
#   claude '/personal-assistant:linkedin-sync'
# If the Mac was asleep at the time, launchd runs it on waking.

set -u

GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"

echo "$(date '+%F %T') starting a linkedin-sync session"
open -g -a "Google Chrome" || echo "$(date '+%F %T') could not start Google Chrome" >&2

cmd="cd '${GTD_DIR}' && claude '/personal-assistant:linkedin-sync'"
osascript - "${cmd}" <<'APPLESCRIPT' || echo "$(date '+%F %T') failed to open iTerm2 (check Automation permission)" >&2
on run argv
  tell application "iTerm2"
    activate
    set newWindow to (create window with default profile)
    tell current session of newWindow to write text (item 1 of argv)
  end tell
end run
APPLESCRIPT
