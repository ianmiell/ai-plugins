#!/usr/bin/env python3
"""Check a draft of Ian's technical writing against the mechanical rules in VOICE.md.

  python3 voice-check.py draft.md
  python3 voice-check.py - < draft.md
  python3 voice-check.py --register cs draft.md
  python3 voice-check.py --register book chapter.md <<'EOF'
  draft text
  EOF

Prints one line per problem, "line N: "matched text": what's wrong", and exits 0 when the
draft is clean, 1 when something was flagged, 2 on bad usage (unknown option, missing or empty
file). Tone, structure and evidence are the guide's job; this only catches the mechanical
giveaways from VOICE.md sections 3, 11, 12, 17 and 18.

Registers (VOICE.md section 4):
  blog   the default: British spelling, spaced hyphens for dashes, eg/ie without dots, no
         "whilst", "folder" rather than "directory", little bold
  cs     a Container Solutions piece: as blog, but house copy may use "whilst"
  book   Follow the Money prose for O'Reilly: American spelling, so British spellings are
         flagged instead; punctuation (dashes, e.g./i.e.) follows the publisher's house style
         and that repo's AGENTS.md, so it isn't checked here

Code (fenced blocks and `inline`), URLs and link targets are skipped. Block quotes (lines
starting ">") are someone else's words, so they get the typography checks but not spelling or
vocabulary. A capitalised word mid-sentence (outside a heading) is taken as a name ("Jira Data
Center", "the Labor Party") and its spelling left alone. Some avoid-list words are only wrong
as metaphors ("landscape", "unlock", "robust"): the message says so, and the call is yours.
"""

import argparse
import re
import sys

REGISTERS = ("blog", "cs", "book")
APOS = "['\u2019]"

# -ise/-ize verbs (and their -isation nouns) that British English spells with s. Technical
# words usually spelt with z even in British text (containerize, serialize, initialize,
# synchronize, virtualize, tokenize) are left out on purpose.
IZE_STEMS = [
  "organ", "real", "recogn", "priorit", "summar", "optim", "util", "standard", "central",
  "decentral", "custom", "minim", "maxim", "normal", "categor", "emphas", "apolog", "author",
  "character", "critic", "final", "modern", "visual", "special", "memor", "monet", "product",
  "incentiv", "industrial", "capital", "democrat", "legitim", "mobil", "public", "rational",
  "stabil", "sympath", "theor", "harmon", "scrutin", "jeopard", "familiar", "general",
  "hypothes", "operational", "commercial", "conceptual", "contextual", "formal", "digit",
  "local", "global", "personal", "trivial", "anonym", "romantic", "patron", "subsid",
]
IZE_ENDINGS = ["e", "es", "ed", "ing", "er", "ers", "ation", "ations"]

# British form, American form, for the other families.
OUR = ["colour", "favour", "behaviour", "honour", "labour", "neighbour", "humour", "flavour",
       "rumour", "harbour", "endeavour", "saviour", "vapour", "armour", "odour", "rigour",
       "valour", "parlour", "splendour", "candour"]
OUR_ENDINGS = ["", "s", "ed", "ing", "ful", "able", "ite", "ites", "al", "ally", "hood", "less",
               "er", "ers"]
RE_WORDS = [("centre", "center"), ("theatre", "theater"), ("fibre", "fiber"), ("litre", "liter"),
            ("calibre", "caliber"), ("sombre", "somber"), ("spectre", "specter"),
            ("lustre", "luster"), ("meagre", "meager"), ("sabre", "saber"),
            ("manoeuvre", "maneuver")]
