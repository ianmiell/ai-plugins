# Note meaningful email interactions in gtd people files

When someone meaningfully interacts with Ian by email, add a short note
about it to their file in `~/git/gtd/people/Firstname_Lastname.md`. This
is a standing instruction, so no per-note approval is needed. List the notes
added in the run's report.

**Meaningful** means a real person engaging with Ian about something of
substance: a proposal, an offer, a request or decision, an introduction, a
change of role or company, or a meeting booked with them. Not meaningful:
newsletters, automated notifications, out-of-office replies, calendar
accept/decline notices, routine HR-tool notices, or Ian's own mail to
himself. Colleagues count when the exchange is substantive (e.g. proposing
a CCF demo), not for routine admin.

**How to write it:**
- Find the file by name: `ls ~/git/gtd/people | grep -i 'Firstname_Lastname'`,
  and also try the email address via `grep -li '<address>' people/*.md`.
  Watch for changed names (e.g. Louise Corrigan → Louise Cox) and
  `_2` duplicates.
- Append to the end of the file, under a `### Email log` heading (add the
  heading once if it isn't there). Never edit inside the
  `## managed by linkedin_tools` … `### managed by linkedin_tools` block.
- One line per interaction:
  `- YYYY-MM-DD (email, work|personal): <one-sentence summary> [task N]`.
  Keep it factual and short. Don't paste email bodies.
- Then run `bin/gtd push` once for all the notes (gtd handles git).

**If no file exists:** don't create one. Tell Ian, and suggest one of:
- create it (`gtd people new Firstname_Lastname` is interactive, so Ian runs
  it, or Claude writes the file in the usual `## Name` / `- Email:` /
  `- Company:` format after a yes),
- it's a duplicate under another spelling (name the candidate), or
- skip, because the contact is one-off.
