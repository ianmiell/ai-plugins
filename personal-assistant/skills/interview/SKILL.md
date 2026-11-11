---
name: interview
description: Prepare for, run notes for, and write up interviews Ian conducts with candidates to work at Container Solutions. If there is a calendar entry that has the word 'interview' and was created by ivana@container-solutions.com then this skill should be triggered. Optional argument "morning" is the unattended weekday run (the interview-morning launchd agent opens a session with "/personal-assistant:interview morning" on days with an interview), which emails Ian the prep for all of today's interviews and notifies him.
---

# Interview

There are two interview types: pairing, and consultant interview.

This document:

https://docs.google.com/document/d/13tkWmTeljfEvi_MlAB9HX5lVW0IaNg2JZzZJfbEezCY/edit?tab=t.0

sets out the processes for each.

The calendar entry should have relevant links pertaining to the candidate.

## Preparing Ian

To prepare me for an interview:

- send me all relevant links

- send me a checklist for the interview process

- look at the CV for the candidate and point out anything I might be interested in pursuing

Where to look, for each candidate:

- The calendar event: time, stage (pairing, technical, culture fit, from the title), co-interviewers,
  Meet link, and the attachments and description links (CV, candidate folder, notes doc, scoring
  board).
- The CV and the notes doc, with the Drive connector.
- Work Gmail from the last 30 days for the candidate's name: the recruiter thread (salary, notice
  period, how earlier stages went and who ran them) and Ivana's Jira mentions, which give the
  ticket (`CE-N`, link `https://container-solutions.atlassian.net/browse/CE-N`) and often the
  GitHub handle.
- `people/` in ~/git/gtd, in case Ian already knows them.

Give each interview: time and stage, the links, the checklist for that stage (from the process
doc), what earlier stages said, and the CV points to probe (gaps, moves, claims to test, fit with
consultancy work, conversation openers). Flag an invite Ian hasn't accepted.

## Morning run (`morning`)

`scripts/interview-morning.sh` (launchd, `com.ianmiell.interview-morning`, weekdays at 07:00)
starts `/personal-assistant:interview morning` only when Ian's work calendar has an event with
"interview" in the title today. Ian isn't watching, so:

1. List today's events on the work calendar and keep those with "interview" in the title. If there
   are none, say so in one line and stop: no email, no notification.
2. Prepare every one as in **Preparing Ian**. For a pairing interview, run the fork script with
   `--dry-run` as the last argument (`python3 <plugin>/scripts/interview-fork.py <handle> --dry-run`)
   and never without it: the fork waits for Ian's yes in this session. No handle found: say so.
3. Email the prep with `mcp__claude_ai_Gmail__send_message`, `to`
   `["ian.miell@container-solutions.com"]` only, never anyone else, subject
   `Interview prep: Wed 11 Nov - James Shelbourne 12:15, Thomas Reilly 15:00`, as `htmlBody`: "All
   times GMT" (or BST) at the top, an `<h3>` per interview in time order, then `<ul>` lists for
   links, checklist and things to probe. End with any fork waiting for a yes and how to answer:
   `claude attach <session>` (the session name is `interview-Ddd-DD-Mon`). If a calendar, CV or the
   mail couldn't be read, still send, and say at the top what's missing.
4. Notify Ian in two ways, with one message, one line, under 200 characters, no markdown and no
   double quotes, e.g. `Interview prep emailed (Wed 11 Nov): 12:15 James Shelbourne (technical),
   15:00 Thomas Reilly (technical). Fork for Rabia waiting for your yes.`
   - `PushNotification` with `status: "proactive"`. A "not sent" result is fine.
   - `osascript -e 'display notification "<message>" with title "Interview prep" sound name "Glass"'`
5. Then wait. If Ian attaches and says yes to a fork, run it for real; after the interview, remove
   access as below.


## Forking the exercise repo (pairing interviews)

Step 3 of the process doc: before a pairing interview, fork `ContainerSolutions/API-Exercise` as
`API-Exercise-<candidate GitHub handle>` and give the candidate write access. Afterwards, remove
their access. `scripts/interview-fork.py` (in the plugin's `scripts/`) does both:

- `interview-fork.py [HANDLE]` forks and invites the candidate with write access.
- `interview-fork.py [HANDLE] --remove` removes their access and cancels any pending invitation.
- `--dry-run` shows what would happen without changing anything; `--yes` skips the y/n prompt.

The handle isn't on the CV or the calendar invite. Look in the candidate folder and the calendar
description first. If it isn't there, ask Ian for it (Ivana or the recruiter can supply it), and
never guess one. The script exits with status 2 and "needs input" when it has no handle, and
checks the handle is a real GitHub user before doing anything.

Forking and inviting are outward-facing, so when preparing Ian: run `--dry-run` with the handle,
show him the result, and run it for real only once he says yes. Include both the fork and the
removal in the checklist, with the status of the fork.

## After the interview: remove the candidate's access

Ian has said the candidate's access to their repo must always be removed once the pairing session
is over (Step 3.4 of the process doc). This is standing permission: don't ask again.

Do it when Ian says the interview is over, asks to write it up or score it, or the scheduled end
time has passed and he is back in the session:

1. Run `scripts/interview-fork.py --list` to see which `API-Exercise-<handle>` forks still have
   outside access. The one for today's candidate is named after their handle.
2. Run `scripts/interview-fork.py <handle> --remove --yes`. It removes the collaborator and cancels
   any pending invitation, and says if there was nothing to remove.
3. Run `--list` again to confirm the repo shows "no outside access", and tell Ian it's done.

Only remove access for the candidate being interviewed. If `--list` shows other people with access
from earlier interviews, tell Ian rather than removing them without being asked. The repo itself
stays, as it holds the candidate's work for the scoring and debrief; don't delete it.

Then the rest of the post-interview checklist: complete the scoring board, move the Jira ticket
to the next stage (or to rejected with a reason), and add light notes to the ticket.
