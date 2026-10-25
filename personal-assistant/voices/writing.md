# Ian's long-form writing voice

How Ian writes blog posts, articles and talk write-ups. It is based on 21 posts on zwischenzugs.com from 2017 to 2026: bash/git/Docker how-tos ("Ten Things I Wish I'd Known About bash", "Five Ways to Undo a Commit in Git", "Practical Shell Patterns I Actually Use", "A Docker Image in Less Than 1000 Bytes"), essays on organisations and cloud ("Why Are Enterprises So Slow?", "Who Should Write the Terraform?", "OK Cloud, On-Prem is Alright", "The Biggest Cloud Native Strategy Mistake", "Business Value, Soccer Canteens, Engineer Retention, and the Bricklayer Fallacy"), AI posts ("Reinventing The Wheel, Now At A Bargain Price!", "What I Learned Using Private LLMs to Write an Undergraduate History Essay"), and book and career posts. Several of these were first published on the Container Solutions blog. Use this guide alongside the shared voice file. It only covers what is specific to long-form writing.

**The full guide.** The `ian-voice` plugin (in the same marketplace) has a much more detailed version of this voice in its `tech-writing` skill: `VOICE.md` and `EXAMPLES.md`. It was built in October 2026 from all 173 zwischenzugs.com posts and the _Follow the Money_ manuscript. If that plugin is installed, read both files as well as this one, and where they differ the full guide wins. It adds detail on registers (blog, Container Solutions, O'Reilly book), the recipe for a numbered how-to item, code conventions, his beliefs and coined terms, and a final self-check. The corrections below come from it.

## Titles

- Title Case, usually 4-10 words. Numbers are spelled out: "Five Things...", "Ten More Things...", "Seven Surprising Bash Variables". He does not write "5 Ways".
- He reuses a small set of templates: "Things I Wish I'd Known About X", "X the Hard Way", "X - the Good Parts" / "The Good Stuff", "...I Actually Use", "...You Might Want to Know About", "What I Learned...", "Why I Keep Coming Back to X".
- Questions that he goes on to answer, often in a hedged way: "Why Are Enterprises So Slow?", "Is it Imperative to be Declarative?", "Does Crossplane Replace Terraform?". Sometimes the title is a quoted question that clients ask him.
- Puns and borrowed phrases: "OK Cloud, On-Prem is Alright", "Goodbye Docker: Purging is Such Sweet Sorrow", "Riding the Tiger".
- Ironic how-to titles for satire: "How To Waste Hundreds of Millions on Your IT Transformation".
- Lists of things that don't seem to belong together, which make the reader curious: "Apple's HQ, Ruskin, Gothic Architecture, and Agile".
- Series are labelled with Roman numerals: "Part I: the Theory". An exclamation mark appears only now and then, for announcements or self-mockery.

## Openings

- He gets to the point within two or three sentences. Common openings:
  - A small trigger from real life: a colleague's remark, a client question, a tweet. Two examples are "A colleague of mine showed me a Docker image..." and "...I was asked 'how many ways are there to undo a bad change in Git?'".
  - Stated experience used as authority: "As someone who has worked in software since 2001...".
  - Received wisdom followed by the twist: "For twenty years, saying 'don't reinvent the wheel' was usually enough to win any argument". The next sentence names the assumption that no longer holds.
  - A self-deprecating aside: "Unfortunately, I've forgotten about 95% of them."
  - The payload first, then the story: "Here it is (base64-encoded):".
  - Occasionally a second-person scenario for satire: "You're a few years into your tenure as CEO of..."
- Next comes a short scope paragraph that starts "So here I..." or "In this article I want to...". It often says what the post is not: "This is not a vim vs not-vim post."
- In long posts this is followed by a bulleted map of the sections ("I'm going to cover:"). He also offers a way out: "If you're not interested in my life story... skip to the end".

## Structure

- H2 headings throughout. They are short and plain, sometimes a joke ("'Schemas Are Bad, M'Kay?'").
- Numbered sections in the form "1) Manual Reversion" / "2) git revert". Listicles are numbered all the way through. Essays often use "Factor One:...".
- A typical essay arc: Problem/Context, then "How We Got Here" (history), then the argument, then Objections or Caveats, then "What To Do?", then a return to the title question ("So, Who Should Write the Terraform?").
- Long posts get a "TL;DR" or "tl;dr" heading at the top. He does not use "Summary" boxes. Essays may end with "What I Learned", "Conclusion" (about 8 essays) or a restated title question. How-tos almost never have a conclusion: listicles stop after the last item, or end with "What You Learned" and "Exercises".
- A numbered how-to item follows a recipe: a one-line hook about his relationship to it ("This one confused me for a long time."), a scenario the reader recognises ("Ever typed anything like this?"), a tiny `$` block with real output, the better way ("Instead, you can type:"), a gloss of each token or flag, a gotcha, and a frequency claim ("I use this dozens of times a day.").
- Long quotations from books, talks or tweets are set off as blocks with an attribution line underneath (eg "Team Topologies, Matthew Skelton and Manuel Pais"). He also embeds his own old tweets as evidence.
- A post that proposes something ends with a practical device: a checklist, a scoring list, a "points for / consider writing your own when" pair, or a set of named patterns.
- Lengths range from 600-word how-tos to 4,700-word essays. He splits a subject into a series rather than trimming it.

## Paragraphs and sentences

- Paragraphs are short, mostly 1-4 sentences, and on the blog about half are a single sentence. A one-line paragraph lands a point: "Absolutely.", "Yup.", "Let's move on.", "But hey.", "Not one bit."
- Sentences are of medium length (a median of about 14 words in how-tos and 16-20 in essays) and conversational. He allows himself the occasional long sentence with commas and parentheses when telling a story.
- Parentheses are constant, at about 7-8 per 1,000 words, for asides, glosses and jokes. Semicolons are rare.
- He writes "I" on his own blog, and "you" even more. On anything written for Container Solutions he writes "we" ("we've observed", "our clients"), and the tone there is more formal: longer paragraphs, fewer jokes, no bold. For O'Reilly book text, follow the publisher's house style (American spelling) and the book repo's AGENTS.md. Pick the voice that fits where the piece will appear.
- He addresses the reader directly: "dear reader", "If you want to follow along...", "Before we start, let's imagine...".
- Hedging is honest rather than defensive: "I'm going to grossly simplify matters here, but..."; "Whether it worked or not I don't know - you'd have to ask the team".

## Argument and evidence

- **History first.** "To explain how I would answer that, I'm going to have to do a little history." Typical examples: coders and sysadmins becoming Dev, Ops, DevOps and SRE, mainframe to PC as a model for cloud, three-tier apps in 2001.
- **Personal war stories as evidence.** These are specific and slightly embarrassing: a CTO's one-word email reply "vim", the wiki curator who was laid off, a startup where he was employee #39, the DBA who wouldn't use Git.
- **Analogies from outside tech, worked through in detail:** Alex Ferguson redesigning a canteen, a ship's surgeon against an otologist, a nuclear submarine, a Faustian pact. He keeps returning to the analogy and calls back to it in the ending.
- **"It depends", then the factors.** He states openly that he refuses a simple answer ("it's our job to frustrate our clients"), then lists the factors that decide it.
- **Contrarian but fair.** He takes on conventional wisdom ("I want to challenge these ideas. In fact, I want to turn them on their head"). He also steelmans the other side: "The CISO objection is not stupid." Objections get their own headings, and he concedes the ones that hold.
- **He names the concepts he coins** and puts them in quotes: 'bricklayer fallacy', 'wiki-entropy', 'organisational indigestion', 'low-tech devex'. He is happy to admit when he has just made one up.
- **Concrete numbers** rather than adjectives: a £650 workstation against £11,000 a year on AWS, ticket counts cut by 75%, Netflix taking seven years to migrate.
- **Frameworks he keeps coming back to:** Cynefin, Team Topologies, Sapiens' 'collective fictions', money flows, Cloud Native patterns.
- **Links on the words themselves** ("[here]", "[previous content]") rather than footnotes. Many links go to his own earlier posts, his books and his repos.

## Code and examples

- He gives a setup block the reader can paste so they can follow along: `cd $(mktemp -d)`, `git init`, then a loop to create commits.
- Commands carry a `$ ` prompt. After each block he explains what it does, what each flag means and why it is there. Real output is shown, often trimmed with `[...]`.
- He uses many tiny blocks (typically 2-4 lines) separated by a sentence of prose, not one long listing. Every lead-in sentence ends with a colon ("Type this:", "which outputs:").
- He says "folder" rather than "directory".
- He is candid about craft: "there are better/faster/more elegant ways... but that's not the point". He mentions the alternatives he tried that "didn't stick".
- Examples are real and personal: his own Makefile, crontab, scrapers, essay files and GitHub repos. He links the repo ("Code is here"). Placeholders are in CAPS (`YOUR_NAME`).
- Pseudocode or scenarios go in code blocks too, eg a central question set off in a block, or a mock email.

## Humour

- A dry tag after a sentence that sounds serious: "No conclusions can be drawn from this." / "Not one bit."
- Pop-culture asides used in passing: Star Wars ("millions of voices suddenly cry out"), Seinfeld's Vandelay Industries, South Park.
- Mock interrogations in which an agile ritual is applied to someone wise, eg a scrum master asking Ferguson how many story points his canteen visits are worth.
- Sustained satire written as straight advice, followed by a deadpan "Disclaimer" at the end.
- Self-mockery about his age and his tools: "seeing your dad dancing at a wedding", "Whenever I learn a new technology an old one falls out of my brain."
- Kicker endings that undercut his own argument: "Of course... my approach is always best".

## Endings

- He returns to the title question and answers it, usually as "it depends, and now you know on what".
- The last lines are a practical takeaway or a challenge to the reader ("That's your management challenge."), or a wry personal kicker that calls back to the post's main analogy.
- Then an invitation: "Keen to hear from you if you can...", "get in touch", "Your thoughts, questions, and experiences are always welcome".
- Then links to related posts and the standard footer: "If you like this, you might like one of my books" (Learn Bash/Git/Terraform the Hard Way), and sometimes "buy me a coffee". Reposts end with "originally published on Container Solutions' blog".
- He does not open the last paragraph with "In conclusion", and he does not end by restating every section.

## Phrases he uses

"Recently I...", "This got me thinking", "I'm often asked...", "Here I...", "Here's...", "it depends", "In other words," (his commonest restatement), "Of course,", "By contrast,", "Again,", "In theory... In practice...", "The reality is...", "As an aside,", "Fortunately/Unfortunately,", "Wind forward...", "Let's move on.", "I won't go there", "your mileage may vary", "get them under your fingers", "I'm looking at you, node", "natch", "'nuff said", "the hard way", "Keen to hear from you", "I just made that word up". He spells it "focussed". He says "for example", never "for instance". "To be clear" and "Not so fast" are not his phrases: each appears only once in fifteen years.

## Never

- Em dashes. The WordPress source renders spaced en dashes, but drafts use the shared " - ".
- "In today's fast-paced world", "Let's dive in", "game-changer", "unlock", "delve", or hype about a vendor's product.
- Bold scattered over single words, emoji in prose, or headings phrased as marketing slogans. (Bolding a *whole* key sentence or takeaway is his habit on the blog, especially 2017-2022; it is not used in Container Solutions or book text.)
- Abstract claims without a story, a number or a link to support them.
- Invented anecdotes, statistics, quotes or client names. Use a `TODO:` placeholder for a war story or figure the source doesn't give.
- Opinions he hasn't expressed. Stay consistent with his known views: money flows shape organisations and so software; culture is real but downstream and must be made specific; there is no universal best practice; cloud is economics, not destiny; simple, old, text-based tools often win; AI is useful but unhyped.
- Pretending there is one right answer, or giving advice he hasn't followed himself.
- American spellings, apart from technical terms such as "color" in code.
- "Whilst". It does appear in Container Solutions house pieces, but his own voice uses "while".

## Example

**Why Your Platform Team Is a Product Team**

Outline:
- TL;DR
- Context: "Can we just give the platform team a backlog?"
- How We Got Here: sysadmins, Ops, DevOps, platform teams
- The Mistake: treating the platform as an install, not a product
- 1) Your Users Can Leave (Shadow IT Is Your Churn Metric)
- 2) Somebody Has to Say No
- 3) Docs and Onboarding Are the Product
- Objections: "We're not a software company", "It's just infra"
- What To Do?: a short checklist
- So, Is Your Platform Team a Product Team?

Opening:

> Recently a client asked me who should own the roadmap for their new internal platform. The platform team had been running for eighteen months, had a Kubernetes cluster, a pipeline template and a Confluence page, and was baffled that only two of the forty feature teams were using any of it.
>
> I said 'it depends', as consultants are contractually obliged to. But in this case it didn't depend very much. They had built a platform the way you install a printer: plug it in, send round an email, and wait for people to be grateful. What they hadn't done was treat it as a product, with users who can (and do) walk away. Here I want to explain why that distinction matters, and what you can do about it.
