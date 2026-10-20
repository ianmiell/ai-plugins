#!/usr/bin/env python3
"""Check a draft against the mechanical rules in voices/*.md.

Reads the draft on stdin (or from a file argument) and prints one line per
problem. Exits 0 when clean, 1 when something was flagged, 2 on bad usage.
Tone is the guides' job; this only catches the mechanical giveaways.

  python3 voice-check.py --channel slack <<'EOF'
  draft text
  EOF
"""

import argparse
import re
import sys

CHANNELS = ("email", "slack", "whatsapp", "linkedin", "writing", "review", "notes")

# Rough word ceilings: past these a draft is unusually long for Ian.
MAX_WORDS = {
  "email": 180,
  "slack": 60,
  "whatsapp": 40,
  "linkedin": 250,
  "writing": None,
  "review": 80,
  "notes": 120,
}

# Channels where Ian doesn't use emoji at all.
NO_EMOJI = {"email", "review", "notes"}

NEVER = [
  "hope this email finds you well",
  "hope this finds you well",
  "hope you are well",
  "please do not hesitate",
  "don't hesitate to",
  "at your earliest convenience",
  "per my last email",
  "circle back",
  "touch base",
  "reach out",
  "reaching out",
  "synergy",
  "synergies",
  "great question",
  "happy to help!",
  "best regards",
  "warm regards",
  "many thanks",
  "best wishes",
  "just checking in",
  "quick question",
  "i wanted to follow up",
  "going forward",
  "deep dive",
  "thrilled to share",
  "humbled to announce",
  "let's connect",
]

# American spelling -> British. Whole words only.
AMERICAN = {
  "organization": "organisation",
  "organizations": "organisations",
  "organize": "organise",
  "organized": "organised",
  "prioritize": "prioritise",
  "prioritized": "prioritised",
  "realize": "realise",
  "realized": "realised",
  "recognize": "recognise",
  "apologize": "apologise",
  "summarize": "summarise",
  "optimize": "optimise",
  "favor": "favour",
  "favorite": "favourite",
  "color": "colour",
  "behavior": "behaviour",
  "honor": "honour",
  "labor": "labour",
  "center": "centre",
  "license": "licence (noun) / license (verb)",
  "catalog": "catalogue",
  "analyze": "analyse",
  "analyzed": "analyse(d)",
  "defense": "defence",
  "traveling": "travelling",
  "canceled": "cancelled",
  "modeling": "modelling",
}

EMOJI = re.compile(
  "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]"
  "|:[a-z0-9_+-]+:"
)
GREETING = re.compile(r"^\s*(hi|hey|hello|dear|good (morning|afternoon))\b", re.I)
FORMAL_GREETING = re.compile(r"^\s*(hi|hello|dear|good (morning|afternoon|evening))\b", re.I)
SIGNOFF = re.compile(r"(^|\n)\s*(thanks,?|cheers,?|kind regards,?)?\s*\n?\s*ian\.?\s*$", re.I)


def check(text, channel):
  problems = []
  lower = text.lower()
  # Code blocks and inline code can hold anything.
  prose = re.sub(r"```.*?```", "", text, flags=re.S)
  prose = re.sub(r"`[^`]*`", "", prose)

  if "—" in prose:
    problems.append("em dash (—): use a spaced hyphen ' - '")
  if re.search(r"\s–\s", prose):
    problems.append("en dash (–) used as a dash: use a spaced hyphen ' - '")

  for phrase in NEVER:
    if phrase in lower:
      problems.append(f"never-list phrase: '{phrase}'")

  for word, brit in AMERICAN.items():
    if re.search(rf"\b{word}\b", prose, re.I):
      problems.append(f"American spelling '{word}': use '{brit}'")

  if channel != "writing":
    bangs = len(re.findall(r"!", prose))
    if bangs > 1:
      problems.append(f"{bangs} exclamation marks: use at most one")
  if "!!" in prose:
    problems.append("'!!': use a single exclamation mark")

  emoji = EMOJI.findall(prose)
  if channel in NO_EMOJI and emoji:
    problems.append(f"emoji in {channel}: Ian doesn't use them here")
  elif len(emoji) > 1 and channel in ("slack", "whatsapp", "linkedin"):
    problems.append(f"{len(emoji)} emoji: use at most one")

  if channel == "slack":
    first = prose.strip().splitlines()[0] if prose.strip() else ""
    if GREETING.match(first) and "can you" not in lower and "could you" not in lower:
      problems.append("greeting on a Slack reply: drop it (only a fresh DM request opens with 'Hey [name],')")
    if SIGNOFF.search(prose.strip()):
      problems.append("signed 'Ian' on Slack: drop the sign-off")

  if channel == "whatsapp":
    first = prose.strip().splitlines()[0] if prose.strip() else ""
    if FORMAL_GREETING.match(first):
      problems.append("formal greeting on WhatsApp: drop it (at most 'hey [name]' to restart a quiet chat)")
    if SIGNOFF.search(prose.strip()):
      problems.append("signed 'Ian' on WhatsApp: drop the sign-off")

  limit = MAX_WORDS[channel]
  words = len(re.findall(r"\b\w+\b", prose))
  if limit and words > limit:
    problems.append(f"{words} words: long for {channel} (norm is under {limit}), cut it down")

  return problems


def main():
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument("--channel", required=True, choices=CHANNELS)
  parser.add_argument("file", nargs="?", help="draft file (default: stdin)")
  args = parser.parse_args()
  text = open(args.file).read() if args.file else sys.stdin.read()
  if not text.strip():
    print("empty draft", file=sys.stderr)
    return 2
  problems = check(text, args.channel)
  for p in problems:
    print(p)
  return 1 if problems else 0


if __name__ == "__main__":
  sys.exit(main())
