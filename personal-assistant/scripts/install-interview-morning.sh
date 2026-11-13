#!/bin/bash
# install-interview-morning.sh: install (or with --uninstall, remove) the launchd agent that starts
# /personal-assistant:interview as a background Claude Code session on weekday mornings when
# there is an interview that day, so the prep is in Ian's inbox before the first one.
#   install-interview-morning.sh            # Monday to Friday at 07:00
#   install-interview-morning.sh 06:30      # weekdays at another time
#   install-interview-morning.sh --uninstall
# Run it now with
#   launchctl kickstart gui/$(id -u)/com.ianmiell.interview-morning
#
# It copies interview-morning.sh and launchd-common.sh from this checkout to
# ~/.local/share/personal-assistant/launchd/ and the agent runs that copy, so it doesn't
# depend on the branch the checkout is on. Re-run it after changing either script.

set -euo pipefail
source "$(dirname "$0")/install-common.sh"

install_scheduled com.ianmiell.interview-morning interview-morning.sh 07:00 "Monday to Friday" \
  "Days with an interview start a background session: list them with 'claude agents', open one with 'claude attach <id>'." \
  "$@"
