#!/usr/bin/env python3
"""Find open gtd tasks that mention any of some terms (names, Gmail thread ids, subject words).

Reads only tasks in status/todo and status/waiting (add --status for others), so the repo's
thousands of closed tasks never come into it. Matching is case-insensitive substring on the
whole notes.md. Tasks are ranked by how many different terms they match.

  gtd-find.py "Jane Doe" 19a2f0c3b4 "contract renewal"
  gtd-find.py --batch <<'EOF'
  1: Jane Doe | jane@acme.com | renewal
  4: Sam Smith | 1a15a0c93b4fd2b5
  EOF

In --batch mode each line is `<item label>: term | term | ...`, and the output is grouped by
label, so one call covers every item of a triage run.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402


def load_tasks(statuses):
  tasks = []
  for n, status in pa.open_tasks(statuses):
    path = os.path.join(pa.GTD, "tasks", str(n), "notes.md")
    try:
      with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    except OSError:
      continue
    lines = text.splitlines()
    subject = lines[0].lstrip("# ").strip() if lines else ""
    tasks.append({"task": n, "status": status, "subject": subject, "lower": text.lower(),
                  "words": URL_RE.sub(" ", text).lower(), "lines": lines})
  return tasks


URL_RE = re.compile(r"https?://\S+")
ID_RE = re.compile(r"[\w:.@%+-]+")


def matches(term, task):
  """Ids and addresses (no spaces; 12+ chars, or 8+ with a digit or @) match anywhere, links
  included; other terms match whole words outside links, so "Google" doesn't hit every
  mail.google.com link."""
  t = term.lower()
  if ID_RE.fullmatch(t) and (len(t) >= 12 or (len(t) >= 8 and re.search(r"[\d@]", t))):
    return t in task["lower"]
  return re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", task["words"]) is not None


def search(tasks, terms, limit, min_terms):
  terms = [t.strip() for t in terms if t.strip()]
  hits = []
  for t in tasks:
    matched = [term for term in terms if matches(term, t)]
    if len(matched) < min_terms:
      continue
    first = matched[0].lower()
    line = next((ln for ln in t["lines"][1:] if first in ln.lower()), t["lines"][0] if t["lines"] else "")
    reminder = pa.task_reminder(t["task"])
    hits.append({"task": t["task"], "status": t["status"], "subject": t["subject"],
                 "matched": matched, "line": pa.one_line(line, 90),
                 "reminder": reminder.strftime("%Y-%m-%d") if reminder else None})
  hits.sort(key=lambda h: (-len(h["matched"]), -h["task"]))
  return hits[:limit]


def print_hits(hits, indent=""):
  if not hits:
    print(f"{indent}(no open task)")
  for h in hits:
    rem = f" remind {h['reminder']}" if h["reminder"] else ""
    print(f"{indent}{h['task']} [{h['status']}{rem}] {h['subject']}")
    print(f"{indent}    matched: {', '.join(h['matched'])} | {h['line']}")


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("terms", nargs="*")
  ap.add_argument("--batch", action="store_true", help="read `label: term | term` lines on stdin")
  ap.add_argument("--status", action="append", choices=pa.STATUSES,
                  help="statuses to search (default todo and waiting; repeatable)")
  ap.add_argument("--min", type=int, default=1, help="least number of terms a task must match")
  ap.add_argument("--limit", type=int, default=5, help="most tasks shown per query")
  ap.add_argument("--json", action="store_true")
  args = ap.parse_args()

  if not os.path.isdir(os.path.join(pa.GTD, "status")):
    pa.die(f"no gtd repo at {pa.GTD} (set GTD_DIR)")
  tasks = load_tasks(args.status or pa.OPEN_STATUSES)

  if args.batch:
    results = []
    for raw in sys.stdin:
      raw = raw.strip()
      if not raw or raw.startswith("#"):
        continue
      label, _, rest = raw.partition(":")
      if not rest:
        label, rest = raw, raw
      results.append({"item": label.strip(),
                      "hits": search(tasks, rest.split("|"), args.limit, args.min)})
    if args.json:
      print(pa.as_json(results))
    else:
      for r in results:
        print(f"{r['item']}:")
        print_hits(r["hits"], "  ")
    return

  if not args.terms:
    ap.error("give terms, or --batch")
  hits = search(tasks, args.terms, args.limit, args.min)
  if args.json:
    print(pa.as_json(hits))
  else:
    print_hits(hits)


if __name__ == "__main__":
  main()
