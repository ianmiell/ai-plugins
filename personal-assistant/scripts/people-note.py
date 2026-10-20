#!/usr/bin/env python3
"""Find a person's gtd people file, and add a log line to it in the right place.

  people-note.py find "Jane Doe" [--email jane@acme.com]
  people-note.py log Jane_Doe --kind "email, work" --task 4652 "Asked for a proposal by Fri."
  people-note.py log Jane_Doe --kind meeting --ref meetings/20261016_1508_X.txt "Agreed a pilot."

`find` tries, in order: the exact file (First_Last.md) and its _2, _3 duplicates; files that
contain the email address; and files whose name has every part of the name (accents folded,
so "Önsel" finds Onsel_...). It prints one line per candidate: file, why, and the person's
Company and Level lines.

`log` writes `- YYYY-MM-DD (<kind>): <text> [task N]` at the end of the file's
`### Email log` section (`### Meeting log` when kind is `meeting`), adding the section once
if it isn't there. A new section goes before `## LinkedIn messages` (which `gtd
import-messages` keeps at the end of the file), and never inside the
`## managed by linkedin_tools` ... `### managed by linkedin_tools` block. A line that is
already there isn't added again. It doesn't commit: run `bin/gtd push` once afterwards.
"""

import argparse
import datetime
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

PEOPLE = os.path.join(pa.GTD, "people")
MANAGED_START = "## managed by linkedin_tools"
MANAGED_END = "### managed by linkedin_tools"
MESSAGES_HEADING = "## LinkedIn messages"
LOG_LINE_RE = re.compile(r"^- \d{4}-\d{2}-\d{2} \((email|slack|whatsapp|linkedin|meeting)[^)]*\):")


def fold(text):
  text = unicodedata.normalize("NFKD", text)
  return "".join(c for c in text if not unicodedata.combining(c)).lower()


def person_files():
  try:
    return sorted(f for f in os.listdir(PEOPLE) if f.endswith(".md"))
  except OSError:
    pa.die(f"no people folder at {PEOPLE} (set GTD_DIR)")


def summary(fname):
  info = []
  try:
    with open(os.path.join(PEOPLE, fname), encoding="utf-8", errors="replace") as f:
      for line in f:
        m = re.match(r"^- (Company|Level|Email): *(.*)", line)
        if m and m.group(2).strip():
          info.append(f"{m.group(1)}: {m.group(2).strip()}")
  except OSError:
    pass
  return "; ".join(dict.fromkeys(info))


def find(name, email):
  files = person_files()
  found = {}
  slug = re.sub(r"\s+", "_", name.strip())
  exact = re.compile(re.escape(fold(slug)) + r"(_\d+)?\.md$")
  for f in files:
    if exact.fullmatch(fold(f)):
      found.setdefault(f, "name" if f.lower() == f"{slug.lower()}.md" else "name (numbered duplicate)")
  if email:
    needle = email.lower()
    for f in files:
      try:
        with open(os.path.join(PEOPLE, f), encoding="utf-8", errors="replace") as fh:
          if needle in fh.read().lower():
            found.setdefault(f, f"contains {email}")
      except OSError:
        continue
  parts = [fold(p) for p in re.split(r"[\s_.-]+", name) if len(p) > 1]
  if len(parts) >= 2:
    for f in files:
      tokens = fold(f[:-3]).split("_")
      if all(p in tokens for p in parts):
        found.setdefault(f, "all name parts")
    # A surname change keeps the first name; a shortened surname keeps the initial (Aachal_R).
    first, last = parts[0], parts[-1]
    for f in files:
      tokens = fold(f[:-3]).split("_")
      if tokens and tokens[0] == first and len(tokens) >= 2 and tokens[1] == last[0]:
        found.setdefault(f, "first name + surname initial")
  return [(f, why, summary(f)) for f, why in found.items()]


def managed_ranges(lines):
  ranges, start = [], None
  for i, ln in enumerate(lines):
    s = ln.rstrip("\n")
    if s == MANAGED_START and start is None:
      start = i
    elif s == MANAGED_END and start is not None:
      ranges.append((start, i))
      start = None
  if start is not None:
    ranges.append((start, len(lines)))
  return ranges


def inside(i, ranges):
  return any(a <= i <= b for a, b in ranges)


