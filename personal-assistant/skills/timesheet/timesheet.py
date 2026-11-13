#!/usr/bin/env python3
"""The timesheet skill's bookkeeping: which week, the proposed split, and checking the filled grid.

  timesheet.py week [--today 2026-11-02] [--last-grid LAST.json]
  timesheet.py propose --monday 2026-10-26 --grid THIS.json --prev LAST.json \\
      [--work W.json] [--personal P.json] [--holidays UK.json] [--json]
  timesheet.py check --plan PLAN.json --grid AFTER.json
  timesheet.py submitted --grid AFTER.json

The grids are what toggl-grid.js returns (a file, `-` for stdin, or the JSON itself as the
argument). The calendar files are list_events results, read as calendar-events.py reads them;
--holidays is the UK holidays calendar's list_events for the week.

week: the week to do. The current week, unless today is Monday or Tuesday and last week is still
NOT SUBMITTED (give its grid with --last-grid; without it, it says to read last week first).

propose: one project per weekday, 8:00 each, in the SKILL's order:
  1. Holiday (vacation): an England and Wales bank holiday (worked out here, plus any public
     holiday on --holidays), or Ian is off: an all-day or out-of-office event on W or P that
     reads as leave (holiday, annual leave, off, vacation, OOO), or a timed one covering most of
     09:00-17:30
  2. what's already in the grid for that day
  3. last week's project for the same weekday (the busiest row that day; else last week's
     most-booked project that isn't holiday)
It prints the table, the status, the total, the cells to change, the plan for toggl-fill.js
(`plan: {...}`, every weekday of every row, "" for empty), and the W events that might change a
day (outside attendees, or client words, suggest Pre sales work; CCF words suggest CCF). Those
hints are for Ian and the model to weigh; they aren't applied. A week that is BEING REVIEWED or
APPROVED prints LOCKED and exits 3.

check: every planned cell against the grid read back after filling, and the week total against
the plan's. OK, or one line per difference (exit 1).

submitted: the status chip; exit 0 if BEING REVIEWED (or APPROVED), 1 if not.
Submitting itself is never done here: only on Ian's explicit say-so, by hand (SKILL.md, Rules).
"""

import argparse
import datetime
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, SCRIPTS)
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

_spec = importlib.util.spec_from_file_location("calendar_events", os.path.join(SCRIPTS, "calendar-events.py"))
ce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ce)

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
WEEKDAYS = DAYS[:5]
DAY = "8:00"
CCF, PRESALES, HOLIDAY = "CCF", "Pre sales work", "Holiday (vacation)"
LEAVE_RE = re.compile(r"\b(holidays?|annual leave|leave|day off|off (work|sick)|vacation|ooo|out of office|pto)\b"
                      r"|^\s*(ian\s+)?off\b", re.I)
PRESALES_RE = re.compile(r"\b(schroders|dnb|natwest|demo|discovery|prospect|pitch|proposal|rfp|client|customer)\b", re.I)
CCF_RE = re.compile(r"\b(ccf|factory|plugin|build session)\b", re.I)
LOCKED = ("BEING REVIEWED", "APPROVED", "SUBMITTED")
CS_DOMAIN = "@container-solutions.com"


def minutes(v):
  s = str(v or "").strip().lower().rstrip("h").strip()
  if not s or s == "-":
    return 0
  m = re.fullmatch(r"(\d+):(\d{2})(?::\d{2})?", s)
  if m:
    return int(m.group(1)) * 60 + int(m.group(2))
  try:
    return round(float(s) * 60)
  except ValueError:
    pa.die(f"can't read {v!r} as hours", 2)


def hours(m):
  return f"{m // 60}:{m % 60:02d}" if m else ""


def read_json(arg):
  if arg is None:
    return None
  text = sys.stdin.read() if arg == "-" else arg if arg.lstrip().startswith(("{", "[", '"')) else \
    open(os.path.expanduser(arg), encoding="utf-8").read()
  vals = ce.json_values(text)
  if not vals:
    pa.die(f"no JSON in {arg[:60]!r}", 2)
  v = vals[0]
  while isinstance(v, str):  # javascript_tool can hand back the JSON as a quoted string
    v = json.loads(v)
  if isinstance(v, list) and v and isinstance(v[0], dict) and "text" in v[0]:
    return read_json(v[0]["text"])
  if isinstance(v, dict) and v.get("error"):
    pa.die(f"the grid wasn't read: {v['error']}", 2)
  return v


def grid_rows(grid):
  """{project: {day: minutes}} from a toggl-grid.js result."""
  out = {}
  for r in (grid or {}).get("rows", []):
    name = (r.get("project") or r.get("label") or "").strip()
    if name:
      out[name] = {d: minutes((r.get("cells") or {}).get(d)) for d in DAYS}
  return out


