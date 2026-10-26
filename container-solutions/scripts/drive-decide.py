#!/usr/bin/env python3
"""Record Ian's decisions on files the checks flagged, so they don't come up again.

  drive-decide.py add <file_id> catalog|filing <decision> [note ...]
  drive-decide.py list [catalog|filing]
  drive-decide.py remove <file_id> [catalog|filing]

Decisions are free text, e.g. "not-marketing", "fine-here", "added", "moved". They live in
~/.claude/container-solutions/drive-decisions.tsv (local: the repo is public). A file with a
decision for a check is left out of that check's output from then on.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_drive as cs  # noqa: E402

CHECKS = ("catalog", "filing")


def read_lines():
  if not os.path.exists(cs.DECISIONS):
    return []
  with open(cs.DECISIONS) as f:
    return [l.rstrip("\n") for l in f if l.strip()]


def write_lines(lines):
  os.makedirs(cs.STATE, exist_ok=True)
  with open(cs.DECISIONS, "w") as f:
    f.write("".join(l + "\n" for l in lines))


def main():
  ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  sub = ap.add_subparsers(dest="cmd", required=True)
  p = sub.add_parser("add")
  p.add_argument("file_id")
  p.add_argument("check", choices=CHECKS)
  p.add_argument("decision")
  p.add_argument("note", nargs="*")
  p = sub.add_parser("list")
  p.add_argument("check", nargs="?", choices=CHECKS)
  p = sub.add_parser("remove")
  p.add_argument("file_id")
  p.add_argument("check", nargs="?", choices=CHECKS)
  args = ap.parse_args()

  if args.cmd == "add":
    keep = [l for l in read_lines() if l.split("\t")[:2] != [args.file_id, args.check]]
    note = " ".join(args.note).replace("\t", " ")
    write_lines(keep + [cs.line(args.file_id, args.check, args.decision, note)])
    print(cs.line("added", args.file_id, args.check, args.decision, note))
  elif args.cmd == "list":
    for fid, (decision, note) in sorted(cs.load_decisions(args.check).items()):
      print(cs.line(fid, decision, note))
  else:
    lines = read_lines()
    keep = [l for l in lines if not (l.split("\t")[0] == args.file_id and (not args.check or l.split("\t")[1] == args.check))]
    write_lines(keep)
    print(f"removed {len(lines) - len(keep)}")


if __name__ == "__main__":
  main()
