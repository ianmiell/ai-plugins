#!/usr/bin/env python3
"""State and bookkeeping for the linkedin-sync skill: the invite window, queue and log, and
the local evidence for new people's levels.

  linkedin-state.py window                    # NOW and LAST (step 4.1)
  linkedin-state.py queue < viewers.txt       # step 4.4: who to invite, in order
  linkedin-state.py log sent URL "Name"       # after each connect-profile.js result
  linkedin-state.py defer < rest.tsv          # everyone not yet tried, as deferred
  linkedin-state.py done NOW                  # write NOW to linkedin-sync-last
  linkedin-state.py evidence < created.txt    # step 6: meetings and people notes per person

State is in ~/.local/state/personal-assistant (PA_LINKEDIN_STATE overrides it):
linkedin-sync-last (UTC time of the last sync) and linkedin-invites.log (one line per viewer
tried: time, status, url, name; tab-separated).

`queue` reads the get_page_text output of the profile views page (or just its JSON lines),
checks the count against `VIEWERS-END <count>`, and prints `url<TAB>name` lines: viewers
held back as deferred by an earlier run first, then the new viewers, leaving out anyone the
log has as sent, pending or connected, at most --max (20) of them. The rest are printed after
a `# over the cap` line for `defer`.

`evidence` reads `gtd import-connections --auto` output (the `Created <file> | <name> | ...`
and `Pending ...` lines) or one name per line, and for each person lists meeting transcripts
of the last 30 days whose name or text has their full name, and other people files that
mention them. Calendar and mail are still the skill's to search. The suggested level is
`met` with a transcript, `in-touch` with a mention, otherwise `forgotten?` (until the calendar
and mail searches have been done).
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


def cmd_queue(args):
  text = sys.stdin.read()
  viewers, count = [], None
  for line in text.splitlines():
    line = line.strip()
    m = re.match(r"VIEWERS-END (\d+)", line)
    if m:
      count = int(m.group(1))
    if line.startswith("{"):
      try:
        viewers.append(json.loads(line))
      except json.JSONDecodeError:
        pa.die(f"not JSON: {line[:80]}")
  if count is not None and count != len(viewers):
    pa.die(f"VIEWERS-END says {count} but there are {len(viewers)} lines: read the page again")
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
  p = sub.add_parser("queue")
  p.add_argument("--max", type=int, default=20)
  p = sub.add_parser("log")
  p.add_argument("status", choices=["sent", "connected", "pending", "no-connect", "needs-email",
                                    "limit", "unexpected", "error", "deferred"])
  p.add_argument("url")
  p.add_argument("name", nargs="?", default="")
  sub.add_parser("defer")
  p = sub.add_parser("done")
  p.add_argument("now")
  p = sub.add_parser("evidence")
  p.add_argument("--days", type=int, default=30)
  args = ap.parse_args()
  {"window": cmd_window, "queue": cmd_queue, "log": cmd_log, "defer": cmd_defer,
   "done": cmd_done, "evidence": cmd_evidence}[args.cmd](args)


if __name__ == "__main__":
  main()
