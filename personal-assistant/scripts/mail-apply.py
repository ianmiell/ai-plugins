#!/usr/bin/env python3
"""Carry out approved mail actions through gog, with the star house rules built in.

Reads a plan on stdin, one action per line: `<mailbox> <action> <threadId> [argument]`.

  archive          leave the inbox, unstarred (unstar-outside-inbox.md)
  keep             stay in the inbox, starred (read later, kept, waiting; star-processed-inbox.md)
  trash            unstar, then move every message of the thread to the trash
  spam             mark spam, out of the inbox, unstarred
  label <Name>     add a label, out of the inbox, unstarred (--create-labels to make a new one)
  gtd <N>          add the GTD-<N> label (made if missing); the thread stays where it is,
                   starred if it's in the inbox, unless the plan also archives it
  star / unstar    just that

  mail-apply.py --dry-run <<'EOF'
  work archive 1a15b0aad89c09a9
  personal keep 1a159da84468dd9d
  personal gtd 4710 1a15a0c93b4fd2b5
  personal archive 1a15a0c93b4fd2b5
  EOF

Several lines may name one thread; labels go on first, then the thread moves. Every thread
the plan names that is still in the inbox at the end is starred, and every one that left it
is unstarred. Sends nothing (gog runs with --gmail-no-send). Drafts aren't done here: they
need the text Ian approved, so the skill makes them with `gog gmail drafts reply`.
Prints a line per thread and a count per mailbox; exits 1 if anything failed.
"""

import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

MOVES = ("archive", "trash", "spam", "label", "keep")
ACTIONS = MOVES + ("gtd", "star", "unstar")


def parse(lines):
  plan = collections.OrderedDict()
  errors = []
  for i, raw in enumerate(lines, 1):
    raw = raw.strip()
    if not raw or raw.startswith("#"):
      continue
    parts = raw.split(None, 3)
    if len(parts) < 3:
      errors.append(f"line {i}: want `<mailbox> <action> <threadId> [argument]`: {raw}")
      continue
    mailbox, action = parts[0], parts[1]
    if mailbox not in pa.MAILBOXES:
      errors.append(f"line {i}: unknown mailbox {mailbox!r}")
      continue
    if action not in ACTIONS:
      errors.append(f"line {i}: unknown action {action!r}")
      continue
    # `gtd N thread` and `label Name thread` read more naturally; accept both orders.
    if action in ("gtd", "label"):
      if len(parts) < 4:
        errors.append(f"line {i}: {action} needs an argument and a thread")
        continue
      a, b = parts[2], parts[3].strip()
      if action == "gtd":
        arg, thread = (a, b) if a.isdigit() else (b, a)
        if not arg.isdigit():
          errors.append(f"line {i}: gtd needs a task number")
          continue
      else:
        thread, arg = (a, b) if re.fullmatch(r"[0-9a-f]{16}", a) else (b, a)
    else:
      thread, arg = parts[2], (parts[3].strip() if len(parts) > 3 else None)
    t = plan.setdefault((mailbox, thread), {"labels": [], "move": None, "star": None})
    if action == "gtd":
      t["labels"].append(f"GTD-{arg}")
    elif action == "label":
      t["labels"].append(arg)
      if t["move"] in (None, "keep"):
        t["move"] = "label"
    elif action in ("star", "unstar"):
      t["star"] = action == "star"
    else:
      if t["move"] not in (None, "keep", "label") and t["move"] != action:
        errors.append(f"line {i}: thread {thread} has both {t['move']} and {action}")
        continue
      if not (action == "keep" and t["move"]):
        t["move"] = action
  return plan, errors


class Labels:
  def __init__(self, mailbox, dry_run, create):
    self.mailbox, self.dry_run, self.create = mailbox, dry_run, create
    self.by_name = {lab["name"]: lab["id"] for lab in pa.gog(mailbox, "gmail", "labels", "list") or []}

  def id(self, name):
    if name in self.by_name:
      return self.by_name[name]
    if not (self.create or name.startswith("GTD-")):
      raise pa.GogError(f"no label {name!r} in {self.mailbox} (pass --create-labels once Ian agrees)")
    made = pa.gog(self.mailbox, "gmail", "labels", "create", name, dry_run=self.dry_run)
    lid = (made or {}).get("id", name) if isinstance(made, dict) else name
    self.by_name[name] = lid
    return lid


def apply_one(mailbox, thread, t, labels, dry_run):
  add, remove = [labels.id(n) for n in t["labels"]], []
  move = t["move"]
  in_inbox = None  # unknown: ask Gmail at the end
  if move in ("archive", "label"):
    remove += ["INBOX", "STARRED"]
    in_inbox = False
  elif move == "spam":
    add.append("SPAM")
    remove += ["INBOX", "STARRED"]
    in_inbox = False
  elif move == "trash":
    remove.append("STARRED")
    in_inbox = False
  elif move == "keep":
    add.append("STARRED")
    in_inbox = True
  if t["star"] is True:
    add.append("STARRED")
  elif t["star"] is False:
    remove.append("STARRED")
  if in_inbox is None and t["star"] is None:
    # gtd label only: star it if it's still in the inbox (star-processed-inbox.md).
    data = pa.gog(mailbox, "gmail", "thread", "get", thread)
    msgs = (data.get("thread", data) or {}).get("messages", [])
    if any("INBOX" in m.get("labelIds", []) for m in msgs):
      add.append("STARRED")
  args = []
  if add:
    args += ["--add", ",".join(dict.fromkeys(add))]
  if remove:
    args += ["--remove", ",".join(dict.fromkeys(remove))]
  if args:
    pa.gog(mailbox, "gmail", "thread", "modify", thread, *args, dry_run=dry_run)
  if move == "trash":
    data = pa.gog(mailbox, "gmail", "thread", "get", thread)
    ids = [m["id"] for m in (data.get("thread", data) or {}).get("messages", [])]
    pa.gog(mailbox, "gmail", "trash", *ids, dry_run=dry_run)
  what = move or ("star" if t["star"] else "unstar" if t["star"] is False else "gtd")
  if t["labels"]:
    what += " + " + ",".join(t["labels"])
  return what


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("--dry-run", action="store_true")
  ap.add_argument("--create-labels", action="store_true", help="make labels that don't exist yet")
  args = ap.parse_args()

  plan, errors = parse(sys.stdin.readlines())
  for e in errors:
    print(e)
  if errors:
    sys.exit(2)
  labels, counts, failed = {}, collections.defaultdict(collections.Counter), False
  for (mailbox, thread), t in plan.items():
    try:
      if mailbox not in labels:
        labels[mailbox] = Labels(mailbox, args.dry_run, args.create_labels)
      what = apply_one(mailbox, thread, t, labels[mailbox], args.dry_run)
      counts[mailbox][what.split(" ")[0]] += 1
      print(f"{mailbox} {thread}: {'would ' if args.dry_run else ''}{what}")
    except pa.GogError as e:
      failed = True
      counts[mailbox]["failed"] += 1
      print(f"{mailbox} {thread}: FAILED: {e}")
  for mb, c in counts.items():
    print(f"{mb}: " + ", ".join(f"{k} {v}" for k, v in c.items()))
  sys.exit(1 if failed else 0)


if __name__ == "__main__":
  main()