def add_line(lines, heading, entry):
  """Return lines with entry added under heading, by the rules in the docstring."""
  if any(ln.rstrip("\n") == entry for ln in lines):
    return lines, False
  ranges = managed_ranges(lines)
  head = next((i for i, ln in enumerate(lines) if ln.rstrip("\n") == heading and not inside(i, ranges)), None)
  if head is not None:
    end = next((j for j in range(head + 1, len(lines)) if lines[j].startswith("#")), len(lines))
    while end > head + 1 and not lines[end - 1].strip():
      end -= 1
    if end > 0 and not lines[end - 1].endswith("\n"):
      lines[end - 1] += "\n"
    return lines[:end] + [entry + "\n"] + lines[end:], True
  at = next((i for i, ln in enumerate(lines) if ln.rstrip("\n") == MESSAGES_HEADING and not inside(i, ranges)), None)
  block = [heading + "\n", entry + "\n"]
  if at is None:
    while lines and not lines[-1].strip():
      lines = lines[:-1]
    if lines and not lines[-1].endswith("\n"):
      lines[-1] += "\n"
    return lines + ["\n"] + block, True
  before = lines[:at]
  while before and not before[-1].strip():
    before = before[:-1]
  return before + ["\n"] + block + ["\n"] + lines[at:], True


def resolve(person):
  f = person if person.endswith(".md") else person + ".md"
  path = f if os.path.isabs(f) else os.path.join(PEOPLE, os.path.basename(f))
  if not os.path.isfile(path):
    pa.die(f"no people file {path}; find it with `people-note.py find`, or ask Ian whether to create one")
  return path


def misplaced(fname):
  """Log lines that sit outside an Email/Meeting log section (e.g. under LinkedIn messages)."""
  with open(os.path.join(PEOPLE, fname), encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
  section, bad = None, []
  for ln in lines:
    if ln.startswith("#"):
      section = ln.strip()
    elif LOG_LINE_RE.match(ln) and section not in ("### Email log", "### Meeting log"):
      bad.append(ln.rstrip("\n"))
  return bad


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  p = sub.add_parser("find", help="find a person's file")
  p.add_argument("name")
  p.add_argument("--email")
  p = sub.add_parser("log", help="add a log line to a person's file")
  p.add_argument("person", help="file name (Jane_Doe or Jane_Doe.md)")
  p.add_argument("text")
  p.add_argument("--kind", required=True,
                 help='"email, work", "email, personal", slack, whatsapp, linkedin or meeting')
  p.add_argument("--task", type=int, action="append", default=[], help="task number (repeatable)")
  p.add_argument("--ref", action="append", default=[], help="other reference, e.g. meetings/<file>.txt")
  p.add_argument("--date", default=datetime.date.today().isoformat())
  p.add_argument("--dry-run", action="store_true")
  sub.add_parser("check", help="list files with log lines outside their log section")
  args = ap.parse_args()

  if args.cmd == "find":
    hits = find(args.name, args.email)
    if not hits:
      print(f"no file for {args.name}" + (f" or {args.email}" if args.email else ""))
      sys.exit(1)
    for f, why, info in hits:
      print(f"{f}\t{why}\t{info}")
    return

  if args.cmd == "check":
    n = 0
    for f in person_files():
      bad = misplaced(f)
      if bad:
        n += 1
        print(f"{f}: {len(bad)} line(s) outside a log section, e.g. {pa.one_line(bad[0], 80)}")
    print(f"{n} file(s)")
    return

  path = resolve(args.person)
  text = " ".join(args.text.split())
  refs = [f"task {t}" for t in args.task] + args.ref
  entry = f"- {args.date} ({args.kind}): {text}" + (f" [{', '.join(refs)}]" if refs else "")
  heading = "### Meeting log" if args.kind.startswith("meeting") else "### Email log"
  with open(path, encoding="utf-8") as f:
    lines = f.readlines()
  new, changed = add_line(lines, heading, entry)
  name = os.path.basename(path)
  if not changed:
    print(f"{name}: already has that line")
    return
  if args.dry_run:
    print(f"{name}: would add under {heading}: {entry}")
    return
  with open(path, "w", encoding="utf-8") as f:
    f.writelines(new)
  print(f"{name}: added under {heading}: {entry}")


if __name__ == "__main__":
  main()
