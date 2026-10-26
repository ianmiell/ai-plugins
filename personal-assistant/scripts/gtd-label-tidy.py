#!/usr/bin/env python3
"""Tidy the mail of closed gtd tasks (rules/close-task-tidies-mail.md), through gog.

For every Gmail label `GTD-<N>` whose task N is closed (status/closed/N): archive and unstar
each thread with the label, and each thread whose Gmail link (with this mailbox's authuser)
is in tasks/N/notes.md; take the label off them; then delete the label. Labels of open
tasks are left alone. Never trashes anything.

  gtd-label-tidy.py                 # both mailboxes (personal only on the MacBook Pro)
  gtd-label-tidy.py --task 4652     # just after closing task 4652
  gtd-label-tidy.py --mailbox personal --dry-run

On the MacBook Pro the work mailbox goes through the Gmail connector, not gog, so it is left
out unless named with --mailbox work; the skill tidies it with the connector.
Prints one line per closed task, and one summary line.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

SEARCH_LIMIT = 100
LABEL_RE = re.compile(r"^GTD-(\d+)$")


def linked_threads(n, address):
  """Thread ids in task N's notes whose Gmail link is for this mailbox."""
  try:
    with open(os.path.join(pa.GTD, "tasks", str(n), "notes.md"), encoding="utf-8", errors="replace") as f:
      text = f.read()
  except OSError:
    return []
  ids = []
  for m in re.finditer(r"https://mail\.google\.com/mail/\?authuser=([^#\s]+)#[a-z]+/([0-9a-f]{16})\b", text):
    if m.group(1).replace("%40", "@").lower() == address:
      ids.append(m.group(2))
  return ids


def tidy_mailbox(mailbox, only_task, dry_run):
  address = pa.mailbox_address(mailbox)
  labels = pa.gog(mailbox, "gmail", "labels", "list") or []
  gtd_labels = []
  for lab in labels:
    m = LABEL_RE.match(lab.get("name", ""))
    if m and (only_task is None or int(m.group(1)) == only_task):
      gtd_labels.append((int(m.group(1)), lab["name"], lab["id"]))
  lines, open_n = [], 0
  tasks = {n for n, _, _ in gtd_labels}
  if only_task is not None:
    tasks.add(only_task)
  for n in sorted(tasks):
    status = pa.task_status(n)
    label = next(((name, lid) for t, name, lid in gtd_labels if t == n), None)
    if status is None:
      lines.append(f"{mailbox}: GTD-{n} has no task {n} in gtd; left alone")
      continue
    if status != "closed":
      open_n += 1
      if only_task is not None:
        lines.append(f"{mailbox}: task {n} is {status}, not closed; left alone")
      continue
    threads, capped = [], False
    if label:
      found = pa.search(mailbox, f"label:{label[0]}", SEARCH_LIMIT)
      threads = [t["id"] for t in found]
      capped = len(found) >= SEARCH_LIMIT  # may be more; keep the label so a rerun finds the rest
    threads += [t for t in linked_threads(n, address) if t not in threads]
    remove = "INBOX,STARRED" + (f",{label[1]}" if label else "")
    for t in threads:
      pa.gog(mailbox, "gmail", "thread", "modify", t, "--remove", remove, dry_run=dry_run)
    if label and not capped:
      pa.gog(mailbox, "gmail", "labels", "delete", label[1], dry_run=dry_run)
    verb = "would archive" if dry_run else "archived"
    if capped:
      tail = f", kept {label[0]}: search hit the {SEARCH_LIMIT}-thread cap, rerun to tidy the rest"
    else:
      tail = (f", {'would remove' if dry_run else 'removed'} {label[0]}" if label else ", no label")
    lines.append(f"{mailbox}: task {n} closed: {verb} {len(threads)} thread(s){tail}")
  return lines, len(gtd_labels), open_n


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("--mailbox", action="append", choices=list(pa.MAILBOXES))
  ap.add_argument("--task", type=int, help="only this task (e.g. just closed)")
  ap.add_argument("--dry-run", action="store_true")
  args = ap.parse_args()

  mailboxes = args.mailbox
  skipped = None
  if not mailboxes:
    mailboxes = ["work", "personal"]
    if pa.machine() == "macbook-pro":
      mailboxes, skipped = ["personal"], "work (MacBook Pro: use the Gmail connector)"

  summary, failed = [], False
  for mb in mailboxes:
    try:
      lines, n_labels, n_open = tidy_mailbox(mb, args.task, args.dry_run)
    except pa.GogError as e:
      failed = True
      print(f"{mb}: can't reach the mailbox, labels left in place: {e}")
      continue
    for ln in lines:
      print(ln)
    summary.append(f"{mb} {n_labels} label(s), {n_open} open")
  if skipped:
    summary.append(f"skipped {skipped}")
  print("GTD labels: " + "; ".join(summary))
  sys.exit(1 if failed else 0)


if __name__ == "__main__":
  main()
