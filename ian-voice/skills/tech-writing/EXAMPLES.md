# Ian Miell's voice: annotated examples

Real passages from Ian's writing, each followed by a short note on what makes
it characteristic. Use these with `VOICE.md` to calibrate rhythm and tone,
not to copy phrasing wholesale. Curly quotes and dashes from the WordPress
source have been normalised to his typed forms (' and " - ").

---

## 1. Essay opening: the consultant's question

From "Who Should Write the Terraform?" (2022):

> Working in Cloud Native consulting, **I'm often asked about who should do
> various bits of 'the platform work'**.
>
> I'm asked this in various forms, and at various levels, but the title's
> question ('Who should write the Terraform?') is a fairly typical one.
> Consultants are often asked simple questions that invite simple answers,
> but it's our job to frustrate our clients, so **I invariably say "it
> depends"**.
>
> The reason it depends is that **the answers to these seemingly simple
> questions are very context-dependent**. Even if there is an 'ideal'
> answer, the world is not ideal, and the best thing for a client at that
> time might not be the best thing for the industry in general.
>
> So here I attempt to lay out the factors that help me answer that
> question as honestly as possible. But before that, we need to lay out
> some background.
>
> **Here's an overview of the flow of the piece:**

What to notice:

- The first sentence is the real-world trigger, given from his own
  position.
- The self-mocking joke about consultants comes in the second paragraph,
  not the first.
- 'it depends' is promised to be unpacked, not left hanging.
- "So here I..." is the scope sentence.
- History is promised before the argument ("we need to lay out some
  background").
- Bold is used on whole key clauses (2018-2022 essay habit).
- There is a roadmap list.

---

## 2. Essay opening: received wisdom, then the twist

From "Reinventing The Wheel, Now At A Bargain Price!" (2026):

> For twenty years, saying "don't reinvent the wheel" was usually enough to
> win any argument about writing bespoke software. But that advice assumed
> two things: writing code was expensive, and importing code was cheap. AI
> and supply-chain governance are changing both assumptions.
>
> ## A Short Personal History of Libraries
>
> When I started in software it felt like the wild west in terms of
> security, audit and compliance. I worked in an unregulated industry as a
> third party supplier to some FTSE-100 businesses as an engineer. I could
> tell stories about access and identity management (or the lack of it)
> that would turn a 2026 CISO's hair white (or, more likely, whiter).
>
> Wind forward a quarter of a century, and now security is not only its
> own discipline, but (mostly) fully baked into the software development
> lifecycle. Compliance is on its way to the party too (this is the area
> I'm working on at the moment, contact me etc.).

What to notice:

- The whole thesis is in three sentences, with no preamble.
- It goes straight into personal history.
- There are stacked parenthetical jokes ("(or, more likely, whiter)").
- "Wind forward..." is one of his transitions.
- The casual plug is tucked into a parenthesis ("contact me etc.").

---

## 3. How-to opening: payoff first, then the story

From "A Docker Image in Less Than 1000 Bytes" (2018):

> Here it is (base64-encoded):
>
> ```
> H4sICIa2A1sCA2IA7Vrrbts2FFYL7M9+7QUGGNyfDYhtkuJFFLAhWZOhBYJmaLMOWBAEFC+x...
> ```
>
> ## How I Got There
>
> A colleague of mine showed me a Docker image he was using to test
> Kubernetes clusters. It did nothing, just starts up as a pod and sits
> there until you kill it.
>
> > 'Look, it's only 700kb! Really quick to download!'
>
> This got me wondering what the smallest Docker image I could create was.
>
> I wanted one I could base64 encode and send 'anywhere' with a cut and
> paste.
>
> Since a Docker image is just a tar file, and a tar file is 'just' a file,
> this should be quite possible.

What to notice:

- Almost every paragraph is a single sentence.
- The trigger is a colleague's remark.
- "This got me wondering" leads into the goal.
- 'just' is in single quotes, which signals the demystifying move.
- Scare quotes go around 'anywhere'.
- "quite possible" is understated.

---

## 4. How-to numbered item

From "Seven God-Like Bash History Shortcuts You Will Actually Use" (2019):

> ### 1) `!$` - The 'Last Argument' One
>
> If you only take one shortcut from this article, make it this one.
>
> **It substitutes in the last argument of the last command into your
> line.**
>
> Consider this scenario:
>
> ```
> $ mv /path/to/wrongfile /some/other/place
> mv: cannot stat '/path/to/wrongfile': No such file or directory
> ```
>
> Ach, I put the `wrongfile` filename in my command. I should have put
> `rightfile` instead.
>
> You might decide to fully re-type the last command, and replace
> `wrongfile` with `rightfile`.
>
> Instead, you can type:
>
> ```
> $ mv /path/to/rightfile !$
> mv /path/to/rightfile /some/other/place
> ```

What to notice:

- The heading uses `N)`, the command in backticks and a nickname in
  single quotes.
- There is a one-line hook, then a bold one-sentence definition.
- The scenario is a real mistake, with real error output.
- "Ach," is a small spoken interjection.
- "Instead, you can type:" ends with a colon before the block.
- The blocks are tiny and use `$` prompts.

---

## 5. Essay conclusion: the coined term and the challenge

From "Business Value, Soccer Canteens, Engineer Retention, and the
Bricklayer Fallacy" (2022):

> At the heart of this problem in software is what I call the 'bricklayer
> fallacy'. Many view software engineering as a series of tasks analogous
> to laying bricks: once you are set up, you can say roughly how long it
> will take to do something, because laying one brick takes a predictable
> amount of time.
>
> [...]
>
> Soccer managers don't suffer as much from this fallacy because we
> intuitively understand that building a great soccer team is not like
> building a brick wall.
>
> [...]
>
> If you remove this judgement from people, you remove their agency.
>
> [...]
>
> If you want to keep the best and most innovative staff - the ones that
> will come up with 10x improvements to your workflows that result in
> significant efficiencies, improvements, and savings - you need to figure
> out who the Alex Fergusons are, and give them the right level autonomy to
> deliver for you. That's your management challenge.

What to notice:

- The concept is named with "what I call" and single quotes.
- The analogy is explained with a colon.
- The essay's main analogy (Ferguson, soccer) is called back at the end.
- A one-sentence paragraph carries the moral.
- The spaced " - " dashes frame an aside.
- The ending is a short challenge to the reader, not a summary.

---

## 6. Book war story (O'Reilly register)

From _Follow the Money_, ch10 (American spelling is the publisher's house
style):

> **War Story: Project to Product Platform**
>
> A B2B software company I worked with on behalf of a consultancy team
> presented its challenges to us as a straightforward set of technical
> problems with its software delivery platform. [...] It was clear to us
> that the client's more intractable challenges building the platform
> would be in managing the expectations of management (who represented the
> patrons of the business) and coordinating the rest of the business [...]
>
> The platform was successfully built, and we moved on from the project.
> Two years later we caught up with them as part of after-sales care, and
> they told us that their biggest problem was that they'd built the
> platform but couldn't get teams to adopt it, for two reasons: sales were
> not "getting behind" the platform, and funding had been cut off. [...]
> Within an hour, two solutions to their challenges were sketched out: a
> model for sales to be incentivized to sell the platform [...] and a
> different accounting model for the platform that treated it as a
> long-lived asset that required ongoing maintenance (like a building)
> rather than a simple asset that would be depreciated over time with no
> further investment (like a laptop).
>
> It is possible that the client was correct in thinking that involving
> non-technical parties too early might have distracted them from their
> immediate technical tasks. In my experience with other clients, however,
> it is rarely a bad idea for a cross-section of people across the
> business to be involved in any analysis of a topic that will eventually
> need their involvement to succeed.

What to notice:

- The client is anonymised.
- The story is told plainly in time order.
- Paragraphs are longer than in the blog (this is the book register).
- Homely analogies (a building, a laptop) sit in parentheses.
- The final paragraph concedes the client's view before stating the
  lesson, with the hedge "In my experience... rarely".

---

## 7. Short note (2026 register)

From "Everything Is An API Now" (2026):

> Tonight I resuscitated it and one-shotted a professional-looking but
> simple site that still gives me the information I wanted (and more - it
> added useful stuff like plot synopses and ratings) in 5 minutes. It works
> perfectly, and I don't even know what tech it used.
>
> Nothing new in that - one-shotting a useful site now feels old hat now
> that we're firing a large chunk of employees because AI.
>
> [...]
>
> I don't need to interact with that annoying cinema site anymore (except
> to buy tickets, though it's tempting to automate that as well...). I can
> just point my harness of choice at it and tell it to give me the
> interface I prefer.
>
> Everything is an API now. Think of that, and what it means for a
> software engineer now!

What to notice:

- The register is casual internet ("one-shotted", "because AI", "harness
  of choice").
- There is a dry aside about layoffs.
- The parenthetical ends with a trailing ellipsis.
- The ending repeats the title as a short thesis, with one exclamation
  mark.

---

## 8. Rewrites: generic draft to Ian

These are illustrations of style. The client scenario in them is made up,
and a real draft must use Ian's real material, never invented anecdotes.

**Generic:**

> Platform engineering has emerged as a transformative discipline that
> empowers organizations to streamline developer workflows. However,
> success requires more than just technology—it demands cultural
> alignment, executive buy-in, and a product mindset.

**Ian:**

> Recently a client asked me why only two of their forty feature teams were
> using the platform they'd spent eighteen months building.
>
> It wasn't the technology. The cluster worked, the pipeline template was
> fine, and the Confluence page was (by enterprise standards) almost
> readable. The problem was that nobody's budget paid for teams to move
> onto it, and the platform team's own funding ran out at the end of the
> financial year. In other words, the platform had no patron.
>
> I've seen this pattern many times, and it's rarely fixed by better
> engineering.

**Generic:**

> In conclusion, there is no one-size-fits-all answer. The right choice
> depends on your organization's unique needs. By carefully weighing these
> factors, you can make an informed decision that drives value.

**Ian:**

> So, should you write it yourself? It depends - but now you know on what.
> If most of the 'consider writing your own' list applies, and the blast
> radius is low, go ahead. If not, take the library, and budget for
> maintaining your relationship with it.
>
> Keen to hear from you if you've tried this and it went horribly wrong.