def status(grid):
  return " ".join(str((grid or {}).get("status") or "").upper().split())


# --- holidays --------------------------------------------------------------------------------

def easter(y):
  a, b, c = y % 19, y // 100, y % 100
  d, e = b // 4, b % 4
  f = (b + 8) // 25
  g = (b - f + 1) // 3
  h = (19 * a + b - d - g + 15) % 30
  i, k = c // 4, c % 4
  l = (32 + 2 * e + 2 * i - h - k) % 7
  m = (a + 11 * h + 22 * l) // 451
  month = (h + l - 7 * m + 114) // 31
  return datetime.date(y, month, (h + l - 7 * m + 114) % 31 + 1)


def bank_holidays(y):
  """England and Wales bank holidays by the usual rules (one-offs come from the holidays calendar)."""
  def first_monday(month):
    d = datetime.date(y, month, 1)
    return d + datetime.timedelta(days=(7 - d.weekday()) % 7)

  def last_monday(month):
    d = datetime.date(y + (month == 12), month % 12 + 1, 1) - datetime.timedelta(days=1)
    return d - datetime.timedelta(days=d.weekday())

  hols = {}
  ny = datetime.date(y, 1, 1)
  hols[ny + datetime.timedelta(days={5: 2, 6: 1}.get(ny.weekday(), 0))] = "New Year's Day"
  e = easter(y)
  hols[e - datetime.timedelta(days=2)] = "Good Friday"
  hols[e + datetime.timedelta(days=1)] = "Easter Monday"
  hols[first_monday(5)] = "Early May bank holiday"
  hols[last_monday(5)] = "Spring bank holiday"
  hols[last_monday(8)] = "Summer bank holiday"
  xmas = datetime.date(y, 12, 25)
  wd = xmas.weekday()
  if wd == 4:    # Fri: Boxing Day moves to Mon
    hols[xmas], hols[datetime.date(y, 12, 28)] = "Christmas Day", "Boxing Day"
  elif wd == 5:  # Sat: both move
    hols[datetime.date(y, 12, 27)], hols[datetime.date(y, 12, 28)] = "Christmas Day", "Boxing Day"
  elif wd == 6:  # Sun: Boxing Day on Mon, Christmas on Tue
    hols[datetime.date(y, 12, 26)], hols[datetime.date(y, 12, 27)] = "Boxing Day", "Christmas Day"
  else:
    hols[xmas], hols[datetime.date(y, 12, 26)] = "Christmas Day", "Boxing Day"
  return hols


def calendar_holidays(path, first, after):
  """Public holidays (not observances, not Scotland or Northern Ireland only) from a holidays calendar."""
  events, _ = ce.load([path], [], [], ce.win_times(first, after))
  out = {}
  for e in events:
    if not e["all_day"] or re.search(r"observance", e["description"], re.I) or \
       re.search(r"scotland|northern ireland|regional", e["title"], re.I):
      continue
    d = e["sdate"]
    while d < e["edate"]:
      out[d] = e["title"]
      d += datetime.timedelta(days=1)
  return out


def leave_days(events, days):
  """{date: reason} for days Ian is off, from W and P."""
  out = {}
  for d in days:
    lo = datetime.datetime(d.year, d.month, d.day, 9, tzinfo=ce.LONDON)
    hi = datetime.datetime(d.year, d.month, d.day, 17, 30, tzinfo=ce.LONDON)
    for e in events:
      during = ce.on_day(e, d) if e["all_day"] else e["start"] < hi and e["end"] > lo
      if ce.declined(e) or not during:
        continue
      leave = LEAVE_RE.search(e["title"]) or e["event_type"] == "outofoffice"
      if not leave:
        continue
      if e["all_day"]:
        out[d] = f"{e['cal']} \"{e['title']}\" (all day)"
      elif (min(e["end"], hi) - max(e["start"], lo)) >= datetime.timedelta(hours=6):
        out[d] = f"{e['cal']} \"{e['title']}\" {ce.hm(e['start'])}-{ce.hm(e['end'])}"
  return out


def hints(events, days):
  out = []
  for d, name in zip(days, WEEKDAYS):
    pre, ccf = [], []
    for e in events:
      if e["all_day"] or ce.declined(e) or e["cal"] == "P" or e["start"].date() != d:
        continue
      outside = [a for a in e["attendees"] if a["email"] and not a["resource"] and
                 not a["email"].endswith(CS_DOMAIN) and a["email"] not in pa.IAN_ADDRESSES]
      if outside or PRESALES_RE.search(e["title"]):
        pre.append(pa.one_line(e["title"], 30))
      elif CCF_RE.search(e["title"]):
        ccf.append(pa.one_line(e["title"], 30))
    if pre:
      out.append(f"{name}: {len(pre)} client/prospect meeting(s) ({', '.join(pre[:3])}) -> pre-sales?")
    if ccf:
      out.append(f"{name}: {len(ccf)} CCF session(s) ({', '.join(ccf[:3])}) -> CCF?")
  return out


