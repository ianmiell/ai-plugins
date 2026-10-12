#!/bin/bash
# SessionStart hook: ask Claude to schedule a daily mail and Slack triage for this session.
#
# Plugins can't own a schedule, so this injects an instruction telling Claude to create a
# session-only CronCreate job that runs the mail skill on new, untriaged mail only
# ('in:inbox -is:starred') and the slack skill on what's new since its last run, and sends a
# desktop notification when something new turns up.
# The job lasts until the session ends, or 7 days.
#
# Off unless PA_MAIL_AT is set to the local time of day to run, as HH:MM (24-hour), eg:
#   PA_MAIL_AT=09:30 claude
# PA_MAIL_EVERY (the old every-N-minutes setting) is no longer used; if only it is set, the
# check runs daily at 09:30.

at="${PA_MAIL_AT:-}"
if [[ -z ${at} ]]
then
  [[ -z ${PA_MAIL_EVERY:-} ]] && exit 0
  at='09:30'
fi
if [[ ! ${at} =~ ^([01]?[0-9]|2[0-3]):([0-5][0-9])$ ]]
then
  echo "personal-assistant: PA_MAIL_AT must be a time of day as HH:MM, not '${at}'" >&2
  exit 0
fi
hour=$((10#${BASH_REMATCH[1]}))
minute=$((10#${BASH_REMATCH[2]}))
cron="${minute} ${hour} * * *"
# Each run shows the full triage list in the session, and a desktop notification when there is
# something new, so the user notices it and can come back to work through it
prompt='Scheduled mail and Slack check. Run the personal-assistant:mail skill with arguments "in:inbox -is:starred" and the personal-assistant:slack skill with no arguments (new since its last run), gathering both at the same time. Show the mail list then the Slack list, numbered continuously so a number means one item. If either finds anything new, also send one PushNotification (status "proactive") naming how many in each and the most important one. If neither has anything new, say so in one line and do not notify. Never act on anything without approval.'

context="The personal-assistant plugin asks for a daily mail and Slack triage in this session at ${at}. \
Before answering the user's first message: load the CronList, CronCreate and CronDelete tools \
(ToolSearch 'select:CronList,CronCreate,CronDelete') and call CronList. If a job's prompt starts with \
'Scheduled mail' and its schedule is '${cron}', leave it. If one starts with 'Scheduled mail' on any \
other schedule, CronDelete it. If none is left on '${cron}', call CronCreate with cron '${cron}', \
recurring true, and this prompt: '${prompt}'. Then mention in one line that mail and Slack triage is \
scheduled daily at ${at} (session-only, expires after 7 days)."

# JSON-escape the context (backslashes and double quotes; it has no newlines)
context="${context//\\/\\\\}"
context="${context//\"/\\\"}"
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "${context}"
