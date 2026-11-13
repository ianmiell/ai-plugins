# install-common.sh: shared by the install-*.sh scripts. Not run directly; each installer
# sources it from its own folder:
#   source "$(dirname "$0")/install-common.sh"
#   install_init com.ianmiell.comms-morning
#
# The agents don't run their scripts from this checkout, which may be on another branch (or
# mid-rebase) when launchd fires. install_copy puts what an agent runs in
# ~/.local/share/personal-assistant/launchd/ (PA_LAUNCHD_DIR), and the plist points there.
# Re-running an installer updates the copies.
#
# Gives:
#   install_init LABEL           set HERE, DEST, PLIST, LOG, DOMAIN; boot out the old agent
#   install_uninstall [NOTE]     remove the plist (the copies and the log stay) and exit
#   install_time HH:MM           check a time and set HOUR and MINUTE
#   install_copy FILE...         copy files from HERE to DEST (scripts stay executable)
#   install_plist SED-ARGS...    fill in the plist template (__SCRIPT__ etc.), lint, load it
#   install_scheduled LABEL WRAPPER DEFAULT_TIME WHEN AFTER [ARG]
#                                the whole of a daily or weekly installer: ARG is HH:MM or
#                                --uninstall; WHEN is how the schedule reads ("Sundays");
#                                AFTER is the closing line
#
# LAUNCHCTL (launchctl) is for the tests, which also point HOME at a temporary folder.

LAUNCHCTL="${LAUNCHCTL:-launchctl}"

install_init() {
  LABEL="$1"
  HERE="$(cd "$(dirname "$0")" && pwd)"
  DEST="${PA_LAUNCHD_DIR:-${HOME}/.local/share/personal-assistant/launchd}"
  PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
  LOG="${HOME}/Library/Logs/${LABEL}.log"
  DOMAIN="gui/$(id -u)"
  "${LAUNCHCTL}" bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
}

install_uninstall() {
  rm -f "${PLIST}"
  echo "Removed ${LABEL}. ${1:-The log (${LOG}) is left in place.}"
  echo "The scripts copied to ${DEST} are left in place (other agents may use them)."
  exit 0
}

install_time() {
  if [[ ! $1 =~ ^([01]?[0-9]|2[0-3]):([0-5][0-9])$ ]]
  then
    echo "Give the time as HH:MM, e.g. 07:45" >&2
    exit 1
  fi
  HOUR=$((10#${BASH_REMATCH[1]}))
  MINUTE=$((10#${BASH_REMATCH[2]}))
}

install_copy() {
  local file
  mkdir -p "${DEST}"
  for file in "$@"
  do
    # Copy then rename, so a run starting at that moment never sees half a file.
    cp "${HERE}/${file}" "${DEST}/.${file}.new"
    case "${file}" in
      *.sh|*.py) chmod 755 "${DEST}/.${file}.new" ;;
      *) chmod 644 "${DEST}/.${file}.new" ;;
    esac
    mv -f "${DEST}/.${file}.new" "${DEST}/${file}"
  done
}

install_plist() {
  mkdir -p "$(dirname "${PLIST}")" "$(dirname "${LOG}")"
  sed -e "s|__LOG__|${LOG}|g" "$@" "${HERE}/${LABEL}.plist" > "${PLIST}"
  plutil -lint "${PLIST}"
  "${LAUNCHCTL}" bootstrap "${DOMAIN}" "${PLIST}"
}

install_scheduled() {
  local label="$1" wrapper="$2" at="${6:-$3}" when="$4" after="$5"
  GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"
  # Check the time before touching the agent, so a typo leaves the old one running.
  [[ ${at} == --uninstall ]] || install_time "${at}"
  install_init "${label}"
  [[ ${at} == --uninstall ]] && install_uninstall
  if [[ ! -d ${GTD_DIR} ]]
  then
    echo "No gtd checkout at ${GTD_DIR}" >&2
    exit 1
  fi
  install_copy "${wrapper}" launchd-common.sh
  install_plist -e "s|__SCRIPT__|${DEST}/${wrapper}|" \
                -e "s|__GTD_DIR__|${GTD_DIR}|g" \
                -e "s|__HOUR__|${HOUR}|g" \
                -e "s|__MINUTE__|${MINUTE}|g"
  printf 'Installed %s: %s at %02d:%02d, logging to %s\n' "${label}" "${when}" "${HOUR}" "${MINUTE}" "${LOG}"
  echo "It runs ${DEST}/${wrapper}: re-run this installer after changing the script."
  echo "${after}"
}