# --- commands --------------------------------------------------------------------------------

def monday_of(d):
  return d - datetime.timedelta(days=d.weekday())


def cmd_week(args):
  today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
  this, last = monday_of(today), monday_of(today) - datetime.timedelta(days=7)

  def label(m):
    return f"W{m.isocalendar()[1]} ({m.day} {m:%b} - {(m + datetime.timedelta(days=6)).day} " \
           f"{(m + datetime.timedelta(days=6)):%b})"
  if today.weekday() <= 1:
    if not args.last_grid:
      print(f"read last week first: {label(last)}, then run again with --last-grid")
      sys.exit(2)
    st = status(read_json(args.last_grid))
    if st == "NOT SUBMITTED" or not st:
      print(f"do last week first: {label(last)} is {st or 'not read (no status)'}; monday {last}")
      return
  print(f"this week: {label(this)}; monday {this}")


def propose(args):
  mon = datetime.date.fromisoformat(args.monday)
  if mon.weekday():
    pa.die(f"{args.monday} isn't a Monday", 2)
  days = [mon + datetime.timedelta(days=i) for i in range(5)]
  grid, prev = read_json(args.grid), read_json(args.prev)
  st = status(grid)
  now_rows, prev_rows = grid_rows(grid), grid_rows(prev)
  holiday_name = next((p for p in list(now_rows) + list(prev_rows) if re.search(r"holiday", p, re.I)), HOLIDAY)

  bank = {d: n for y in {mon.year, days[-1].year} for d, n in bank_holidays(y).items()}
  missing = []
  if args.holidays:
    try:
      bank.update(calendar_holidays(args.holidays, mon, mon + datetime.timedelta(days=7)))
    except (OSError, ValueError) as e:
      missing.append(f"holidays calendar: {e}")
  events, info = ce.load(args.work, args.personal, [], ce.win_times(mon, mon + datetime.timedelta(days=7)))
  missing += ce.errors(info)
  events = ce.merge(events)
  off = leave_days(events, days)

  plan, why = {}, {}
  for d, name in zip(days, WEEKDAYS):
    filled = {p: v[name] for p, v in now_rows.items() if v[name]}
    if d in bank:
      plan[name], why[name] = {holiday_name: 480}, f"bank holiday: {bank[d]}"
    elif d in off:
      plan[name], why[name] = {holiday_name: 480}, f"off: {off[d]}"
    elif filled:
      plan[name], why[name] = filled, "already in the grid"
    else:
      last = {p: v[name] for p, v in prev_rows.items() if v[name] and not re.search(r"holiday", p, re.I)}
      if last:
        p = max(last, key=lambda k: last[k])
        plan[name], why[name] = {p: 480}, "last week's " + name
      else:
        totals = {p: sum(v[x] for x in WEEKDAYS) for p, v in prev_rows.items() if not re.search(r"holiday", p, re.I)}
        totals = {p: t for p, t in totals.items() if t}
        if totals:
          p = max(totals, key=lambda k: totals[k])
          plan[name], why[name] = {p: 480}, "last week's main project"
        else:
          plan[name], why[name] = {}, "nothing to go on: ask Ian"
  projects = list(dict.fromkeys([p for p in (CCF, PRESALES) if p in now_rows or p in prev_rows or
                                 any(p in plan[n] for n in WEEKDAYS)] +
                                [p for n in WEEKDAYS for p in plan[n]] +
                                [p for p, v in now_rows.items() if any(v[x] for x in WEEKDAYS)]))
  if holiday_name not in projects:
    projects.append(holiday_name)
  fill = {p: {n: hours(plan[n].get(p, 0)) for n in WEEKDAYS} for p in projects}
  changes = []
  for p in projects:
    for n in WEEKDAYS:
      have = now_rows.get(p, {}).get(n, 0)
      want = plan[n].get(p, 0)
      if have != want:
        changes.append({"project": p, "day": n, "from": hours(have), "to": hours(want),
                        "row_missing": p not in now_rows and bool(want)})
  fill = {p: v for p, v in fill.items() if p in now_rows or any(v.values())}
  weekend = [f"{p} {d} {hours(v[d])}" for p, v in now_rows.items() for d in ("Sat", "Sun") if v[d]]
  total = sum(m for n in WEEKDAYS for m in plan[n].values())
  w_events = [e for e in events if e["cal"] in ("W", "W+P")]
  res = {"monday": mon.isoformat(), "week": (grid or {}).get("week") or f"W{mon.isocalendar()[1]}", "status": st,
         "table": {p: {n: hours(plan[n].get(p, 0)) for n in WEEKDAYS} for p in projects},
         "why": why, "total": hours(total), "changes": changes, "plan": fill, "weekend": weekend,
         "hints": hints(w_events, days), "missing": missing}
  return res


