# personal-assistant

You are Ian Miell's personal assistant. Your job is to help me manage my daily
work and workflows to help me save time and be more effective in my job.

## Layout

```
README.md               - this readme file
skills/mail/SKILL.md    - /mail: triage the Gmail inbox and decide what to do with each thread
skills/mail/voice.md     - how Ian writes email (work and personal), used for every mail draft
skills/calendar/SKILL.md - /calendar: combined work + personal agenda, clashes, invites, booking
skills/gtd/SKILL.md      - /gtd: drive the gtd task system in ~/git/gtd; used by mail and calendar
skills/slack/SKILL.md    - /slack: triage Slack DMs, mentions and threads; drafts replies, never sends
skills/meeting/SKILL.md  - /meeting: name a new recording after its calendar event, move it in for transcription, delete the .mkv, act on the transcript
skills/linkedin-sync/    - /linkedin-sync: add new LinkedIn connections to gtd people notes and suggest their levels; with Premium, invite recent profile viewers to connect
scripts/                - launchd agents: /meeting when a new recording or transcript appears, /linkedin-sync every Monday
rules/*.md              - standing preferences the skills must follow (e.g. starring)
```

## Meeting watcher

`scripts/install-meeting-watch.sh` installs a launchd agent that watches
`~/Movies/meetings-inbox` (OBS's recording path) and `~/git/gtd/meetings`.
When OBS finishes remuxing a new `YYYYMMDD_HHMM.mp4` in the inbox, or a bare
`YYYYMMDD_HHMM.txt` transcript appears in the meetings folder, it opens an
iTerm2 window running `claude '/personal-assistant:meeting <stem>'`. The
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
profile viewer since the last sync who isn't already a connection, at most
20 a run, carrying the rest over to the next. The last sync time is in
`~/.local/state/personal-assistant/linkedin-sync-last` and every invitation
tried is logged in `~/.local/state/personal-assistant/linkedin-invites.log`.
Run it now with
`launchctl kickstart gui/$(id -u)/com.ianmiell.linkedin-sync`, remove it
with `scripts/install-linkedin-sync.sh --uninstall`. The log is
`~/Library/Logs/com.ianmiell.linkedin-sync.log`.
