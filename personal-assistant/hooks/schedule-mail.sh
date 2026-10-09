#!/bin/bash
# SessionStart hook: ask Claude to schedule recurring mail triage for this session.
#
# Plugins can't own a schedule, so this injects an instruction telling Claude to create a
# session-only CronCreate job that runs the mail skill on new, untriaged mail only
# ('in:inbox -is:starred') and sends a desktop notification when something new turns up.
# The job lasts until the session ends, or 7 days.
#
# Off unless PA_MAIL_EVERY is set to the interval in minutes, eg:
#   PA_MAIL_EVERY=30 claude
# Values from 1 to 59 that divide 60 give an exact schedule (eg 15, 20, 30); anything else
# is rounded down to one that does; 60 or more means hourly.

every="${PA_MAIL_EVERY:-}"
[[ -z ${every} ]] && exit 0
if [[ ! ${every} =~ ^[0-9]+$ ]] || (( every < 1 ))
then
  echo "personal-assistant: PA_MAIL_EVERY must be a number of minutes, not '${every}'" >&2
  exit 0
fi

# Minutes past the hour to run at: start at :07 (off the busy :00/:30 marks), every 'every' minutes
if (( every >= 60 ))
then
  minutes=7
else
  while (( 60 % every != 0 ))
  do
    every=$((every - 1))
  done
  minutes=''
  for (( m = 7 % every; m < 60; m += every ))
  do
    minutes="${minutes:+${minutes},}${m}"
  done
fi
cron="${minutes} * * * *"
# Each run shows the full triage list in the session, and a desktop notification when there is
# something new, so the user notices it and can come back to work through it
prompt='Scheduled mail check. Run the personal-assistant:mail skill with arguments "in:inbox -is:starred" and show the full triage list as usual. If it finds any new threads, also send a PushNotification (status "proactive") naming how many and the most important one. If nothing is new, say so in one line and do not notify. Never act on any thread without approval.'

context="The personal-assistant plugin asks for recurring mail triage in this session (PA_MAIL_EVERY=${PA_MAIL_EVERY}). \
Before answering the user's first message: load the CronList and CronCreate tools (ToolSearch 'select:CronList,CronCreate'), \
call CronList, and if no job's prompt already starts with 'Scheduled mail check', call CronCreate with cron '${cron}', \
recurring true, and this prompt: '${prompt}'. Then mention in one line that mail triage is scheduled (${cron}, \
session-only, expires after 7 days)."

# JSON-escape the context (backslashes and double quotes; it has no newlines)
context="${context//\\/\\\\}"
context="${context//\"/\\\"}"
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "${context}"
