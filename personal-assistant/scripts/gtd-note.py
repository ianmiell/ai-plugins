#!/usr/bin/env python3
"""Add a dated note to an existing gtd task, push it, and tag the email it came from.

The note comes on stdin. Only run it once Ian has approved the note.

  gtd-note.py 4646 --mailbox personal --thread 1a15a0c93b4fd2b5 <<'EOF'
  Clinic moved the deadline to Fri 30 Oct.
  EOF

  gtd-note.py 4630 --link "https://containersolutions.slack.com/archives/D0123/p1792500000123456" <<'EOF'
  Gustavo will demo on Tue; wants the slides by Mon.
  EOF

  gtd-note.py 4652 --ref meetings/20261016_1508_Acme.txt <<'EOF'
  Transcript of the meeting.
  EOF

What it does, in order:
  1. Checks tasks/N/notes.md is task N, and that the task isn't closed.
  2. Appends a blank line, `YYYY-MM-DD: <first line of the note>`, any further lines, then
     the source on its own line (--link, --ref, or for --mailbox/--thread the thread's Gmail
     URL from `gog gmail url`). The same note twice is added once.
  3. `bin/gtd push`.
  4. With --mailbox/--thread: labels the thread GTD-<N> (made if missing) and, with --archive,
     archives and unstars it, through mail-apply.py. On the MacBook Pro the work mailbox is the
     Gmail connector's: pass the connector's viewUrl as --link, leave out --mailbox, and label
     the thread with the connector.
Prints a line per step; stops at the first step that fails.
"""

import argparse
import datetime
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def step(ok, what, detail=""):
  print(("ok    " if ok else "FAIL  ") + what + (f": {detail.strip()}" if detail.strip() else ""))
  if not ok:
    sys.exit(1)


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("task", type=int)
  ap.add_argument("--link", help="source line (Slack link, 'WhatsApp: <chat>, <time>', connector viewUrl)")
  ap.add_argument("--ref", help="another reference, e.g. meetings/<file>.txt")
  ap.add_argument("--mailbox", choices=list(pa.MAILBOXES))
  ap.add_argument("--thread", help="Gmail thread id (with --mailbox)")
  ap.add_argument("--archive", action="store_true", help="archive the thread once labelled")
  ap.add_argument("--date", default=datetime.date.today().isoformat())
  ap.add_argument("--dry-run", action="store_true", help="print the note, change nothing")
  args = ap.parse_args()
  if bool(args.mailbox) != bool(args.thread):
    ap.error("--mailbox and --thread go together")
  if args.archive and not args.thread:
    ap.error("--archive needs --mailbox and --thread")
  if sum(bool(x) for x in (args.link, args.ref, args.thread)) > 1:
    ap.error("give one of --link, --ref, or --mailbox and --thread")
  notes = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
  if not notes:
    ap.error("the note goes on stdin")

  n = args.task
  path = os.path.join(pa.GTD, "tasks", str(n), "notes.md")
  try:
    with open(path, encoding="utf-8") as f:
      text = f.read()
  except OSError:
    pa.die(f"no task {n} (no tasks/{n}/notes.md)")
  lines = text.splitlines()
  if len(lines) < 2 or lines[1].strip() != f"Task Number: {n}":
    step(False, "check task", f"tasks/{n}/notes.md doesn't say `Task Number: {n}` on line 2; not touching it")
  status = pa.task_status(n)
  if status == "closed":
    step(False, "check task", f"task {n} is closed; reopen it first (bin/gtd ms todo {n}) if Ian wants the note")

  source = args.link or args.ref
  if args.thread:
    if args.dry_run:
      source = f"<Gmail link for {args.mailbox} thread {args.thread}>"
    else:
      try:
        urls = pa.gog(args.mailbox, "gmail", "url", args.thread) or []
        source = urls[0]["url"]
      except (pa.GogError, IndexError, KeyError) as e:
        step(False, "Gmail link", str(e))

  body = notes.splitlines()
  block = [f"{args.date}: {body[0].strip()}"] + [l.rstrip() for l in body[1:]] + ([source] if source else [])
  print(f"task {n} [{status}] {lines[0].lstrip('# ').strip()}")
  if args.dry_run:
    print("would add:\n" + "\n".join("  " + l for l in block))
    if args.thread:
      print(f"would label {args.mailbox} thread {args.thread} GTD-{n}" + (" and archive it" if args.archive else ""))
    return

  if "\n".join(block) in text:
    step(True, "note", "already there")
  else:
    with open(path, "w", encoding="utf-8") as f:
      f.write(text.rstrip("\n") + "\n\n" + "\n".join(block) + "\n")
    code, out, err = pa.gtd_cmd("push")
    step(code == 0, "note + gtd push", "" if code == 0 else out + err)

  if args.thread:
    plan = f"{args.mailbox} gtd {n} {args.thread}\n"
    if args.archive:
      plan += f"{args.mailbox} archive {args.thread}\n"
    p = subprocess.run([sys.executable, os.path.join(HERE, "mail-apply.py")], input=plan,
                       capture_output=True, text=True)
    step(p.returncode == 0, f"GTD-{n} label" + (" + archive" if args.archive else ""),
         p.stdout.splitlines()[0] if p.returncode == 0 and p.stdout else p.stdout + p.stderr)


if __name__ == "__main__":
  main()