PAIRS = [
  ("analyse", "analyze"), ("analysed", "analyzed"), ("analysing", "analyzing"),
  ("analyser", "analyzer"), ("analysers", "analyzers"), ("paralyse", "paralyze"),
  ("paralysed", "paralyzed"), ("catalyse", "catalyze"), ("catalysed", "catalyzed"),
  ("catalogue", "catalog"), ("catalogues", "catalogs"), ("catalogued", "cataloged"),
  ("cataloguing", "cataloging"),
  ("defence", "defense"), ("defences", "defenses"), ("offence", "offense"),
  ("offences", "offenses"), ("pretence", "pretense"),
  ("grey", "gray"), ("greys", "grays"), ("greyed", "grayed"),
  ("sceptic", "skeptic"), ("sceptics", "skeptics"), ("sceptical", "skeptical"),
  ("scepticism", "skepticism"),
  ("artefact", "artifact"), ("artefacts", "artifacts"),
  ("judgement", "judgment"), ("judgements", "judgments"),
  ("acknowledgement", "acknowledgment"), ("acknowledgements", "acknowledgments"),
  ("aluminium", "aluminum"), ("cosy", "cozy"), ("mould", "mold"), ("moulds", "molds"),
  ("mouldy", "moldy"), ("plough", "plow"),
  ("travelling", "traveling"), ("travelled", "traveled"), ("traveller", "traveler"),
  ("travellers", "travelers"), ("cancelled", "canceled"), ("cancelling", "canceling"),
  ("modelling", "modeling"), ("modelled", "modeled"), ("modeller", "modeler"),
  ("labelled", "labeled"), ("labelling", "labeling"), ("levelled", "leveled"),
  ("levelling", "leveling"), ("signalled", "signaled"), ("signalling", "signaling"),
  ("fuelled", "fueled"), ("fuelling", "fueling"), ("marvellous", "marvelous"),
  ("counsellor", "counselor"), ("counsellors", "counselors"),
  ("fulfil", "fulfill"), ("fulfils", "fulfills"), ("fulfilment", "fulfillment"),
  ("skilful", "skillful"), ("wilful", "willful"), ("enrol", "enroll"), ("enrols", "enrolls"),
  ("enrolment", "enrollment"), ("instalment", "installment"), ("instalments", "installments"),
  # Ian's own double s (VOICE.md rule 6).
  ("focussed", "focused"), ("focussing", "focusing"),
]
# Only one way round: the other form is right in both, or can't be told apart from a word.
US_ONLY = {"analyzes": "analyses", "paralyzes": "paralyses",
           "license": "licence (the noun; license is the verb)",
           "licenses": "licences (the noun; licenses is the verb)"}
UK_ONLY = {"licence": "license", "licences": "licenses", "programme": "program",
           "programmes": "programs", "practise": "practice", "practised": "practiced",
           "practising": "practicing", "practises": "practices"}


def spelling_pairs():
  pairs = list(PAIRS)
  for stem in IZE_STEMS:
    pairs += [(stem + "is" + e, stem + "iz" + e) for e in IZE_ENDINGS]
  for brit in OUR:
    pairs += [(brit + e, brit[:-2] + "r" + e) for e in OUR_ENDINGS]
  for brit, us in RE_WORDS:
    pairs += [(brit, us), (brit + "s", us + "s"), (brit[:-1] + "ed", us + "ed"),
              (brit[:-1] + "ing", us + "ing")]
  return pairs


def spelling_table(register):
  """{wrong form: right form} for the register: American forms for blog and cs, British ones
  for the book."""
  pairs = spelling_pairs()
  if register == "book":
    table = {b: u for b, u in pairs}
    table.update(UK_ONLY)
  else:
    table = {u: b for b, u in pairs}
    table.update(US_ONLY)
  return table


# Avoid-list words and phrases (VOICE.md sections 6, 12, 17 and 18): (pattern, message).
# Matched case-insensitively over prose, with any run of spaces or a line break between words.
AVOID = [
  (r"\bdelv(e|es|ed|ing)\b", "on the avoid list"),
  (r"\blandscapes?\b", "on the avoid list as a metaphor"),
  (r"\bleverag(ing|ed|es)\b|\b(to|can|could|will|would|should|must|we|you|they|I|let's)\s+leverage\b",
   "'leverage' as a verb is on the avoid list: say 'use'"),
  (r"\butili[sz](e|es|ed|ing|ation)\b", "on the avoid list: say 'use'"),
  (r"\bgame[- ]chang(er|ers|ing)\b", "on the avoid list"),
  (r"\bunlock(s|ed|ing)?\b", "on the avoid list as a metaphor"),
  (r"\bseamless(ly)?\b", "on the avoid list"),
  (r"\brobust(ly|ness)?\b", "on the avoid list as praise"),
  (r"\bcutting[- ]edge\b", "on the avoid list"),
  (r"\bsynerg(y|ies|istic)\b", "on the avoid list"),
  (r"\bholistic(ally)?\b", "on the avoid list"),
  (r"\bempower(s|ed|ing|ment)?\b", "on the avoid list"),
  (r"(?<!['\u2018])\bjourneys?\b(?!['\u2019])", "on the avoid list unless ironic, in single quotes ('journey')"),
  (r"\b(furthermore|moreover|additionally)\b", "on the avoid list"),
  (r"\bin\s+conclusion\b", "on the avoid list: end on a reframe, device or kicker"),
  (r"(?m)(?:^[ \t>*+-]*|(?<=[.!?:]\s))(?:more\s+|most\s+)?importantly\b", "on the avoid list"),
  (rf"\bit{APOS}?s\s+worth\s+noting\b|\bit\s+is\s+worth\s+noting\b", "on the avoid list"),
  (rf"\bit{APOS}?s\s+important\s+to\s+note\b|\bit\s+is\s+important\s+to\s+note\b", "on the avoid list"),
  (rf"\blet{APOS}?s\s+dive\b|\bdive\s+right\s+in\b", "on the avoid list"),
  (rf"\bhere{APOS}s\s+the\s+thing\b", "on the avoid list"),
  (r"\blet\s+that\s+sink\s+in\b", "on the avoid list"),
  (rf"\bin\s+today{APOS}?s\s+fast[- ]paced\b|\bfast[- ]paced\s+world\b", "on the avoid list"),
  (r"\bever[- ]evolving\b", "on the avoid list"),
  (r"\bgreat\s+question\b", "on the avoid list"),
  (r"\bi\s+hope\s+this\s+helps\b", "on the avoid list"),
  (r"\bi\s+hope\s+you\s+found\s+this\s+useful\b", "not his: end on a reframe, device or kicker"),
  (r"\bhappy\s+coding\b", "on the avoid list"),
  (r"\bfor\s+instance\b", "he says 'for example'"),
  (r"\bsmash\s+that\s+like\b|\bsubscribe\s+to\s+(my|the|our)\s+newsletter\b",
   "no calls to subscribe or like (VOICE.md section 17)"),
  (rf"\b(it|this|that)(?:{APOS}s|\s+is|\s+was)(?:\s+not|n{APOS}t)\s+[^.!?]{{1,80}}[.!?]\s+(it|this|that)(?:{APOS}s|\s+is|\s+was)\b",
   "the dramatic 'It's not X. It's Y.' reveal (VOICE.md section 18)"),
]
WHILST = (r"\bwhilst\b", "he writes 'while' ('whilst' is only for Container Solutions house copy)")
# Lower case only, so "Active Directory" is left alone.
DIRECTORY = (r"\bdirector(y|ies)\b", "he says 'folder' in prose (VOICE.md section 9)")

