# Newsletters Ian doesn't read go to the trash

The senders with bucket `trash` in `senders.tsv` (next to this file) always go
under UNSUBSCRIBE / JUNK with the action `→ Trash`, never Read later or
Archive. As of October 2026:

- The Week (`info@newsletter.theweek.co.uk`), e.g. "Evening Review"
- The Prof G Pod (`profgmedia+prof-g@substack.com`). Not the Prof G Markets
  newsletter, which Ian reads (see read-later-stays-in-inbox.md).
- FINOS community newsletter (`karl.moll@finos.org`), e.g. "TWAF: ..."
- Scott Galloway's own newsletter (`profgmedia@substack.com`), e.g. "Signal-ing
  Our Thanks". Not Prof G Markets, which Ian reads.

`scripts/mail-gather.py` marks their threads `[trash]`.

Still list them in the triage batch, and trash only once Ian approves it, like
any other action. When Ian says he doesn't read another newsletter, add a
`trash` line for it to `senders.tsv` (that's what the scripts read), and to the
list above.
