#!/bin/bash
# install-obs-auto-record.sh: install (or with --uninstall, remove) the launchd agent that starts
# an OBS recording whenever a Zoom, Google Meet, Teams, WhatsApp, Slack huddle or similar call is
# live (see obs-auto-record.py).
#
# It copies obs-auto-record.py from this checkout to ~/.local/share/personal-assistant/launchd/
# and the agent runs that copy, so it doesn't depend on the branch the checkout is on (it
# failed when the checkout was on a branch without it). Re-run it after changing the script.

set -euo pipefail
source "$(dirname "$0")/install-common.sh"

install_init com.ianmiell.obs-auto-record
[[ ${1:-} == --uninstall ]] && install_uninstall

install_copy obs-auto-record.py
install_plist -e "s|__SCRIPT__|${DEST}/obs-auto-record.py|"

echo "Installed ${LABEL}: checking for live calls every 20 seconds, logging to ${LOG}"
echo "It runs ${DEST}/obs-auto-record.py: re-run this installer after changing the script."
echo "OBS needs obs-websocket enabled on port 4455 without authentication."
echo "The first time it checks each browser, macOS asks to allow control of it. Allow it."
