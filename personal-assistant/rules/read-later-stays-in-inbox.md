# Read later stays in the inbox, starred

Ian doesn't use a "Read later" label. An email worth reading but needing no
action (newsletters Ian reads, interesting discussion threads, articles sent
to self) stays **in the inbox** and is **starred**.

- Never create or apply a `Read later` label.
- Don't archive these threads, even though nothing needs doing.
- In the triage list, show them under READ LATER with the action
  `→ Keep + star`.

## Newsletters Ian reads

Always READ LATER (keep + star), never junk or archive by default. They're the
`read-later` lines of `senders.tsv` (next to this file), which
`scripts/mail-gather.py` marks `[read-later]`. As of October 2026:

- Our World in Data (`newsletter@ourworldindata.org`), including "Data Insight" emails
- The Rest Is History (`therestishistory@mail.beehiiv.com`)
- Prof G Markets (`profgmedia+markets-newsletter@substack.com`), by Scott Galloway & Ed Elson.
  Not the Prof G Pod, which goes to the trash (see newsletters-to-trash.md)
- Benedict Evans (`list@ben-evans.com`), "Benedict's Newsletter"
- Unsupervised Learning by Daniel Miessler (`unsupervised-learning@mail.beehiiv.com`)
- O'Reilly (`reply@et.oreilly.com`), e.g. "This Week in AI" event reminders. The address
  sends O'Reilly's other marketing too, so all of it comes up read later
- Zeihan on Geopolitics (`peterzeihan@creator.patreon.com`)
- London Centric by Jim Waterson (`londoncentric@substack.com`)
- Dan Davies' "Back of Mind" (`backofmind@substack.com`)

When Ian says he reads another newsletter, add a `read-later` line for it to
`senders.tsv` (that's what the scripts read), and to this list.
