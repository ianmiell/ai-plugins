# launchd-common.sh: shared by the launchd wrappers (comms-morning.sh, interview-morning.sh,
# weekly-plan.sh, linkedin-sync.sh, meeting-watch.sh). Not run directly; each wrapper sources it
# from its own folder:
#   source "$(dirname "$0")/launchd-common.sh"
#
# The installers copy the wrappers and this file to ~/.local/share/personal-assistant/launchd/,
# so the agents don't depend on which branch the checkout is on.
#
# Gives:
#   log MESSAGE...        a dated line on stdout (launchd sends it to the agent's log)
#   log_start NAME        "NAME started", with the power source and how long since the Mac woke
#   pa_path               put claude, Homebrew (gog, ffprobe, gh, timeout) and gtd on PATH
#   stay_awake            hold an idle-sleep assertion (caffeinate -i) while the wrapper runs
#   wait_for_network      wait up to NETWORK_WAIT seconds (300) for the network, then go on anyway
#   preflight             check that claude and the gtd folder are there, logging which isn't
#   start_claude ARGS...  run "${CLAUDE_BIN}" ARGS... in the gtd folder, logging a failure
#
# Settings, all from the environment: GTD_DIR (~/git/gtd), CLAUDE_BIN (claude),
# NETWORK_WAIT (300), NETWORK_URL (Google's 204 check). Works with macOS's bash 3.2.

GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
NETWORK_WAIT="${NETWORK_WAIT:-300}"
NETWORK_URL="${NETWORK_URL:-https://www.google.com/generate_204}"

log() { echo "$(date '+%F %T') $*"; }

# "on AC power, woke 42s ago": enough to tell a run on waking from one on time. Missing tools
# or odd output just leave a part out.
power_note() {
  local source="" woke="" now secs
  source=$(pmset -g batt 2>/dev/null | sed -n "s/^Now drawing from '\(.*\)'.*/\1/p")
  secs=$(sysctl -n kern.waketime 2>/dev/null | sed -n 's/^{ sec = \([0-9][0-9]*\),.*/\1/p')
  if [[ -n ${secs} && ${secs} != 0 ]]
  then
    now=$(date +%s)
    woke="woke $((now - secs))s ago"
  fi
  if [[ -n ${source} && -n ${woke} ]]
  then
    echo "on ${source}, ${woke}"
  else
    echo "${source:+on ${source}}${woke}"
  fi
}

log_start() {
  local note
  note=$(power_note 2>/dev/null)
  log "$1 started (pid $$${note:+, ${note}})"
}

# launchd's PATH is /usr/bin:/bin:/usr/sbin:/sbin and ~/.zshrc isn't read. Put the usual tool
# folders that exist and aren't on PATH yet at the front; the background session inherits it
# (bin/gtd-push calls a bare `gtd`, /meeting needs ffprobe). The same list as pa_common.py.
pa_path() {
  local dir add=""
  for dir in /opt/homebrew/bin /usr/local/bin "${HOME}/.local/bin" "${GTD_DIR}/bin"
  do
    [[ -d ${dir} ]] || continue
    case ":${PATH}:" in
      *":${dir}:"*) ;;
      *) add="${add}${dir}:" ;;
    esac
  done
  export PATH="${add}${PATH}"
}

# Hold an idle-sleep assertion for as long as this script runs. Closing the lid on battery
# still sleeps the Mac; caffeinate can't stop that.
stay_awake() {
  caffeinate -i -w $$ &
}

# Launchd runs a missed StartCalendarInterval job on waking, often before Wi-Fi is back.
# Returns 1 if the network never came (the caller carries on: the skill reports what it
# couldn't reach).
wait_for_network() {
  local waited=0
  until curl -s -o /dev/null --max-time 5 "${NETWORK_URL}"
  do
    if (( waited >= NETWORK_WAIT ))
    then
      log "no network after ${NETWORK_WAIT}s; starting anyway" >&2
      return 1
    fi
    sleep 5
    waited=$((waited + 5))
  done
  (( waited > 0 )) && log "network up after ${waited}s"
  return 0
}

# Each problem gets its own message, so the log says what's wrong rather than "failed to start".
preflight() {
  local ok=0
  if ! command -v "${CLAUDE_BIN}" >/dev/null 2>&1
  then
    log "preflight: claude not found (CLAUDE_BIN=${CLAUDE_BIN}, PATH=${PATH})" >&2
    ok=1
  fi
  if [[ ! -d ${GTD_DIR} ]]
  then
    log "preflight: no gtd folder at ${GTD_DIR}" >&2
    ok=1
  fi
  return ${ok}
}

start_claude() {
  if ! cd "${GTD_DIR}"
  then
    log "could not cd to ${GTD_DIR}" >&2
    return 1
  fi
  local rc=0
  "${CLAUDE_BIN}" "$@" || rc=$?
  if (( rc != 0 ))
  then
    log "claude exited with ${rc}: failed to start a background claude session" >&2
  fi
  return ${rc}
}
