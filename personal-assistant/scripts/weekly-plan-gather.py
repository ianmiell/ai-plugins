#!/usr/bin/env python3
"""Everything the weekly plan needs for one Monday-to-Sunday week, in one compact print.

  weekly-plan-gather.py --work W.json --personal P.json            # the coming week
  weekly-plan-gather.py --work W.json --personal P.json --monday 2026-11-16
  weekly-plan-gather.py --gog work --personal P.json
  weekly-plan-gather.py --window-only                               # startTime/endTime to fetch

The week is the next Monday after today (on a Monday, that Monday), unless --monday names one.
The calendar files are the list_events results for the week, as calendar-events.py reads them
(any wrapper; --gog fetches a calendar with gog instead). It prints:

  - the email subject, the window for list_events, and anything missing
  - CLASHES across both calendars, then each day Mon to Sun in London time with its zone (GMT or
    BST, per day, so the late-October clock change is right): the agenda lines (declined events
    left out), all-day events, and on weekdays the free blocks of 90 minutes or more between
    09:00 and 17:30
  - REMINDERS from today to Friday (`gtd-list.py reminders`)
  - OPEN TASKS (`gtd-list.py open`: todo and waiting with priorities and flags)
  - NOTES: the last 12 non-blank lines of notes.md for each high-priority todo, each overdue task
    and each reminder due by Friday

A calendar or the task list that can't be read is named on a `missing:` line, so the email can
say so. It changes nothing. --now YYYY-MM-DDTHH:MM stands in for the clock (tests).
"""

import argparse
import datetime
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402


def load_module(name, file):
  spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
  mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(mod)
  return mod


ce = load_module("calendar_events", "calendar-events.py")
mail = load_module("pa_mail_html", "pa-mail-html.py")
NOTE_LINES = 12


def gtd_list(*args, now=None):
  cmd = [sys.executable, os.path.join(HERE, "gtd-list.py"), *args] + (["--now", now] if now else [])
  p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
  if p.returncode != 0:
    raise RuntimeError((p.stderr or p.stdout).strip() or f"exit {p.returncode}")
  return p.stdout


