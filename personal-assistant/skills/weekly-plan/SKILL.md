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
included briefly. Times are Europe/London. Calendar times come back in UTC
(`...Z`): add an hour while British Summer Time is on.

## Gather

Run these together.

1. **Work calendar:** `mcp__claude_ai_Google_Calendar__list_events` with
   `calendarId: ian.miell@container-solutions.com`, `startTime` Monday
   00:00, `endTime` the Monday after at 00:00, `orderBy: startTime`.
2. **Personal calendar:** the same with `calendarId: ian.miell@gmail.com`.
   One connector reads both (see the calendar skill).
3. **Tasks:** `$S` is the plugin's `scripts/` folder (`<base>/../../scripts`,
   where `<base>` is this skill's base directory). Run, from `~/git/gtd`:
   - `python3 $S/gtd-list.py open` for todo and waiting, with priorities
     and flags
   - `python3 $S/gtd-list.py reminders <today> <Friday>` for reminders
     falling due before the week ends, including overdue ones
4. Read the last 12 or so non-blank lines of `tasks/<N>/notes.md` for each
   high-priority todo, each overdue task and each reminder due that week,
   so the plan can say what the next step is. Don't read the whole of
   `tasks/`.

## Plan

- Drop events Ian declined, and Reclaim "Personal Commitment" blocks that
  only mirror another event at the same time. Keep all-day and evening
  events (talks, dinners, visits).
- **Clashes:** two accepted events that overlap, or an in-person event
  whose location makes the next one impossible. Say which one to move and
  to which free slot.
- **Free blocks:** gaps of 90 minutes or more between 09:00 and 17:30.
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

Email the plan with `mcp__claude_ai_Gmail__send_message`, `to`
`["ian.miell@container-solutions.com"]` only, subject
`Weekly plan: Mon D – Fri D Mon` (e.g. `Weekly plan: Mon 2 – Fri 6 Nov`),
as `htmlBody` with `<h3>` per section and `<ul>` lists, "All times GMT"
(or BST) at the top. Never send to anyone else.

- **`sunday`** (the unattended run): send straight away, then end with a
  short summary of the plan and the Gmail message id. If a calendar or the
  task list couldn't be read, still send, and say at the top of the email
  what's missing.
- **`noemail`:** show the plan in the conversation and send nothing.
- **Otherwise:** show the plan, then send it, unless Ian asked not to.

Then offer, without doing it, to move a clashing meeting, block focus time
or push back reminders that won't fit.
