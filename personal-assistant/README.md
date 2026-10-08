# personal-assistant

You are Ian Miell's personal assistant. Your job is to help me manage my daily
work and workflows to help me save time and be more effective in my job.

## Layout

```
README.md               - this readme file
skills/mail/SKILL.md    - /mail: triage the Gmail inbox and decide what to do with each thread
skills/calendar/SKILL.md - /calendar: combined work + personal agenda, clashes, invites, booking
skills/gtd/SKILL.md      - /gtd: drive the gtd task system in ~/git/gtd; used by mail and calendar
rules/*.md              - standing preferences the skills must follow (e.g. starring)
hooks/hooks.json        - SessionStart hook: with PA_MAIL_EVERY=<minutes> set, schedules /mail
                          (new mail only) every N minutes for the session (hooks/schedule-mail.sh)
```
