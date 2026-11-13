# personal-assistant

You are Ian Miell's personal assistant. Your job is to help me manage my daily
work and workflows to help me save time and be more effective in my job.

## Layout

```
README.md               - this readme file
skills/comms/SKILL.md   - /comms: everything at once (both mailboxes, Slack, WhatsApp, LinkedIn messages, invitations and unanswered comments on Ian's posts, pending invites, apps with access to his Google accounts) in one list and one round of approvals; the usual starting point
skills/mail/SKILL.md    - /mail: triage the Gmail inbox and decide what to do with each thread
skills/calendar/SKILL.md - /calendar: combined work + personal agenda, clashes, invites, booking
skills/gtd/SKILL.md      - /gtd: drive the gtd task system in ~/git/gtd; used by mail and calendar
skills/slack/SKILL.md    - /slack: triage Slack DMs, mentions and threads; drafts replies, never sends
skills/whatsapp/SKILL.md - /whatsapp: triage WhatsApp from the desktop app's local database (read only); drafts open in the app for Ian to send
skills/meeting/SKILL.md  - /meeting: name a new recording after its calendar event, move it in for transcription, delete the .mkv, act on the transcript
skills/write/SKILL.md    - /write: draft LinkedIn posts and messages, blog posts and articles, PR review comments in Ian's voice; /write check reviews a draft
skills/timesheet/SKILL.md - /timesheet: fill in the weekly Toggl Track timesheet in Chrome (8 h a weekday across CCF, pre-sales and holiday) and submit it for approval after Ian's yes
skills/interview/SKILL.md - /interview: prep a question plan and scorecard for hiring or internal interviews with Container Solutions staff, and write up the notes or transcript as feedback; drafts only
skills/weekly-plan/SKILL.md - /weekly-plan: plan the coming Mon-Fri from both calendars and open gtd tasks, and email it to Ian
skills/linkedin-sync/    - /linkedin-sync: add new LinkedIn connections to gtd people notes and suggest their levels; invite people Ian has emailed who aren't in people/ (personal mail after his yes); with Premium, invite recent profile viewers to connect; follow back followers; pick out the posts in his feed he should respond to
voices/*.md             - how Ian writes: common.md (shared core) plus email, slack, whatsapp, linkedin, writing, review and notes; read before any draft
scripts/whatsapp.py     - read-only queries on WhatsApp's local database (chats, read, search, mine) and draft hand-off (whatsapp://send or clipboard)
scripts/voice-check.py  - mechanical check of a draft against the voices (em dashes, banned phrases, US spelling, emoji, length)
scripts/pa-env.py       - start-of-run checks in one call: machine, gog mailbox access, WhatsApp, Slack/WhatsApp windows, each isolated so one failure doesn't stop the rest; `auth [--notify]` checks just the gog logins; `mark` records a run
scripts/mail-gather.py  - inbox threads via gog, compactly, with a first-pass hint from the house rules; `read` gives a thread as plain text; `starred-outside` lists starred threads out of the inbox, marking the ones this plugin starred
scripts/mail-apply.py   - approved archive/keep/trash/spam/label/GTD-N actions via gog, with the star rules built in; records the stars it sets
scripts/gtd-find.py     - open gtd tasks mentioning names, thread ids or subject words (`--batch` for a whole triage run)
scripts/gtd-new-task.py - new gtd task with its source link and notes; for email, labels the thread GTD-<N> and archives it
scripts/gtd-note.py     - dated note with its source on an existing gtd task, pushed; for email, labels the thread GTD-<N>
scripts/gtd-list.py     - gtd tasks by prefix with review flags (overdue, due soon, untouched); leaves out MEETING: tasks; `reminders FROM TO` for the calendar
scripts/gtd-label-tidy.py - archive the mail of closed tasks and remove their GTD-<N> labels (rules/close-task-tidies-mail.md)
scripts/interview-fork.py - fork the pairing exercise repo for a candidate (ContainerSolutions/API-Exercise-<handle>) and give them write access; `--remove` takes it away after the interview (the skill does this without asking); `--list` shows who still has access; asks for the handle if it isn't given
scripts/people-note.py  - find a person's gtd people file (`find --batch` for a whole run), add an email/slack/whatsapp/meeting log line in the right place, set their level
scripts/meeting-files.py - the meeting skill's file steps: pending, status (a stem's files in both folders, no globs), plan/apply names, whisper check/start, .mkv checks, wait for the transcript, dedupe, save the summary (git add + push)
scripts/pa_common.py    - shared helpers for the scripts above (mailboxes, gog with --gmail-no-send, gtd paths, `tool()` and PATH for launchd sessions)
scripts/pa-notify.py    - macOS notification with the text passed safely to osascript (one line, no markdown, 200 chars); prints the text for PushNotification
scripts/comms-gather.py - /comms in one zsh-safe call: `scope "<arg>"` (channels, queries, windows, what's off here) and `run` (pa-env check, mail list, GTD label tidy, WhatsApp chats side by side, each isolated, failures summarised)
scripts/comms-items.py  - the triage ledger: `add` items, `render` numbered tables (--mail for /mail), `expand "<Ian's answer>"` into the mail-apply plan and other steps, `show`, `next` batch, `notify`
scripts/mail-draft.py   - voice-checked Gmail draft reply or forward through gog, never sent; create_draft arguments for the work connector
scripts/slack-merge.py  - Slack search results into conversations: window, threads, drops Ian-last, self-DMs, bots; links and gtd-find --batch lines
scripts/calendar-events.py - W+P calendars from saved list_events results (or gog): window, agenda with clashes/W+P/pending, free, match (meeting), attendees, verify, access
scripts/weekly-plan-gather.py - the week for /weekly-plan in one print: days in GMT/BST, clashes, free blocks, reminders, open tasks, notes tails, subject
scripts/pa-mail-html.py - markdown plan to {to, subject, htmlBody} for Ian's work address (weekly, interview)
scripts/interview-gather.py - the day's interviews: stage, from Ivana yes/no, people, links, CE-N, people/ file, GitHub handles found in saved mail
scripts/launchd-common.sh - shared by the launchd wrappers: start log line, PATH, network wait, caffeinate, preflight
scripts/install-common.sh - shared by the install-*.sh scripts: copy to ~/.local/share/personal-assistant/launchd, fill in and load the plist
scripts/                - launchd agents: /meeting when a new recording or transcript appears, /linkedin-sync every Monday, /comms every morning, /weekly-plan every Sunday evening, /interview on weekday mornings with an interview, OBS auto-record
skills/timesheet/toggl-grid.js, toggl-fill.js, timesheet.py - read and fill the Toggl grid, propose the split, check the fill and the status
skills/linkedin-sync/preflight.js - checks a new tab is on LinkedIn and signed in before the step's script
skills/comms/extract-google-apps.js, google-apps.py - /comms' Google apps check: read the apps with access to each Google account in Chrome, and track which are new, widened or kept
skills/linkedin-sync/linkedin-state.py - linkedin-sync bookkeeping: window, invite queue and log, follow-back queue and log, email correspondents to look up and match, connections file, data export check and `export --import`, local evidence for levels (with calendar attendees), Gmail queries (`mail-query`), scoring feed posts worth a response; reads the extract scripts' downloads (`--from-download`), says STOP/BUDGET/RERUN after each log line and defers the rest of the queue (`defer --rest`)
rules/*.md              - standing preferences the skills must follow (e.g. starring)
rules/senders.tsv       - newsletter and notification senders the mail scripts sort without reading
tests/                  - `python3 -m unittest discover -s personal-assistant/tests`: the scripts against made-up fixtures and a fake gog
```

