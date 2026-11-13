#!/bin/bash
# install-linkedin-sync.sh: install (or with --uninstall, remove) the launchd agent that starts
# /personal-assistant:linkedin-sync as a background Claude Code session every Monday at 08:30.
# Run it now with
#   launchctl kickstart gui/$(id -u)/com.ianmiell.linkedin-sync
#
# It copies linkedin-sync.sh and launchd-common.sh from this checkout to
# ~/.local/share/personal-assistant/launchd/ and the agent runs that copy, so it doesn't
# depend on the branch the checkout is on. Re-run it after changing either script.

set -euo pipefail
source "$(dirname "$0")/install-common.sh"

GTD_DIR="${GTD_DIR:-${HOME}/git/gtd}"
install_init com.ianmiell.linkedin-sync
[[ ${1:-} == --uninstall ]] && install_uninstall

if [[ ! -d ${GTD_DIR}/people ]]
then
  echo "No people folder in ${GTD_DIR}" >&2
  exit 1
fi

install_copy linkedin-sync.sh launchd-common.sh
install_plist -e "s|__SCRIPT__|${DEST}/linkedin-sync.sh|" \
              -e "s|__GTD_DIR__|${GTD_DIR}|g"

echo "Installed ${LABEL}: Mondays at 08:30, logging to ${LOG}"
echo "It runs ${DEST}/linkedin-sync.sh: re-run this installer after changing the script."
echo "Each run starts a background session: list them with 'claude agents', open one with 'claude attach <id>'."
