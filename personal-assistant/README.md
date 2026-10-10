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
bin/pa-mail             - fixed commands for the personal mailbox via gog (list, read, archive, star,
                          label, trash...); can't send mail
bin/pa-gtd              - fixed commands for ~/git/gtd (find, show, new, note, defer, status, push)
rules/*.md              - standing preferences the skills must follow (e.g. starring)
hooks/hooks.json        - SessionStart hook: with PA_MAIL_EVERY=<minutes> set, schedules /mail
                          (new mail only) and /slack every N minutes for the session (hooks/schedule-mail.sh)
```

## Prompt-free runs

`/mail`, `/slack`, `/calendar` and `/gtd` run their shell work through `pa-mail` and
`pa-gtd` (on PATH while the plugin is enabled), one command per Bash call, so a short
allowlist covers them. Each skill's `allowed-tools` pre-approves its tools for the turn it
runs in. For scheduled runs and follow-up turns, add the same rules to
`~/.claude/settings.json` under `permissions.allow` (plugins can't ship permission rules):

```json
"Bash(pa-mail *)",
"Bash(pa-gtd *)",
"mcp__claude_ai_Gmail__search_threads", "mcp__claude_ai_Gmail__get_thread",
"mcp__claude_ai_Gmail__list_labels", "mcp__claude_ai_Gmail__label_thread",
"mcp__claude_ai_Gmail__unlabel_thread", "mcp__claude_ai_Gmail__create_label",
"mcp__claude_ai_Gmail__trash_thread", "mcp__claude_ai_Gmail__mark_thread_spam",
"mcp__claude_ai_Gmail__create_draft", "mcp__claude_ai_Gmail__list_drafts",
"mcp__claude_ai_Gmail__get_draft",
"mcp__claude_ai_Google_Calendar__list_calendars", "mcp__claude_ai_Google_Calendar__list_events",
"mcp__claude_ai_Google_Calendar__search_events", "mcp__claude_ai_Google_Calendar__get_event",
"mcp__claude_ai_Google_Calendar__suggest_time",
"mcp__claude_ai_Slack__slack_read_user_profile", "mcp__claude_ai_Slack__slack_search_public_and_private",
"mcp__claude_ai_Slack__slack_read_channel", "mcp__claude_ai_Slack__slack_read_thread",
"mcp__claude_ai_Slack__slack_list_user_channels", "mcp__claude_ai_Slack__slack_search_users",
"mcp__claude_ai_Slack__slack_send_message_draft"
```

Left out on purpose, so they still ask: sending or forwarding email, posting, scheduling or
reacting in Slack, and accepting, creating, moving or cancelling calendar events (all of
these reach other people), plus raw `gog` and `bin/gtd` commands the scripts don't cover.
The skills' own rules still require Ian's approval in the conversation before any change.
