# House style for gtd tasks and notes

Tasks, people notes and log lines in the gtd repo should read as if the owner
typed them between meetings: short, first person or no subject at all, and
easy to scan in a terminal. These rules come from comparing several years of
hand-written tasks and people notes with recent agent-written ones.

## Task subjects

- Start with a category prefix from `.metadata/categories`: `CS:` (day job),
  `MC:` (own company and side work), `HOME:` (personal). `MEETING:` subjects
  are made by the calendar sync. Don't type one by hand.
- After the prefix, the subject is a short handle, not a summary. Most
  hand-written ones are about 25 characters, and few go past 45.
- Verb first when there is an action (`Chase`, `Book`, `Pay`, `Review`,
  `Follow up with`). A bare noun is fine for a topic or project (`HOME: shelving`).
- Capitalisation is loose: a capital after the prefix is common, lower case
  is fine too. No full stop at the end.
- Keep dates, amounts, email subjects and reasons out of the subject. They go
  in the body. A short date is fine when it is the point (`... (nov 16th)`).
- Good: `CS: Chase [name] re SoW`, `MC: Invoice [client] for March`,
  `HOME: cancel gym`, `CS: [client] demo prep`.
- Bad: `CS: Waiting for [name] ([client]) intro to [name] re product`,
  `HOME: Fix website (down since 3 Mar ~09:10)`.

## Task notes

- The first lines are fixed: `# <subject>` then `Task Number: N`. After that it is
  free-form markdown.
- Paste links bare, one per line, often with no label at all. A word or two
  first is enough (`Proposal doc:`, `Email:`).
- Write in fragments: `Awaiting quote`, `Asked [name] on slack`,
  `Sent calendly link.`, `Chase in 3 months.` First person (`I`, `me`) or no
  subject. Never refer to the owner by name in the third person.
- Mark status with an upper-case word at the end of a line: `DONE`, `TODO`,
  `DOING`, `WAITING`, `SENT`, `ABANDONED`, `KEEP IN MIND`, `NFA`. `TODO:` at
  the start of a line is an open action, and the task can't close while one is left.
- Use lists only for real lists: who to ask, items to buy, agenda points,
  numbers. `##` headings only in long reference notes (measurements, plans).
- Opinions and asides are welcome and short (`Screenshots look fake to me.`).
- Copy-pasted text (a quote from an email, a booking reference) goes in as is,
  in quotes or on its own lines. Don't rewrite it.

## Updating a task

- Add new lines at the bottom (or next to the item they update). Don't rewrite
  what is already there.
- Hand-written updates usually have no date: `Chased again.`,
  `Response received - they'll get back to me.` When a date helps, put it first
  as `YYYY-MM-DD:` and keep the update to one line.
- Mark an item done by adding `DONE` at the end of its line. Don't delete it.
- Waiting on someone: one line saying who and what (`Waiting on [name] for CVs`),
  and move the task to `waiting`. A follow-up date goes in a reminder, not in prose.

## People notes and log lines

- Free text sits under the `- Key: value` lines. It is one to three short
  lines: where we met, what they do, one thing worth remembering.
  `Met at [conference] 2024. Platform lead at [client].`
  `Worked with at [client]. Sharp.` `See 1234` (a task number).
- Log lines are one line each, newest last, under `### Meeting log` /
  `### Email log`:
  `- YYYY-MM-DD (meeting): <what happened> [meetings/<file>.txt]`
  `- YYYY-MM-DD (email, work): <what happened> [task N]`
- Each line says what they did or want, in about 10 to 20 words. Leave out
  everyone else who was there and the background story.

## Where Claude's notes drift from Ian's

| Don't | Do |
|------|----|
| 60-100 character subjects with names in brackets, dates and reasons | A 2-5 word handle after the prefix |
| `Ian followed up with...`, `Ian said he'd...` | `Followed up.` / `I said I'd book it.` |
| Saying where it came from: `From meeting "...", 3 Mar.` | Just the transcript path or link, if it is needed at all |
| Job titles and companies for everyone mentioned | First names. The people file has the rest |
| Restating the email in full sentences | The ask in one fragment, plus the link |
| A dated paragraph for every update | `Chased again.`, or one dated line if the date matters |
| `Related: #N (...)` with a description | `See N` |
| `## Why` / `## Check` sections for a small task | Two or three lines |
| Semicolons, nested brackets, ~ and ≤ | Plain words, dashes, `eg`, `?` for things you're not sure of |

## Invented examples

```
# CS: Chase [name] re pilot
Task Number: 1234

https://mail.google.com/...
Sent deck, awaiting response.
Asked [name] if [client] still has budget DONE
Chased again.
```

```
# HOME: boiler service
Task Number: 1235

Engineer due Thurs am?
TODO: find warranty docs
Quote seems high, get a second one.
```

People note: `Met at a meetup. Runs a small platform consultancy.`
Log line: `- 2026-03-02 (email, work): Wants a demo next week [task 1234]`