def cmd_propose(args):
  st = status(read_json(args.grid))
  if st in LOCKED:
    print(f"LOCKED: the week is {st}; don't change it (and don't Withdraw unless Ian asks for that week)")
    sys.exit(3)
  res = propose(args)
  if args.json:
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return
  for m in res["missing"]:
    print(f"missing: {m}")
  mon = datetime.date.fromisoformat(res["monday"])
  sun = mon + datetime.timedelta(days=6)
  print(f"{res['week']} ({mon.day} {mon:%b} - {sun.day} {sun:%b}): {res['status'] or 'status not read'}, "
        + ("grid already matches this" if not res["changes"] else f"needs {len(res['changes'])} cell(s) changed"))
  print("\n| | " + " | ".join(WEEKDAYS) + " | Total |\n|---|" + "---|" * 6)
  for p, cells in res["table"].items():
    t = sum(minutes(v) for v in cells.values())
    print(f"| {p} | " + " | ".join(cells[n] for n in WEEKDAYS) + f" | {t // 60} h |")
  print(f"\ntotal {res['total']}")
  for n in WEEKDAYS:
    print(f"  {n}: {res['why'][n]}")
  if res["changes"]:
    print("\nchanges:")
    for c in res["changes"]:
      print(f"  {c['project']} {c['day']}: {c['from'] or 'empty'} -> {c['to'] or 'empty'}"
            + ("  (no row yet: + Add row)" if c["row_missing"] else ""))
  if res["weekend"]:
    print("weekend hours already in the grid (left alone): " + ", ".join(res["weekend"]))
  if res["hints"]:
    print("\nhints from W (not applied):")
    for h in res["hints"]:
      print(f"  {h}")
  print("\nplan: " + json.dumps(res["plan"], ensure_ascii=False))


def cmd_check(args):
  plan = read_json(args.plan)
  if isinstance(plan, dict) and "plan" in plan:
    plan = plan["plan"]
  grid = read_json(args.grid)
  rows = grid_rows(grid)
  diffs = []
  for p, days in plan.items():
    if p not in rows:
      if any(minutes(v) for v in days.values()):
        diffs.append(f"{p}: no row in the grid")
      continue
    for d, want in days.items():
      if rows[p].get(d, 0) != minutes(want):
        diffs.append(f"{p} {d}: expected {want or 'empty'}, grid has {hours(rows[p].get(d, 0)) or 'empty'}")
  expected = sum(minutes(v) for days in plan.values() for v in days.values()) + \
    sum(m for p, v in rows.items() if p not in plan for m in v.values()) + \
    sum(v[d] for p, v in rows.items() if p in plan for d in DAYS if d not in plan[p])
  have = sum(m for v in rows.values() for m in v.values())
  shown = minutes(((grid or {}).get("totals") or {}).get("week"))
  if have != expected:
    diffs.append(f"total: expected {hours(expected)}, the cells add up to {hours(have) or '0:00'}")
  if shown and shown != have:
    diffs.append(f"total: the grid's TOTAL shows {hours(shown)}, the cells add up to {hours(have)} (still saving?)")
  if diffs:
    print("DIFFERENT\n" + "\n".join("  " + d for d in diffs))
    sys.exit(1)
  print(f"OK: every planned cell matches; week total {hours(have) or '0:00'}; status {status(grid) or 'not read'}")


def cmd_submitted(args):
  st = status(read_json(args.grid))
  if st in LOCKED:
    print(f"{st}: submitted")
    return
  print(f"{st or 'no status read'}: not submitted")
  sys.exit(1)


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  p = sub.add_parser("week", help="which week to do")
  p.add_argument("--today", help="YYYY-MM-DD")
  p.add_argument("--last-grid", help="toggl-grid.js result for last week")
  p = sub.add_parser("propose", help="the proposed split and the cells to change")
  p.add_argument("--monday", required=True)
  p.add_argument("--grid", required=True, help="toggl-grid.js result for the week")
  p.add_argument("--prev", help="toggl-grid.js result for the week before")
  p.add_argument("--work", action="append", default=[])
  p.add_argument("--personal", action="append", default=[])
  p.add_argument("--holidays", help="UK holidays calendar list_events result")
  p.add_argument("--json", action="store_true")
  p = sub.add_parser("check", help="the filled grid against the plan")
  p.add_argument("--plan", required=True, help="the plan JSON (or propose --json output)")
  p.add_argument("--grid", required=True)
  p = sub.add_parser("submitted", help="is the week submitted?")
  p.add_argument("--grid", required=True)
  args = ap.parse_args()
  {"week": cmd_week, "propose": cmd_propose, "check": cmd_check, "submitted": cmd_submitted}[args.cmd](args)


if __name__ == "__main__":
  main()
