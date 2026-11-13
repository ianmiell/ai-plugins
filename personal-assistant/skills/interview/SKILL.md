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

Start with the calendar, through `interview-gather.py` in the plugin's `scripts/` folder
(`$S` is `<base>/../../scripts`, where `<base>` is this skill's base directory):

```bash
python3 $S/interview-gather.py --gog [--date YYYY-MM-DD]
```

`--gog` reads the work calendar with gog. If that fails (it prints a `missing:` line), use
`list_events` on `ian.miell@container-solutions.com` for the day instead and pass the result
with `--work <file>` (the path the harness saved it to, or `-` with a heredoc for a small
inline result; see the calendar skill, step 2). For each event with "interview" in the title
it prints the local time, stage from the title, `from Ivana: yes/no`, Ian's response, the
co-interviewers and theirs, the candidate, the Meet link, the links in the description and
attachments, `CE-N` tickets with their Jira links, the candidate's `people/` file if any, and
the subject line for the email. Use those rather than reading the raw event.

**Interviews not from Ivana.** Ivana (`ivana@container-solutions.com`) creates the hiring
interviews. An entry marked `from Ivana: no` may be something else (an internal
interview, a talk, someone else's process): don't prep it silently and don't drop it
silently. Mention it with its time, title and organiser, and ask Ian whether to prep it.
In the morning run, list it in the email under "Also on the calendar" with that question,
and prep only the `from Ivana: yes` ones.

Where to look, for each candidate:

- The calendar event: time, stage (pairing, technical, culture fit, from the title), co-interviewers,
  Meet link, and the attachments and description links (CV, candidate folder, notes doc, scoring
  board).
- The CV and the notes doc, with the Drive connector.
- Work Gmail from the last 30 days for the candidate's name: the recruiter thread (salary, notice
  period, how earlier stages went and who ran them) and Ivana's Jira mentions, which give the
  ticket (`CE-N`, link `https://container-solutions.atlassian.net/browse/CE-N`) and often the
  GitHub handle. Save the threads' text to files under `/tmp/` and run
  `interview-gather.py ... --mail-file <file>` (repeatable): it lists the GitHub handles that
  are literally written there (a github.com/<handle> link, or "GitHub: handle"), with the line
  each came from, and the `CE-N` tickets. A handle it doesn't list isn't in the mail: never
  guess one.
- `people/` in ~/git/gtd, in case Ian already knows them.

Give each interview: time and stage, the links, the checklist for that stage (from the process
doc), what earlier stages said, and the CV points to probe (gaps, moves, claims to test, fit with
consultancy work, conversation openers). Flag an invite Ian hasn't accepted.

## Morning run (`morning`)

`scripts/interview-morning.sh` (launchd, `com.ianmiell.interview-morning`, weekdays at 07:00)
starts `/personal-assistant:interview morning` only when Ian's work calendar has an event with
"interview" in the title today. Ian isn't watching, so:

1. Run `python3 $S/interview-gather.py --gog` (or `--work <file>` from `list_events`, as above).
   If it prints "no interviews", say so in one line and stop: no email, no notification. Prep the
   ones marked `from Ivana: yes`; the others go in the email as questions (see **Interviews not
   from Ivana**). If every one is `from Ivana: no`, still send the short email asking about them,
   and notify.
2. Prepare every one as in **Preparing Ian**. For a pairing interview, run the fork script with
   `--dry-run` as the last argument (`python3 <plugin>/scripts/interview-fork.py <handle> --dry-run`)
   and never without it: the fork waits for Ian's yes in this session. No handle found: say so.
3. Write the prep as simple markdown: a `##` heading per interview in time order, then `-` lists
   for links, checklist and things to probe; then "Also on the calendar" for entries not from
   Ivana; end with any fork waiting for a yes and how to answer: `claude attach <session>` (the
   session name is `interview-Ddd-DD-Mon`). Turn it into the email with
   `python3 $S/pa-mail-html.py --kind interview --date <today> --detail "<the gather script's
   subject names and times, e.g. Jane Doe 12:15, John Roe 15:00>" [--missing "the CV"] <<'MD'`
   ... `MD`. It prints JSON with `to` (always `["ian.miell@container-solutions.com"]`),
   `subject` (`Interview prep: Wed 11 Nov - Jane Doe 12:15, John Roe 15:00`) and `htmlBody`
   ("All times GMT" or BST at the top). Send those three fields unchanged with
   `mcp__claude_ai_Gmail__send_message`, never to anyone else. If a calendar, CV or the mail
   couldn't be read, still send, with `--missing` for each so the top says what's missing.
4. Notify Ian in two ways, with one message, one line, e.g. `Interview prep emailed (Wed 11 Nov):
   12:15 Jane Doe (technical), 15:00 John Roe (pairing). Fork for John waiting for your yes.`
   Mention any entry not from Ivana ("1 more not from Ivana: prep it?").
   - `python3 $S/pa-notify.py --title "Interview prep" --sound Glass "<message>"` shows it in
     Notification Centre and prints the cleaned one-line text (under 200 characters, no
     markdown, no double quotes; apostrophes are safe).
   - `PushNotification` with `status: "proactive"` and that printed text. A "not sent" result is
     fine.
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
