#!/bin/bash
# install-comms-morning.sh: install (or with --uninstall, remove) the launchd agent that starts
# /personal-assistant:comms as a background Claude Code session every morning, so the
# triage list and drafts are waiting when Ian sits down.
#   install-comms-morning.sh            # every day at 05:00
#   install-comms-morning.sh 08:15      # every day at another time
#   install-comms-morning.sh --uninstall
# Run it now with
#   launchctl kickstart gui/$(id -u)/com.ianmiell.comms-morning
#
# It copies comms-morning.sh and launchd-common.sh from this checkout to
# ~/.local/share/personal-assistant/launchd/ and the agent runs that copy, so it doesn't
# depend on the branch the checkout is on. Re-run it after changing either script.

set -euo pipefail
source "$(dirname "$0")/install-common.sh"

install_scheduled com.ianmiell.comms-morning comms-morning.sh 05:00 "every day" \
  "Each run starts a background session: list them with 'claude agents', open one with 'claude attach <id>'." \
  "$@"
