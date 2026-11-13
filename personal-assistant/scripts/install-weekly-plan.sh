#!/bin/bash
# install-weekly-plan.sh: install (or with --uninstall, remove) the launchd agent that starts
# /personal-assistant:weekly-plan as a background Claude Code session every Sunday evening, which
# emails Ian a plan for the coming week.
#   install-weekly-plan.sh            # Sundays at 18:00
#   install-weekly-plan.sh 19:00      # Sundays at another time
#   install-weekly-plan.sh --uninstall
# Run it now with
#   launchctl kickstart gui/$(id -u)/com.ianmiell.weekly-plan
#
# It copies weekly-plan.sh and launchd-common.sh from this checkout to
# ~/.local/share/personal-assistant/launchd/ and the agent runs that copy, so it doesn't
# depend on the branch the checkout is on. Re-run it after changing either script.

set -euo pipefail
source "$(dirname "$0")/install-common.sh"

install_scheduled com.ianmiell.weekly-plan weekly-plan.sh 18:00 "Sundays" \
  "Each run starts a background session: list them with 'claude agents', open one with 'claude attach <id>'." \
  "$@"
