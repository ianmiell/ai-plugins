# personal-assistant

You are Ian Miell's personal assistant. Your job is to help me manage my daily
work and workflows to help me save time and be more effective in my job.

## Layout

```
README.md               - this readme file
skills/comms/SKILL.md   - /comms: everything at once (both mailboxes, Slack, WhatsApp, LinkedIn, pending invites) in one list and one round of approvals; the usual starting point
skills/mail/SKILL.md    - /mail: triage the Gmail inbox and decide what to do with each thread
skills/calendar/SKILL.md - /calendar: combined work + personal agenda, clashes, invites, booking
skills/gtd/SKILL.md      - /gtd: drive the gtd task system in ~/git/gtd; used by mail and calendar
skills/slack/SKILL.md    - /slack: triage Slack DMs, mentions and threads; drafts replies, never sends
skills/whatsapp/SKILL.md - /whatsapp: triage WhatsApp from the desktop app's local database (read only); drafts open in the app for Ian to send
skills/meeting/SKILL.md  - /meeting: name a new recording after its calendar event, move it in for transcription, delete the .mkv, act on the transcript
skills/write/SKILL.md    - /write: draft LinkedIn posts and messages, blog posts and articles, PR review comments in Ian's voice; /write check reviews a draft
skills/linkedin-sync/    - /linkedin-sync: add new LinkedIn connections to gtd people notes and suggest their levels; with Premium, invite recent profile viewers to connect
voices/*.md             - how Ian writes: common.md (shared core) plus email, slack, whatsapp, linkedin, writing, review and notes; read before any draft
scripts/whatsapp.py     - read-only queries on WhatsApp's local database (chats, read, search, mine) and draft hand-off (whatsapp://send or clipboard)
scripts/voice-check.py  - mechanical check of a draft against the voices (em dashes, banned phrases, US spelling, emoji, length)
scripts/pa-env.py       - start-of-run checks in one call: machine, gog mailbox access, WhatsApp, Slack/WhatsApp windows; `mark` records a run
scripts/mail-gather.py  - inbox threads via gog, compactly, with a first-pass hint from the house rules; `read` gives a thread as plain text
scripts/mail-apply.py   - approved archive/keep/trash/spam/label/GTD-N actions via gog, with the star rules built in
scripts/gtd-find.py     - open gtd tasks mentioning names, thread ids or subject words (`--batch` for a whole triage run)
scripts/gtd-new-task.py - new gtd task with its source link and notes; for email, labels the thread GTD-<N> and archives it
scripts/gtd-label-tidy.py - archive the mail of closed tasks and remove their GTD-<N> labels (rules/close-task-tidies-mail.md)
scripts/people-note.py  - find a person's gtd people file and add an email/slack/whatsapp/meeting log line in the right place
scripts/meeting-files.py - the meeting skill's file steps: pending, plan/apply names, .mkv checks, wait for the transcript, dedupe
scripts/pa_common.py    - shared helpers for the scripts above (mailboxes, gog with --gmail-no-send, gtd paths)
scripts/                - launchd agents: /meeting when a new recording or transcript appears, /linkedin-sync every Monday
skills/linkedin-sync/linkedin-state.py - linkedin-sync bookkeeping: window, invite queue and log, local evidence for levels
rules/*.md              - standing preferences the skills must follow (e.g. starring)
rules/senders.tsv       - newsletter and notification senders the mail scripts sort without reading
tests/                  - `python3 -m unittest discover -s personal-assistant/tests`: the scripts against made-up fixtures and a fake gog
```

## Scripts

The scripts do the deterministic parts of the skills (gog calls, gtd file
lookups, house-rule bookkeeping, file moves), so the model reads a few compact
lines instead of raw API JSON and repeated greps. gog always runs with
`--gmail-no-send`. They read Ian's real mail and gtd repo by default;
`GTD_DIR`, `PA_STATE`, `PA_GOG`, `MEETINGS_INBOX` and `PA_LINKEDIN_STATE`
point them elsewhere, which is what the tests do. Run the tests with:

```
python3 -m unittest discover -s personal-assistant/tests -v
```

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

`scripts/install-linkedin-sync.sh` installs a launchd agent that opens an
iTerm2 window running `claude '/personal-assistant:linkedin-sync'` every
Monday at 08:30 (on waking, if the Mac was asleep). The skill reads
LinkedIn's Recently added connections page in Chrome, through Claude in
Chrome, back to the newest connection already in `~/git/gtd/people`, adds
the new people with `gtd import-connections --auto`, and suggests a level
for each from the calendars, meeting transcripts and email. If the account
has LinkedIn Premium, it also sends a connection request (no note) to each
profile viewer since the last sync who isn't already a connection, carrying
over to the next run anyone it doesn't get to. Then it invites the people
LinkedIn suggests on the Grow page with the most mutual connections. All
invitations share a budget of about 40 in any 24 hours with Premium
(viewers first), or 10 without (suggestions only). The last sync time is in
`~/.local/state/personal-assistant/linkedin-sync-last` and every invitation
tried is logged in `~/.local/state/personal-assistant/linkedin-invites.log`.
Run it now with
`launchctl kickstart gui/$(id -u)/com.ianmiell.linkedin-sync`, remove it
with `scripts/install-linkedin-sync.sh --uninstall`. The log is
`~/Library/Logs/com.ianmiell.linkedin-sync.log`.
