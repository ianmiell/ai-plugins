# ian-voice

How Ian Miell writes in public about software, packaged so any LLM can draft
or review technical writing as him.

## Layout

```
skills/tech-writing/SKILL.md    - /tech-writing: draft or review a blog post, article, how-to, talk write-up or book prose in Ian's voice
skills/tech-writing/VOICE.md    - the full, self-contained voice description (persona, registers, titles, openings, structure, evidence, code, mechanics, vocabulary, humour, beliefs, endings, checklist)
skills/tech-writing/EXAMPLES.md - annotated real passages and generic-to-Ian rewrites
```

## Using it outside Claude Code

`VOICE.md` doesn't depend on any tools. Paste it (and `EXAMPLES.md` if
there's room) into the system prompt or the first message of any LLM, then
ask for the piece: "Using the voice guide above, write a blog post about X
from these notes: ...".

## Sources

Built in October 2026 from all 173 posts on zwischenzugs.com (2011-2026),
including essays first published on the Container Solutions blog, and
from the _Follow the Money_ manuscript (O'Reilly, 2026). The book analysis
compared Ian's raw drafts against the edited text, to separate his habits
from house style.

The `personal-assistant` plugin's `voices/writing.md` is a shorter guide
for the same genre, used by its `/write` skill. This guide supersedes it
in detail and corrects it in places: whole-sentence bolding is common in
the 2017-22 blog posts, and "To be clear" and "Not so fast" are not
signature phrases.
