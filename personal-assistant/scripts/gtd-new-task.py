#!/usr/bin/env python3
"""Create a gtd task with its source link and notes in one go, and tag the email it came from.

Notes come on stdin. Only run it once Ian has approved the subject, notes and status.

  gtd-new-task.py --subject "HOME: Fill in the clinic form" --mailbox personal \\
      --thread 1a15a0c93b4fd2b5 --archive --defer 2 <<'EOF'
  Clinic wants the treatment forms filled in; the link expires on Thu 22 Oct.
  EOF

  gtd-new-task.py --subject "CS: Reply to Trifork offer" \\
      --link "https://containersolutions.slack.com/archives/D0123/p1792500000123456" <<'EOF'
  ...
  EOF

What it does, in order:
  1. `GO_TO_TASK=N bin/gtd nt SUBJECT`, then reads the number from .metadata/lasttask (and
     checks the new task's subject is ours).
  2. Writes the source on the line after `Task Number:` (--link, or for --mailbox/--thread
     the thread's Gmail URL from `gog gmail url`), then the notes, then `bin/gtd push`.
  3. --priority, then --defer DAYS (reminder, moves to waiting) or --status.
  4. With --mailbox/--thread: labels the thread GTD-<N> (made if missing) and, with
     --archive, archives and unstars it, through mail-apply.py. On the MacBook Pro the work
     mailbox is the Gmail connector's: pass the connector's viewUrl as --link, leave out
     --mailbox, and label the thread with the connector.
Prints `task <N>` and a line per step; stops at the first step that fails.
"""

import argparse
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
  ap.add_argument("--subject", required=True, help='with its prefix, e.g. "CS: ..."')
  ap.add_argument("--link", help="source line (Slack link, 'WhatsApp: <chat>, <time>', connector viewUrl)")
  ap.add_argument("--mailbox", choices=list(pa.MAILBOXES))
  ap.add_argument("--thread", help="Gmail thread id (with --mailbox)")
  ap.add_argument("--archive", action="store_true", help="archive the thread once labelled")
  ap.add_argument("--defer", type=int, metavar="DAYS", help="reminder in DAYS, moves to waiting")
  ap.add_argument("--status", choices=["todo", "waiting", "background", "someday"])
  ap.add_argument("--priority", choices=["high", "medium", "low"])
  args = ap.parse_args()
  if bool(args.mailbox) != bool(args.thread):
    ap.error("--mailbox and --thread go together")
  if not args.link and not args.thread:
    ap.error("give --link, or --mailbox and --thread")
  if args.defer is not None and args.status:
    ap.error("--defer already moves the task to waiting; leave out --status")
  notes = sys.stdin.read().strip() if not sys.stdin.isatty() else ""

  link = args.link
  if not link:
    try:
      urls = pa.gog(args.mailbox, "gmail", "url", args.thread) or []
      link = urls[0]["url"]
    except (pa.GogError, IndexError, KeyError) as e:
      step(False, "Gmail link", str(e))

  last = os.path.join(pa.GTD, ".metadata", "lasttask")
  before = open(last).read().strip()
  code, out, err = pa.gtd_cmd("nt", args.subject, extra_env={"GO_TO_TASK": "N"})
  n = open(last).read().strip()
  if code != 0 or n == before:
    step(False, "gtd nt", out + err)
  notes_path = os.path.join(pa.GTD, "tasks", n, "notes.md")
  with open(notes_path, encoding="utf-8") as f:
    lines = f.read().splitlines()
  if len(lines) < 2 or lines[0] != f"# {args.subject}" or lines[1] != f"Task Number: {n}":
    step(False, "check new task", f"tasks/{n}/notes.md doesn't start with our subject; not touching it")
  print(f"task {n}")
  step(True, "gtd nt", f"task {n} created")

  body = lines[:2] + [link, ""] + (notes.splitlines() if notes else []) + [l for l in lines[2:] if l.strip()]
  with open(notes_path, "w", encoding="utf-8") as f:
    f.write("\n".join(body).rstrip() + "\n")
  code, out, err = pa.gtd_cmd("push")
  step(code == 0, "notes + gtd push", "" if code == 0 else out + err)

  if args.priority and args.priority != "medium":
    code, out, err = pa.gtd_cmd("mp", args.priority, n)
    step(code == 0, f"priority {args.priority}", "" if code == 0 else out + err)
  if args.defer is not None:
    code, out, err = pa.gtd_cmd("defer", n, str(args.defer))
    step(code == 0, f"defer {args.defer} days (waiting)", "" if code == 0 else out + err)
  elif args.status and args.status != "todo":
    code, out, err = pa.gtd_cmd("ms", args.status, n)
    step(code == 0, f"status {args.status}", "" if code == 0 else out + err)
  if (args.priority and args.priority != "medium") or args.defer is not None or \
     (args.status and args.status != "todo"):
    # mp, defer and ms stage their changes but leave the commit to gtd's next run.
    code, out, err = pa.gtd_cmd("push")
    step(code == 0, "gtd push", "" if code == 0 else out + err)

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
