#!/bin/bash
# interview-morning.sh: run by launchd on weekday mornings (see com.ianmiell.interview-morning.plist
# and install-interview-morning.sh). Looks at today's events on Ian's work calendar, and only if
# one has "interview" in its title starts a background Claude Code session running
#   claude --bg '/personal-assistant:interview morning'
# which prepares Ian for each of today's interviews (links, checklist, CV points, the GitHub fork
# for a pairing interview as a dry run), emails the prep to his work address and notifies him.
# On days without an interview it exits without starting Claude. Sessions show up in
# `claude agents`; `claude attach <id>` opens one (to say yes to a fork, for instance).
#
# Sending email needs Gmail's send_message, which the global settings don't allow, so this
# session alone gets it through --allowed-tools. The skill only ever sends to Ian himself.
#
# DRY_RUN=1 prints what it would do without starting a session.
#
# If the Mac was asleep at the time, launchd runs this on waking, often before Wi-Fi is back,
# so it waits for the network first, and keeps the Mac from idle-sleeping while it waits and
# for the first AWAKE_FOR seconds of the session (default 15 minutes).

set -u

GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"
WORK_ACCOUNT="${WORK_ACCOUNT:-ian.miell@container-solutions.com}"
AWAKE_FOR="${AWAKE_FOR:-900}"
NETWORK_WAIT="${NETWORK_WAIT:-300}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
DRY_RUN="${DRY_RUN:-}"

log() { echo "$(date '+%F %T') $*"; }

# Hold an idle-sleep assertion for as long as this script runs.
caffeinate -i -w $$ &

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

# gog --plain prints a header, then ID, START, END, SUMMARY separated by tabs. If the calendar
# can't be read (expired token, no network), start the session anyway: it reads the calendar
# through its own connector and stops quietly if there's no interview.
if events="$(gog --readonly --no-input -a "${WORK_ACCOUNT}" calendar events --today --all-pages --plain 2>&1)"
then
  interviews="$(printf '%s\n' "${events}" | tail -n +2 | cut -f2,4- | grep -i 'interview')"
  if [[ -z ${interviews} ]]
  then
    log "no interviews today"
    exit 0
  fi
  log "interviews today:"
  printf '%s\n' "${interviews}"
else
  log "could not read the calendar with gog; starting the session to check: ${events}" >&2
fi

if [[ -n ${DRY_RUN} ]]
then
  log "DRY_RUN: would start '/personal-assistant:interview morning' in ${GTD_DIR}"
  exit 0
fi

# The = form matters: --allowed-tools takes a list and would swallow the prompt otherwise.
# Only the fork's dry run is allowed; the real fork waits for Ian.
if (cd "${GTD_DIR}" && "${CLAUDE_BIN}" --bg --name "interview-$(date +%a-%d-%b)" \
      --allowed-tools="mcp__claude_ai_Gmail__send_message,Bash(python3 *interview-fork.py * --dry-run)" \
      '/personal-assistant:interview morning')
then
  sleep "${AWAKE_FOR}"
else
  log "failed to start a background claude session" >&2
fi
