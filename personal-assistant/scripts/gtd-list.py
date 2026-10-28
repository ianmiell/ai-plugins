#!/usr/bin/env python3
"""List gtd tasks for review, grouped by subject prefix, with their reminders and what to flag.

  gtd-list.py                         # todo, grouped by prefix (CS, HOME, MC, ...)
  gtd-list.py waiting                 # also background, someday, new, or open (todo + waiting)
  gtd-list.py todo waiting --soon 3 --stale 60
  gtd-list.py reminders 2026-10-28 2026-11-03   # reminders firing in a window (calendar skill)

Reads the task files directly (no bin/gtd run, no per-task subprocess), so it's quick on the
whole repo and changes nothing.

`list` (the default) prints, per prefix, one line per task: number, priority (when not medium),
subject, reminder date, and flags:
  OVERDUE         the reminder is in the past
  due in Nd       the reminder fires within --soon days (7)
  untouched Nd    no file in the task's folder changed for --stale days (90) or more. It reads
                  file times, which a fresh clone resets, so it can only under-report.
  past meeting    a `MEETING: ... starting at Tue 20 Oct, 10:00, id: ...` task whose time has
                  passed: `bin/gtd clear-meetings` closes them
Then a FLAGS block repeats the flagged tasks, worst first, so Ian sees them without scrolling.

`reminders FROM [TO]` prints every task that isn't closed whose reminder falls between FROM and
TO (dates, both inclusive; TO defaults to FROM), soonest first, leaving out `MEETING:` tasks
(they mirror calendar events).
"""

import argparse
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

PRIORITIES = ("high", "medium", "low")
PREFIX_RE = re.compile(r"^([A-Z][A-Z0-9&_-]{0,11}):\s")
MEETING_RE = re.compile(r"^MEETING: .* starting at ([A-Z][a-z]{2} \d{1,2} [A-Z][a-z]{2}), (\d{2}:\d{2}), id: ")
PREFIX_ORDER = ("CS", "HOME", "MC")


def task_priority(n):
  for p in PRIORITIES:
    if os.path.lexists(os.path.join(pa.GTD, "priority", p, str(n))):
      return p
  return "medium"


def last_touched(n):
  d = os.path.join(pa.GTD, "tasks", str(n))
  times = []
  try:
    for name in os.listdir(d):
      try:
        times.append(os.stat(os.path.join(d, name)).st_mtime)
      except OSError:
        pass
  except OSError:
    pass
  return datetime.datetime.fromtimestamp(max(times)) if times else None


def meeting_time(subject, now):
  """The time a MEETING: task's meeting starts, as gtd clear-meetings reads it (this year)."""
  m = MEETING_RE.match(subject)
  if not m:
    return None
  try:
    return datetime.datetime.strptime(f"{m.group(1)} {now.year} {m.group(2)}", "%a %d %b %Y %H:%M")
  except ValueError:
    return None


def load(statuses, now, soon, stale):
  tasks = []
  for n, status in pa.open_tasks(statuses):
    subject = pa.task_subject(n)
    if subject is None:
      continue
    m = PREFIX_RE.match(subject)
    t = {"task": n, "status": status, "subject": subject, "prefix": m.group(1) if m else "",
         "priority": task_priority(n), "reminder": pa.task_reminder(n), "flags": [], "rank": 9}
    if t["reminder"]:
      days = (t["reminder"].date() - now.date()).days
      if t["reminder"] < now:
        t["flags"].append("OVERDUE")
        t["rank"] = 0
      elif days <= soon:
        t["flags"].append(f"due in {days}d" if days else "due today")
        t["rank"] = 2
    when = meeting_time(subject, now)
    if when and when < now:
      t["flags"].append("past meeting")
      t["rank"] = min(t["rank"], 1)
    touched = last_touched(n)
    if touched and stale and (now - touched).days >= stale and not when:
      t["flags"].append(f"untouched {(now - touched).days}d")
      t["rank"] = min(t["rank"], 3)
    tasks.append(t)
  return tasks


def line(t, show_status):
  bits = [f"{t['task']:>5}"]
  if show_status:
    bits.append(f"[{t['status']}]")
  if t["priority"] != "medium":
    bits.append(f"({t['priority']})")
  bits.append(pa.one_line(t["subject"], 90))
  if t["reminder"]:
    bits.append(f"remind {t['reminder']:%Y-%m-%d}")
  if t["flags"]:
    bits.append("⚑ " + ", ".join(t["flags"]))
  return " ".join(bits)


