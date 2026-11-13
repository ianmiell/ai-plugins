---
name: weekly-plan
description: Plan Ian's coming working week (Monday to Friday) from both Google calendars and his open gtd tasks, and email the plan to his work address. Flags clashes and overbooked days, finds the free blocks for deep work, slots the high-priority todos and the reminders falling due into specific days, and lists what can wait. Use when Ian asks for a plan for next week, "plan my week", or invokes /weekly-plan; the weekly-plan launchd agent opens a session with "/personal-assistant:weekly-plan sunday" every Sunday evening. Optional argument: "sunday" (the unattended run, which emails without asking), "noemail" (show the plan only), or a Monday date, e.g. "/weekly-plan 2026-11-09".
---

# Weekly plan

Turn next week's two calendars and the open gtd tasks into one day-by-day
plan, then email it to Ian. Read only: change no task, event or reminder.

## The week

The week is the next Monday to Friday after today (on a Monday, that
Monday's week), unless the argument names a Monday. The weekend after it is
included briefly. Times are Europe/London. Don't convert calendar times by
hand: the gather script below shows every time in London time with GMT or
BST per day, which is right across the late-October and late-March clock
changes too.

`$S` is the plugin's `scripts/` folder (`<base>/../../scripts`, where
`<base>` is this skill's base directory).

## Gather

1. `python3 $S/weekly-plan-gather.py --window-only` (add `--monday
   YYYY-MM-DD` when the argument names one) prints the week, the email
   subject and the `startTime` / `endTime` for `list_events`.
2. In one message, `mcp__claude_ai_Google_Calendar__list_events` with
   `calendarId: ian.miell@container-solutions.com` and with
   `calendarId: ian.miell@gmail.com`, both with that `startTime` and
   `endTime`, `orderBy: startTime`, `pageSize: 250`. One connector reads
   both (see the calendar skill).
3. A week of W is usually too big to come back inline, so the harness
   saves it to a file and gives the path. Pass that path as it is; don't
   open it or write jq or python against it. A result that did come back
   inline goes in on stdin as `-` with a heredoc, pasted exactly as
   returned (only one calendar can use stdin; save the other with Write to
   a file under `/tmp/` first). A `nextPageToken` means another page:
   fetch it and pass it too (`--work` and `--personal` repeat). Then, from
   `~/git/gtd`:

   ```bash
   python3 $S/weekly-plan-gather.py --work <W file> --personal <P file or -> [--monday YYYY-MM-DD]
   ```

   It prints, in one go: `missing:` lines for anything it couldn't read;
   the clashes across both calendars; each day Mon to Sun with its zone,
   the agenda lines (declined events left out, W+P for the same event on
   both, FREE, PENDING, TIGHT), the hours booked, and on weekdays the free
   blocks of 90 minutes or more between 09:00 and 17:30; the reminders
   from today to Friday; the open todo and waiting tasks with priorities
   and flags (`gtd-list.py`); and the last 12 non-blank lines of notes for
   each high-priority todo, each overdue task and each reminder due that
   week, so the plan can say what the next step is.

Use its times, clashes and free blocks as they are; don't work them out
again from the raw events. Don't read the whole of `tasks/`.

## Plan

- Declined events are already left out. Also leave out Reclaim "Personal
  Commitment" blocks that only mirror another event at the same time (the
  script reports them as clashes). Keep all-day and evening events (talks,
  dinners, visits).
- **Clashes:** the script's CLASHES (two busy events that overlap) and
  TIGHT flags (an in-person event whose location makes the next one hard).
  Say which one to move and to which free slot.
- **Free blocks:** the script's `free` line for each weekday.
- **Shape of the week:** 3 to 5 bullets: the big fixed points, the
  overbooked days, the free blocks.
- **Day by day, Mon to Fri:** meetings worth noting (not every daily
  standup), plus what to do in the free blocks: high-priority todos first,
  especially anything with a deadline that week or the next (deadlines
  often sit in the subject, e.g. "(nov 16th)"), then prep for that week's
  meetings, then reminders due that day. Put items that need someone,
  such as a question for JOD, on the day of a meeting with them. Refer to
  tasks as `#N` with a few words of subject.
- **Weekend:** fixed events plus a HOME task or two.
- **Not this week:** medium and low todos that can wait, one line.

Keep it to what fits on a screen or two. Don't invent facts: if a task's
notes don't say what the next step is, use the subject.

## Deliver

Write the plan as simple markdown (`##` per section, `-` lists, `**bold**`,
links) and turn it into the email with:

```bash
python3 $S/pa-mail-html.py --kind weekly --date <Monday> [--missing "personal calendar"] <<'MD'
<the plan>
MD
```

It prints JSON with `to` (always `["ian.miell@container-solutions.com"]`),
`subject` (`Weekly plan: Mon 2 – Fri 6 Nov`) and `htmlBody` (escaped, with
"All times GMT", or BST, or both across a clock change, at the top, and a
Missing line first when `--missing` is given, once per thing missing). Pass
those three fields unchanged to `mcp__claude_ai_Gmail__send_message`. Never
send to anyone else.

- **`sunday`** (the unattended run): send straight away, then end with a
  short summary of the plan and the Gmail message id. If a calendar or the
  task list couldn't be read (a `missing:` line from the gather script, or
  a `list_events` error), still send, with `--missing` for each, so the
  top of the email says what's missing.
- **`noemail`:** show the plan in the conversation and send nothing.
- **Otherwise:** show the plan, then send it, unless Ian asked not to.

Then offer, without doing it, to move a clashing meeting, block focus time
or push back reminders that won't fit.
