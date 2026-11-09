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
show him the result, and run it for real only once he says yes. Removing access after the session
likewise waits for his yes (or his asking for it). Include both the fork and the removal in the
checklist, with the status of the fork.
