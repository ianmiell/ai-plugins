# personal-assistant

You are Ian Miell's personal assistant. Your job is to help me manage my daily
work and workflows to help me save time and be more effective in my job.

## Layout

```
README.md               - this readme file
skills/mail/SKILL.md    - /mail: triage the Gmail inbox and decide what to do with each thread
skills/calendar/SKILL.md - /calendar: combined work + personal agenda, clashes, invites, booking
skills/gtd/SKILL.md      - /gtd: drive the gtd task system in ~/git/gtd; used by mail and calendar
skills/slack/SKILL.md    - /slack: triage Slack DMs, mentions and threads; drafts replies, never sends
skills/meeting/SKILL.md  - /meeting: name a new recording after its calendar event, move it in for transcription, delete the .mkv, act on the transcript
scripts/                - launchd agent that opens /meeting in iTerm2 when a new recording or transcript appears
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
