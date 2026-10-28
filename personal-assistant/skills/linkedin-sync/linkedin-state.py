#!/usr/bin/env python3
"""State and bookkeeping for the linkedin-sync skill: the invite window, queue and log, and
the local evidence for new people's levels.

  linkedin-state.py window                    # NOW and LAST (step 4.1)
  linkedin-state.py budget [--per-day 40]     # invitations sent in the last 24 hours, and LEFT
  linkedin-state.py queue < viewers.txt       # step 4.4: who to invite, in order
  linkedin-state.py suggestions < page.txt    # step 5.3: suggested people to invite, in order
  linkedin-state.py log sent URL "Name"       # after each connect-profile.js result
  linkedin-state.py defer < rest.tsv          # everyone not yet tried, as deferred
  linkedin-state.py done NOW                  # write NOW to linkedin-sync-last
  linkedin-state.py evidence < created.txt    # step 7: meetings and people notes per person
  linkedin-state.py connections [OUT] < page.txt  # step 2.3: the connections JSON for the import
  linkedin-state.py export                    # step 6: newest data export, and what to do

State is in ~/.local/state/personal-assistant (PA_LINKEDIN_STATE overrides it):
linkedin-sync-last (UTC time of the last sync) and linkedin-invites.log (one line per viewer
tried: time, status, url, name; tab-separated).

`queue` reads the get_page_text output of the profile views page (or just its JSON lines),
checks the count against `VIEWERS-END <count>`, and prints `url<TAB>name` lines: viewers
held back as deferred by an earlier run first, then the new viewers, leaving out anyone the
log has as sent, pending or connected, at most --max (20) of them. The rest are printed after
a `# over the cap` line for `defer`.

`budget` counts the `sent` lines of the last 24 hours in the log and prints `SENT <n>` and
`LEFT <per-day - n>` (at least 0): about 40 invitations a day with Premium, 10 without.

`suggestions` reads the get_page_text output of the Grow page (SUGGESTIONS-BEGIN ...
SUGGESTIONS-END <count>), checks the count, and prints `url<TAB>name<TAB>mutual` lines in the
page's order (most mutual connections first), leaving out anyone the log has at all: a
suggestion is tried once, and never deferred.

`evidence` reads `gtd import-connections --auto` output (the `Created <file> | <name> | ...`
and `Pending ...` lines) or one name per line, and for each person lists meeting transcripts
of the last 30 days whose name or text has their full name, and other people files that
mention them. Calendar and mail are still the skill's to search. The suggested level is
`met` with a transcript, `in-touch` with a mention, otherwise `forgotten?` (until the calendar
and mail searches have been done).

`connections` reads the get_page_text output of the connections page after
extract-connections.js (GTD-SYNC-BEGIN ... GTD-SYNC-END <count>), checks the count, and writes
the JSON lines, as they are, to OUT (default $TMPDIR/linkedin-connections-<YYYYMMDD>.json) for
`gtd import-connections --auto`. It refuses without the GTD-SYNC-END line.

`export` finds the newest *LinkedInDataExport*.zip in ~/Downloads (PA_DOWNLOADS overrides it)
and prints `EXPORT <path> <age>d` (or `EXPORT none`), then `ACTION import` when it's less than
7 days old, `ACTION request` when there's none or it's more than 30 days old, else
`ACTION none`.
"""

import argparse
import datetime
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

STATE = os.path.expanduser(os.environ.get("PA_LINKEDIN_STATE", "~/.local/state/personal-assistant"))
LAST = os.path.join(STATE, "linkedin-sync-last")
LOG = os.path.join(STATE, "linkedin-invites.log")
DOWNLOADS = os.path.expanduser(os.environ.get("PA_DOWNLOADS", "~/Downloads"))
DONE = {"sent", "pending", "connected"}


def utc_now():
  return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_log():
  """url -> (latest status, name)."""
  latest = {}
  try:
    with open(LOG, encoding="utf-8") as f:
      for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 3:
          latest[parts[2]] = (parts[1], parts[3] if len(parts) > 3 else "")
  except OSError:
    pass
  return latest


