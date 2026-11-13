# Emails outside the inbox are unstarred

A starred thread must be in the inbox. When a thread leaves the inbox
(archived, trashed, spam, or moved under a label), remove its star in the
same operation:

- Connector: `unlabel_thread` with `["INBOX", "STARRED"]`.
- gog: `gmail thread modify <id> --remove INBOX,STARRED`.

`mail-apply.py` records every star it sets (in
`~/.claude/personal-assistant/starred-by-pa.tsv`), so stars outside the inbox
can be told apart: `scripts/mail-gather.py starred-outside` lists the
`is:starred -in:inbox` threads for the gog mailboxes, marking which this
plugin starred.

- Starred by this plugin: unstar them, no need to ask (the thread left the
  inbox some other way, e.g. Ian archived it in Gmail). The command prints the
  `mail-apply.py` lines that do it.
- Older stars (and every star on the connector mailbox, which has no record):
  list them and offer to unstar them. Don't unstar them unasked, because they
  may predate this rule.
