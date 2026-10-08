# Emails outside the inbox are unstarred

A starred thread must be in the inbox. When a thread leaves the inbox
(archived, trashed, spam, or moved under a label), remove its star in the
same operation:

- Connector: `unlabel_thread` with `["INBOX", "STARRED"]`.
- gog: `gmail thread modify <id> --remove INBOX,STARRED`.

If a triage run finds starred threads outside the inbox (`is:starred
-in:inbox`) that this plugin didn't create, list them and offer to unstar
them. Don't unstar them unasked, because older stars may predate this rule.