def append_log(status, url, name):
  os.makedirs(STATE, exist_ok=True)
  with open(LOG, "a", encoding="utf-8") as f:
    f.write(f"{utc_now()}\t{status}\t{url}\t{' '.join(name.split())}\n")


def cmd_window(args):
  note = None
  try:
    last = open(LAST).read().strip()
  except OSError:
    last = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    note = "# no linkedin-sync-last (first run): LAST is a week ago"
  print(f"NOW {utc_now()}")
  print(f"LAST {last}")
  if note:
    print(note)


def read_page(text, end):
  """The JSON lines of a page, checked against its `<end> <count>` line."""
  rows, count = [], None
  for line in text.splitlines():
    line = line.strip()
    m = re.match(rf"{end} (\d+)", line)
    if m:
      count = int(m.group(1))
    if line.startswith("{"):
      try:
        rows.append(json.loads(line))
      except json.JSONDecodeError:
        pa.die(f"not JSON: {line[:80]}")
  if count is not None and count != len(rows):
    pa.die(f"{end} says {count} but there are {len(rows)} lines: read the page again")
  return rows


def cmd_budget(args):
  since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
  sent = 0
  try:
    with open(LOG, encoding="utf-8") as f:
      for line in f:
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1] == "sent":
          try:
            at = datetime.datetime.strptime(parts[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
          except ValueError:
            continue
          sent += at >= since
  except OSError:
    pass
  print(f"SENT {sent}")
  print(f"LEFT {max(0, args.per_day - sent)}")


def cmd_queue(args):
  viewers = read_page(sys.stdin.read(), "VIEWERS-END")
  log = read_log()
  queue, seen = [], set()
  for url, (status, name) in log.items():
    if status == "deferred":
      queue.append((url, name))
      seen.add(url)
  for v in viewers:
    url = v.get("url") or v.get("profileUrl")
    if not url or url in seen or log.get(url, ("",))[0] in DONE:
      continue
    seen.add(url)
    queue.append((url, v.get("name", "")))
  print(f"# {len(viewers)} viewer(s) on the page, {len(queue)} to try "
        f"({sum(1 for s, _ in log.values() if s == 'deferred')} deferred from before)")
  for i, (url, name) in enumerate(queue):
    if i == args.max:
      print("# over the cap: pass the lines below to `defer`")
    print(f"{url}\t{name}")


def cmd_suggestions(args):
  people = read_page(sys.stdin.read(), "SUGGESTIONS-END")
  log = read_log()
  queue, seen = [], set()
  for p in people:
    url = p.get("url")
    if not url or url in seen or url in log:
      continue
    seen.add(url)
    queue.append((url, p.get("name", ""), p.get("mutual", 0)))
  print(f"# {len(people)} suggestion(s) on the page, {len(queue)} not tried before")
  for url, name, mutual in queue:
    print(f"{url}\t{name}\t{mutual}")


def cmd_connections(args):
  text = sys.stdin.read()
  if not re.search(r"^\s*GTD-SYNC-END \d+", text, re.M):
    pa.die("no `GTD-SYNC-END <count>` line: pass the whole get_page_text output, after extract-connections.js")
  read_page(text, "GTD-SYNC-END")
  lines = [l.strip() for l in text.splitlines() if l.strip().startswith("{")]
  out = args.out or os.path.join(os.environ.get("TMPDIR", "/tmp"),
                                 f"linkedin-connections-{datetime.date.today():%Y%m%d}.json")
  with open(out, "w", encoding="utf-8") as f:
    f.writelines(l + "\n" for l in lines)
  print(f"{len(lines)} connection(s) -> {out}")


def cmd_export(args):
  zips = [os.path.join(DOWNLOADS, f) for f in os.listdir(DOWNLOADS)
          if "LinkedInDataExport" in f and f.endswith(".zip")] if os.path.isdir(DOWNLOADS) else []
  if not zips:
    print("EXPORT none")
    print("ACTION request")
    return
  newest = max(zips, key=os.path.getmtime)
  age = int((time.time() - os.path.getmtime(newest)) // 86400)
  print(f"EXPORT {newest} {age}d")
  print("ACTION " + ("import" if age < 7 else "request" if age > 30 else "none"))


def cmd_log(args):
  append_log(args.status, args.url, args.name)
  print(f"logged {args.status} {args.url}")


def cmd_defer(args):
  n = 0
  for line in sys.stdin:
    line = line.rstrip("\n")
    if not line or line.startswith("#"):
      continue
    url, _, name = line.partition("\t")
    append_log("deferred", url, name)
    n += 1
  print(f"deferred {n}")


def cmd_done(args):
  os.makedirs(STATE, exist_ok=True)
  with open(LAST, "w") as f:
    f.write(args.now + "\n")
  print(f"linkedin-sync-last = {args.now}")


def people_in(text):
  """(name, own file or None) from import output, or one name per line."""
  out, import_output = [], re.search(r"^\s*(Created \S+\.md|Pending) .*\|", text, re.M)
  for line in text.splitlines():
    line = line.strip()
    m = re.match(r"Created (\S+\.md) \| ([^|]+)", line)
    if m:
      out.append((m.group(2).strip(), os.path.basename(m.group(1))))
      continue
    m = re.match(r"Pending ([^|]+)\|", line)
    if m:
      out.append((m.group(1).strip(), None))
      continue
    if line and not import_output and not line.startswith("#"):
      out.append((line, None))
  return out


def cmd_evidence(args):
  meetings_dir = os.path.join(pa.GTD, "meetings")
  people_dir = os.path.join(pa.GTD, "people")
  cutoff = time.time() - args.days * 86400
  transcripts = []
  for f in os.listdir(meetings_dir) if os.path.isdir(meetings_dir) else []:
    p = os.path.join(meetings_dir, f)
    if f.endswith(".txt") and os.path.getmtime(p) >= cutoff:
      with open(p, encoding="utf-8", errors="replace") as fh:
        transcripts.append((f, fh.read().lower()))
  notes = []
  for f in os.listdir(people_dir) if os.path.isdir(people_dir) else []:
    if f.endswith(".md"):
      with open(os.path.join(people_dir, f), encoding="utf-8", errors="replace") as fh:
        notes.append((f, fh.read().lower()))
  for name, own in people_in(sys.stdin.read()):
    key, slug = name.lower(), name.replace(" ", "_").lower()
    met = [f for f, t in transcripts if key in t or slug in f.lower()]
    own = own or f"{name.replace(' ', '_')}.md"
    mentioned = [f for f, t in notes if f != own and key in t]
    level = "met" if met else "in-touch" if mentioned else "forgotten?"
    ev = [f"meetings/{f}" for f in met[:3]] + [f"people/{f}" for f in mentioned[:3]]
    print(f"{name}\t{level}\t{'; '.join(ev) or '-'}")


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  sub.add_parser("window")
  p = sub.add_parser("budget")
  p.add_argument("--per-day", type=int, default=40)
  p = sub.add_parser("queue")
  p.add_argument("--max", type=int, default=20)
  p = sub.add_parser("log")
  p.add_argument("status", choices=["sent", "connected", "pending", "no-connect", "needs-email",
                                    "limit", "unexpected", "error", "deferred"])
  p.add_argument("url")
  p.add_argument("name", nargs="?", default="")
  sub.add_parser("suggestions")
  p = sub.add_parser("connections")
  p.add_argument("out", nargs="?", help="default $TMPDIR/linkedin-connections-<YYYYMMDD>.json")
  sub.add_parser("export")
  sub.add_parser("defer")
  p = sub.add_parser("done")
  p.add_argument("now")
  p = sub.add_parser("evidence")
  p.add_argument("--days", type=int, default=30)
  args = ap.parse_args()
  {"window": cmd_window, "budget": cmd_budget, "queue": cmd_queue, "suggestions": cmd_suggestions, "log": cmd_log, "defer": cmd_defer,
   "done": cmd_done, "evidence": cmd_evidence, "connections": cmd_connections, "export": cmd_export}[args.cmd](args)


if __name__ == "__main__":
  main()