## Scripts

The scripts do the deterministic parts of the skills (gog calls, gtd file
lookups, house-rule bookkeeping, file moves), so the model reads a few compact
lines instead of raw API JSON and repeated greps. gog always runs with
`--gmail-no-send`. They read Ian's real mail and gtd repo by default;
`GTD_DIR`, `PA_STATE`, `PA_GOG`, `MEETINGS_INBOX`, `PA_LINKEDIN_STATE` and
`PA_DOWNLOADS` point them elsewhere, and `PA_MACHINE` (`macbook-pro` or
`other`) skips the machine check, which is what the tests do. Run the tests
with:

```
python3 -m unittest discover -s personal-assistant/tests -v
```

The skills run in zsh, through the Bash tool. A separator such as `echo ===`
is an error there, and so is a glob that matches nothing, which aborts the
whole command. The scripts print their own headers and find files
themselves, so the skills don't need either.

## Launchd agents

The install-*.sh scripts copy each agent's wrapper (with
`launchd-common.sh` and anything else it runs) to
`~/.local/share/personal-assistant/launchd/` and point the plist there, so
an agent keeps working whichever branch the checkout is on. Re-run the
installer (with the same time, if it isn't the default) after changing a
wrapper. Each run logs a `started` line first, with the power source and
how long since the Mac woke. launchd runs a missed time on waking only if
the Mac was asleep: when it was shut down, nothing runs and nothing is
logged.

## Meeting watcher

`scripts/install-meeting-watch.sh` installs a launchd agent that watches
`~/Movies/meetings-inbox` (OBS's recording path) and `~/git/gtd/meetings`.
When OBS finishes remuxing a new `YYYYMMDD_HHMM.mp4` in the inbox, or a bare
`YYYYMMDD_HHMM.txt` transcript appears in the meetings folder, it starts a
background Claude Code session running
`claude --bg '/personal-assistant:meeting <stem>'`, which shows up in
`claude agents` and the agent list in Claude Code (`claude attach <id>` opens
it in a terminal). The
skill names the recording and moves it into the meetings folder, where
Whisper Transcription's Watch Folder transcribes it. Remove it with
`scripts/install-meeting-watch.sh --uninstall`. The log is
`~/Library/Logs/com.ianmiell.meeting-watch.log`.

## LinkedIn sync

`scripts/install-linkedin-sync.sh` installs a launchd agent that starts a
background Claude Code session running
`claude --bg --chrome '/personal-assistant:linkedin-sync'` (listed in
`claude agents` and the agent list in Claude Code) every
Monday at 08:30 (on waking, if the Mac was asleep). The skill reads
LinkedIn's Recently added connections page in Chrome, through Claude in
Chrome, back to the newest connection already in `~/git/gtd/people`, adds
the new people with `gtd import-connections --auto`, and suggests a level
for each from the calendars, meeting transcripts and email. If the account
has LinkedIn Premium, it also sends a connection request (no note) to each
profile viewer since the last sync who isn't already a connection, carrying
over to the next run anyone it doesn't get to. Then it invites the people
LinkedIn suggests on the Grow page with the most mutual connections. All
invitations share a budget of about 20 in any 24 hours with Premium
(viewers first), or 10 without (suggestions only), and at most 150 in any
7 days to stay under LinkedIn's weekly invitation limit. Then it follows back
everyone among the newest 200 followers whom Ian doesn't follow yet, at most
25 a day. The last sync time is in
`~/.local/state/personal-assistant/linkedin-sync-last`, every invitation
tried is logged in `~/.local/state/personal-assistant/linkedin-invites.log`,
every correspondent looked up in `linkedin-correspondents.log`,
and every follow-back in `linkedin-follows.log` next to it.
Run it now with
`launchctl kickstart gui/$(id -u)/com.ianmiell.linkedin-sync`, remove it
with `scripts/install-linkedin-sync.sh --uninstall`. The log is
`~/Library/Logs/com.ianmiell.linkedin-sync.log`.

## Morning comms

`scripts/install-comms-morning.sh` installs a launchd agent that starts a
background Claude Code session running
`claude --bg --chrome '/personal-assistant:comms morning'` every day at
05:00 (or another time: `scripts/install-comms-morning.sh 08:15`). The
session is named for the day (`comms-Mon-02-Nov`). It gathers every channel
and does the cross-checks, then stops at the numbered list, with proposed
replies, and waits. Because of `morning`, it then sends a notification
(PushNotification, which reaches the phone when Remote Control is connected,
plus a macOS Notification Centre alert) such as "Comms ready (Mon 02 Nov):
3 act now ... Top: ...". Nothing is drafted, sent, archived or marked until
Ian attaches with `claude attach <id>` and approves. The Slack and WhatsApp
last-run files only move after he has seen the list, so a morning session
he never opens loses nothing: the next `/comms` still covers that window.
The list is as of when it ran, so when attaching later, ask it to pick up
anything newer. Sessions nobody opens stay in `claude agents` until
stopped.

When the Mac is asleep at 05:00, launchd runs the agent on waking (missed
mornings collapse into one run). When it's shut down, that morning is
skipped. On waking, the script waits up to 5 minutes for the network
before starting the session. It keeps the Mac from idle-sleeping while it
waits and for 20 minutes afterwards (`caffeinate -i`), but closing the lid
on battery still sleeps it. To have the list ready before opening the
laptop, `sudo pmset repeat wake MTWRF 04:55:00` may help when the laptop
is on power; test it before relying on it. Run it now with
`launchctl kickstart gui/$(id -u)/com.ianmiell.comms-morning`, remove it
with `scripts/install-comms-morning.sh --uninstall`. The log is
`~/Library/Logs/com.ianmiell.comms-morning.log`.

## Weekly plan

`scripts/install-weekly-plan.sh` installs a launchd agent that starts a
background Claude Code session running
`claude --bg '/personal-assistant:weekly-plan sunday'` every Sunday at
18:00 (or another time: `scripts/install-weekly-plan.sh 19:00`). The
session reads both calendars and the open gtd tasks for the coming Monday
to Friday and emails a day-by-day plan (clashes, free blocks, which todos
and reminders go where) to ian.miell@container-solutions.com. It changes
nothing else. Gmail's `send_message` isn't allowed in the global settings,
so `weekly-plan.sh` grants it to this session alone with
`--allowed-tools`; the skill only sends to Ian. When the Mac is asleep at
18:00, launchd runs it on waking; when it's shut down, that week is
skipped. Run it now with
`launchctl kickstart gui/$(id -u)/com.ianmiell.weekly-plan`, remove it
with `scripts/install-weekly-plan.sh --uninstall`. The log is
`~/Library/Logs/com.ianmiell.weekly-plan.log`. `/weekly-plan noemail`
shows the plan without sending it.