def last_lines(n, count=NOTE_LINES):
  try:
    with open(os.path.join(pa.GTD, "tasks", str(n), "notes.md"), encoding="utf-8", errors="replace") as f:
      lines = [l.rstrip() for l in f if l.strip()]
  except OSError:
    return []
  lines = [l for l in lines[1:] if not l.startswith("Task Number:")]  # the first line is the subject
  return [pa.one_line(l, 160) for l in lines[-count:]]


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("--work", action="append", default=[], metavar="FILE")
  ap.add_argument("--personal", action="append", default=[], metavar="FILE")
  ap.add_argument("--gog", action="append", default=[], choices=["work", "personal"])
  ap.add_argument("--monday", help="YYYY-MM-DD (default: the coming Monday)")
  ap.add_argument("--window-only", action="store_true", help="just the week and the list_events window")
  ap.add_argument("--from", dest="start", default="09:00")
  ap.add_argument("--to", dest="stop", default="17:30")
  ap.add_argument("--min", type=int, default=90)
  ap.add_argument("--now", help=argparse.SUPPRESS)
  args = ap.parse_args()
  now = ce.now_london(args.now)
  today = now.date()
  if args.monday:
    try:
      mon = datetime.date.fromisoformat(args.monday)
    except ValueError:
      pa.die(f"bad date {args.monday!r}: use YYYY-MM-DD", 2)
    if mon.weekday():
      pa.die(f"{args.monday} is a {mon:%A}, not a Monday", 2)
  else:
    mon = today + datetime.timedelta(days=(7 - today.weekday()) % 7)
  fri, after = mon + datetime.timedelta(days=4), mon + datetime.timedelta(days=7)
  start, end = ce.win_times(mon, after)
  zones = ce.zones_text(mon, after)
  print(f"WEEK {ce.day_label(mon)} to {ce.day_label(fri, True)} (weekend to {ce.day_label(after - datetime.timedelta(days=1))}), "
        f"times London: {zones}")
  print(f"subject: {mail.subject('weekly', mon)}")
  print(f"list_events: startTime {start:%Y-%m-%dT%H:%M:%S} endTime {end:%Y-%m-%dT%H:%M:%S}")
  if args.window_only:
    return

  missing = []
  if not (args.work or "work" in args.gog):
    missing.append("work calendar (not given)")
  if not (args.personal or "personal" in args.gog):
    missing.append("personal calendar (not given)")
  events, info = ce.load(args.work, args.personal, args.gog, (start, end))
  missing += ce.errors(info)
  n = len(events)
  events = ce.merge(events)
  merged = n - len(events)
  hidden = len([e for e in events if ce.declined(e)])
  events = [e for e in events if not ce.declined(e)]
  ce.flag(events)

  tasks_out = rem_out = None
  tasks = []
  try:
    tasks_out = gtd_list("open", now=args.now)
    tasks = json.loads(gtd_list("open", "--json", now=args.now))
    rem = json.loads(gtd_list("reminders", today.isoformat(), max(today, fri).isoformat(), "--json", now=args.now))
    rem_out = gtd_list("reminders", today.isoformat(), max(today, fri).isoformat(), now=args.now)
  except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as e:
    missing.append(f"gtd tasks: {pa.one_line(str(e), 150)}")
    rem = []
  for m in missing:
    print(f"missing: {m}")
  print("calendars: " + ce.summary(info, hidden, merged))

  clashes = [(e, c) for e in events for c in e["clash_with"] if ce.sort_key(e) < ce.sort_key(c)]
  if clashes:
    print(f"\nCLASHES ({len(clashes)})")
    for a, b in clashes:
      print(f"  {ce.day_label(a['start'].date())} {ce.hm(a['start'])}-{ce.hm(a['end'])} {a['cal']} \"{pa.one_line(a['title'], 40)}\""
            f" overlaps {ce.hm(b['start'])}-{ce.hm(b['end'])} {b['cal']} \"{pa.one_line(b['title'], 40)}\"")
  frm, to = ce.parse_hm(args.start), ce.parse_hm(args.stop)
  d = mon
  while d < after:
    todays = sorted((e for e in events if ce.on_day(e, d)), key=lambda e: (not e["all_day"], ce.sort_key(e)))
    timed = [e for e in todays if not e["all_day"]]
    lo, hi = ce.midnight(d), ce.midnight(d + datetime.timedelta(days=1))
    spans, load, t = sorted((max(e["start"], lo), min(e["end"], hi)) for e in timed if ce.busy(e)), 0.0, lo
    for s, f in spans:
      if f > t:
        load += (f - max(s, t)).total_seconds() / 3600
        t = f
    print(f"\n{ce.day_label(d).upper()} ({ce.zone(d)}): {len(timed)} meeting(s), {load:.1f}h busy")
    for e in todays:
      mark = "⚠ " if "CLASH" in e["flags"] or "TIGHT" in e["flags"] else "  "
      print(mark + ce.ev_line(e, set(ce.FIELDS), d))
    if d.weekday() < 5:
      gaps = ce.free_gaps(events, d, frm, to, args.min)
      print(f"  free {args.start}-{args.stop} >= {args.min}m: "
            + (", ".join(f"{ce.hm(s)}-{ce.hm(e)} ({ce.dur(s, e)})" for s, e in gaps) or "none"))
    d += datetime.timedelta(days=1)

  print(f"\nREMINDERS {today:%a %d %b} to {fri:%a %d %b}")
  print("  " + (rem_out or "(not read)").strip().replace("\n", "\n  "))
  print("\nOPEN TASKS")
  print("  " + (tasks_out or "(not read)").strip().replace("\n", "\n  "))

  pick = {}
  for t in tasks:
    if t.get("priority") == "high" and t.get("status") == "todo":
      pick.setdefault(t["task"], (t["subject"], "high"))
    if "OVERDUE" in (t.get("flags") or []):
      pick.setdefault(t["task"], (t["subject"], "overdue"))
  for r in rem:
    pick.setdefault(r["task"], (r["subject"], f"reminder {r['reminder'][:10]}"))
  if pick:
    print(f"\nNOTES (last {NOTE_LINES} non-blank lines)")
    for n, (subject, why) in sorted(pick.items()):
      print(f"  #{n} {pa.one_line(subject, 80)} ({why})")
      for l in last_lines(n) or ["(no notes)"]:
        print(f"    {l}")


if __name__ == "__main__":
  main()
