---
name: interview
description: Prepare for, run notes for, and write up interviews Ian conducts with candidates to work at Container Solutions. If there is a calendar entry that has the word 'interview' and was created by ivana@container-solutions.com then this skill should be triggered.
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