EMOJI = re.compile("[\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF\U00002600-\U000027BF]")
URL = re.compile(r"https?://[^\s)\]>\"']+")
LINK_TARGET = re.compile(r"(?<=\])\([^)\s]*\)")
INLINE_CODE = re.compile(r"(`+)[^`\n]*?\1")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def blank(m):
  return " " * len(m.group(0))


def prose_of(text):
  """The draft with code, URLs and link targets blanked out, keeping every offset and line."""
  out, fence = [], None
  for line in text.split("\n"):
    m = FENCE.match(line)
    if fence:
      out.append(" " * len(line))
      if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
        fence = None
      continue
    if m:
      fence = m.group(1)
      out.append(" " * len(line))
      continue
    line = INLINE_CODE.sub(blank, line)
    line = URL.sub(blank, line)
    line = LINK_TARGET.sub(blank, line)
    out.append(line)
  return "\n".join(out)


class Checker:

  def __init__(self, text, register="blog"):
    self.text = text
    self.register = register
    self.prose = prose_of(text)
    self.lines = self.prose.split("\n")
    self.starts = [0]
    for line in self.lines:
      self.starts.append(self.starts[-1] + len(line) + 1)
    self.quoted = {i + 1 for i, l in enumerate(self.lines) if l.lstrip().startswith(">")}
    self.headings = {i + 1 for i, l in enumerate(self.lines) if re.match(r"\s*#{1,6}\s", l)}
    self.problems = []

  def line_of(self, offset):
    lo, hi = 0, len(self.lines)
    while lo < hi:
      mid = (lo + hi + 1) // 2
      if self.starts[mid] <= offset:
        lo = mid
      else:
        hi = mid - 1
    return lo + 1

  def flag(self, offset, matched, message):
    self.problems.append((self.line_of(offset), " ".join(matched.split()), message))

  def scan(self, pattern, message, flags=re.I, words=True):
    """Flag every match of pattern. words=True skips block quotes (someone else's words)."""
    for m in re.finditer(pattern, self.prose, flags):
      if words and self.line_of(m.start()) in self.quoted:
        continue
      self.flag(m.start(), m.group(0).strip(), message)

  def typography(self):
    if self.register != "book":
      self.scan("\u2014", "em dash: use a spaced hyphen ' - '", words=False)
      self.scan(r"\s\u2013\s", "spaced en dash: type a spaced hyphen ' - '", words=False)
      self.scan(r"(?<=\S)\u2013(?=\S)", "en dash: type a hyphen ('2011-2026')", words=False)
      self.scan(r"(?<=\S) -- (?=\S)", "double hyphen as a dash: use a spaced hyphen ' - '", words=False)
      self.scan(r"(?<![\w.])e\.\s?g\b\.?", "write 'eg', without full stops", words=False)
      self.scan(r"(?<![\w.])i\.\s?e\b\.?", "write 'ie', without full stops", words=False)
      self.scan(r"(?<![\w.])(eg|ie)\.(?=\s+[a-z])", "write 'eg'/'ie' without a full stop", flags=0,
                words=False)
      self.scan(r"(?<![\w.])(eg|ie),", "no comma after 'eg'/'ie'", flags=0, words=False)
    if "!!" in self.prose:
      self.scan(r"!{2,}", "use a single exclamation mark", words=False)
    for m in EMOJI.finditer(self.prose):
      self.flag(m.start(), m.group(0), "emoji: he essentially never uses them")
    for m in re.finditer(r"(?<![\w&/#\]])#[A-Za-z][\w-]*", self.prose):
      if self.line_of(m.start()) not in self.headings:
        self.flag(m.start(), m.group(0), "hashtag: he never uses them")
    if self.register != "book":
      self.scan(r"(\*\*|__)[A-Za-z][\w'-]*\1", "bold on a single word: bold a whole key sentence or none",
                flags=0, words=False)
    for m in re.finditer(r"(?m)^#\s+\d{1,3}\s+[A-Za-z]+", self.prose):
      self.flag(m.start(), m.group(0), "numbers in titles are spelled out ('Five Ways', not '5 Ways')")

  def spelling(self):
    table = spelling_table(self.register)
    kind = "British" if self.register == "book" else "American"
    for m in re.finditer(r"[A-Za-z]+", self.prose):
      word = m.group(0)
      right = table.get(word.lower())
      if not right:
        continue
      n = self.line_of(m.start())
      if n in self.quoted:
        continue
      if word[0].isupper() and n not in self.headings:
        before = self.prose[self.starts[n - 1]:m.start()]
        at_start = re.fullmatch(r"[\s>*+-]*(\d+[.)])?[\s*_\"'(\u2018\u201c]*", before)
        if not at_start and before.rstrip(" *_\"'(\u2018\u201c")[-1:] not in tuple(".!?:"):
          continue  # a name, mid-sentence
      note = " (Follow the Money uses O'Reilly's American house style)" if self.register == "book" else ""
      self.flag(m.start(), word, f"{kind} spelling{note}: use '{right}'")

  def vocabulary(self):
    pats = list(AVOID)
    if self.register != "cs":
      pats.append(WHILST)
    if self.register != "book":
      pats.append(DIRECTORY)
    for pat, message in pats:
      self.scan(pat, message, flags=0 if pat == DIRECTORY[0] else re.I)
    paras = [p for p in re.split(r"\n\s*\n", self.prose) if p.strip() and not p.lstrip().startswith("#")]
    if paras:
      first, last = paras[0], paras[-1]
      m = re.search(r"\bhave\s+you\s+ever\s+wondered\b", first, re.I)
      if m:
        self.flag(self.prose.index(first) + m.start(), m.group(0),
                  "generic hook: open with something that happened")
      m = re.match(r"\s*(ultimately)\b", last, re.I)
      if m:
        self.flag(self.prose.rindex(last) + m.start(1), m.group(1),
                  "'Ultimately' as a sign-off: end on a reframe, device or kicker")

  def counts(self):
    words = len(re.findall(r"\b\w+\b", self.prose))
    bangs = [m.start() for m in re.finditer(r"!(?!\[)", self.prose)]
    if len(bangs) > 1 + words // 500:
      self.flag(bangs[0], "!", f"{len(bangs)} exclamation marks in {words} words: he uses about one per 1,000")
    if self.register != "book":
      semis = [m.start() for m in re.finditer(r";(?!\w)", self.prose)]
      if len(semis) > 2 + words // 1000:
        self.flag(semis[0], ";", f"{len(semis)} semicolons in {words} words: he rarely uses them")

  def run(self):
    self.typography()
    self.spelling()
    self.vocabulary()
    self.counts()
    seen, out = set(), []
    for p in sorted(self.problems, key=lambda p: p[0]):
      if p not in seen:
        seen.add(p)
        out.append(p)
    return out


def check(text, register="blog"):
  """[(line, matched text, message)] for a draft."""
  return Checker(text, register).run()


def main():
  ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  ap.add_argument("--register", choices=REGISTERS, default="blog")
  ap.add_argument("file", nargs="?", default="-", help="the draft (default, or '-': stdin)")
  args = ap.parse_args()
  try:
    if args.file == "-":
      text = sys.stdin.read()
    else:
      with open(args.file, encoding="utf-8") as f:
        text = f.read()
  except OSError as e:
    print(f"can't read {args.file}: {e.strerror}", file=sys.stderr)
    return 2
  if not text.strip():
    print("empty draft", file=sys.stderr)
    return 2
  problems = check(text, args.register)
  for line, matched, message in problems:
    print(f'line {line}: "{matched}": {message}')
  return 1 if problems else 0


if __name__ == "__main__":
  sys.exit(main())