def cmd_list(args, now):
  statuses = []
  for s in args.statuses or ["todo"]:
    statuses += list(pa.OPEN_STATUSES) if s == "open" else [s]
  statuses = list(dict.fromkeys(statuses))
  tasks = load(statuses, now, args.soon, args.stale)
  if args.json:
    print(pa.as_json(tasks))
    return
  show_status = len(statuses) > 1
  groups = {}
  for t in tasks:
    groups.setdefault(t["prefix"], []).append(t)
  order = [p for p in PREFIX_ORDER if p in groups] + sorted(p for p in groups if p not in PREFIX_ORDER and p) + \
          ([""] if "" in groups else [])
  prio = {p: i for i, p in enumerate(PRIORITIES)}
  print(f"{len(tasks)} task(s) in {', '.join(statuses)}")
  for p in order:
    group = sorted(groups[p], key=lambda t: (prio[t["priority"]], t["reminder"] or datetime.datetime.max, -t["task"]))
    print(f"\n{p or '(no prefix)'} ({len(group)})")
    for t in group:
      print("  " + line(t, show_status))
  flagged = sorted((t for t in tasks if t["flags"]), key=lambda t: (t["rank"], t["reminder"] or now, t["task"]))
  if flagged:
    print(f"\nFLAGS ({len(flagged)})")
    for t in flagged:
      print("  " + line(t, show_status))
    if any("past meeting" in t["flags"] for t in flagged):
      print("  → past MEETING: tasks: bin/gtd clear-meetings closes them")


def parse_date(s):
  try:
    return datetime.date.fromisoformat(s)
  except ValueError:
    pa.die(f"bad date {s!r}: use YYYY-MM-DD", 2)


def cmd_reminders(args, now):
  start = parse_date(args.start)
  end = parse_date(args.end) if args.end else start
  hits = []
  for n, status in pa.open_tasks([s for s in pa.STATUSES if s != "closed"]):
    r = pa.task_reminder(n)
    if not r or not start <= r.date() <= end:
      continue
    subject = pa.task_subject(n) or ""
    if subject.startswith("MEETING:"):
      continue
    hits.append({"task": n, "status": status, "subject": subject, "reminder": r})
  hits.sort(key=lambda h: (h["reminder"], h["task"]))
  if args.json:
    print(pa.as_json(hits))
    return
  if not hits:
    print(f"no reminders {start}" + (f" to {end}" if end != start else ""))
  for h in hits:
    print(f"{h['reminder']:%a %Y-%m-%d %H:%M}  {h['task']} [{h['status']}] {pa.one_line(h['subject'], 90)}")


def main():
  common = argparse.ArgumentParser(add_help=False)
  common.add_argument("--json", action="store_true")
  common.add_argument("--now", help=argparse.SUPPRESS)  # for the tests: YYYY-MM-DDTHH:MM
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd")
  p = sub.add_parser("list", parents=[common], help="tasks by prefix with flags (the default)")
  p.add_argument("statuses", nargs="*", choices=[s for s in pa.STATUSES if s != "closed"] + ["open"])
  p.add_argument("--soon", type=int, default=7, help="flag reminders due within DAYS (7)")
  p.add_argument("--stale", type=int, default=90, help="flag tasks untouched for DAYS (90; 0 turns it off)")
  p = sub.add_parser("reminders", parents=[common], help="reminders firing between two dates")
  p.add_argument("start", help="YYYY-MM-DD")
  p.add_argument("end", nargs="?", help="YYYY-MM-DD (default: the same day)")
  argv = sys.argv[1:]
  # No subcommand (a bare status, an option, or nothing) means `list`.
  if not argv or argv[0] not in ("list", "reminders", "-h", "--help"):
    argv = ["list"] + argv
  args = ap.parse_args(argv)

  if not os.path.isdir(os.path.join(pa.GTD, "status")):
    pa.die(f"no gtd repo at {pa.GTD} (set GTD_DIR)")
  now = datetime.datetime.fromisoformat(args.now) if args.now else datetime.datetime.now()
  if args.cmd == "reminders":
    cmd_reminders(args, now)
  else:
    cmd_list(args, now)


if __name__ == "__main__":
  main()
