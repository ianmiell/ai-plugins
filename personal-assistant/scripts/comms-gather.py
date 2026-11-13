#!/usr/bin/env python3
"""The scripted half of a /comms run in one zsh-safe call: scope, checks, mail, tidy, WhatsApp.

  comms-gather.py scope "2d work"         # what a /comms argument covers, and each window
  comms-gather.py run "morning"           # scope, then every scripted section, side by side
  comms-gather.py run "" --tidy-dry-run   # the GTD-<N> tidy only says what it would do

`scope` turns the /comms argument into the channels and windows the run covers, as the comms
skill's Scope step says:
  (nothing), morning     every channel; Slack and WhatsApp since their last runs (capped at
                         7 days, the last 24 hours with no record); mail `in:inbox`
  work / personal        W✉ S LI 📅W 🔑W / P✉ WA 📅P 🔑P
  mail, work-mail, personal-mail, slack, whatsapp, linkedin, invites, apps
                         only those (with work or personal: only that side of them)
  today, yesterday, 2d, 6h, 1w, since monday, since 2026-11-02, last 3 days
                         that window for Slack, WhatsApp and mail (`newer_than:2d` or
                         `after:2026/11/09`); invites stay at the next 4 weeks
  unread                 mail `is:unread`, WhatsApp --unread; Slack keeps its window
WhatsApp, LinkedIn and Google apps are MacBook Pro only: elsewhere they're dropped and listed
as off on this machine. On the MacBook Pro the work mailbox is the Gmail connector's, not
gog's. Words it doesn't know are listed as not understood, never guessed. The scope is saved
in PA_STATE/comms-scope.json for comms-items.py and slack-merge.py.

`run` prints the scope, then runs, at the same time and each with its own timeout:
  pa-env       pa-env.py check (machine, gog mailbox checks, WhatsApp, windows)
  mail         mail-gather.py list for the gog mailboxes in scope (it saves the list for
               comms-items.py in PA_STATE/mail-gather-last.json)
  tidy         gtd-label-tidy.py for the same mailbox(es) (rules/close-task-tidies-mail.md)
  whatsapp     whatsapp.py chats with the window (MacBook Pro only)
Each section's output follows a `▶ name` header and ends with a `◀ name: ok` or
`◀ name: FAILED` line; one failing doesn't stop the others. The last line names the sections
that failed and the connector steps still to do. It exits 0 even when a section failed (the
summary says which), so a failure shows as that section's, not the whole run's; 2 on bad usage.
"""

import argparse
import concurrent.futures
import datetime
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = 7 * 86400
DEFAULT = 86400
INVITE_DAYS = 28

# Every channel, in the order the comms skill lists them, with its tag.
CHANNELS = [
  ("work-mail", "W✉"), ("personal-mail", "P✉"), ("slack", "S"), ("whatsapp", "WA"),
  ("linkedin", "LI"), ("invites-work", "📅 W"), ("invites-personal", "📅 P"),
  ("apps-work", "🔑 W"), ("apps-personal", "🔑 P"),
]
TAG = dict(CHANNELS)
SIDES = {
  "work": {"work-mail", "slack", "linkedin", "invites-work", "apps-work"},
  "personal": {"personal-mail", "whatsapp", "invites-personal", "apps-personal"},
}
NAMES = {
  "mail": {"work-mail", "personal-mail"}, "email": {"work-mail", "personal-mail"},
  "work-mail": {"work-mail"}, "personal-mail": {"personal-mail"},
  "slack": {"slack"}, "whatsapp": {"whatsapp"}, "wa": {"whatsapp"},
  "linkedin": {"linkedin"}, "li": {"linkedin"},
  "invites": {"invites-work", "invites-personal"}, "calendar": {"invites-work", "invites-personal"},
  "apps": {"apps-work", "apps-personal"},
}
MBP_ONLY = {"whatsapp", "linkedin", "apps-work", "apps-personal"}
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def scope_file():
  return os.path.join(pa.STATE, "comms-scope.json")


def last_run(channel, now):
  """Start of a channel's window from its last-run file, as pa-env.py check works it out."""
  try:
    with open(os.path.join(pa.STATE, f"{channel}-last-run")) as f:
      last, source = int(f.read().strip()), "last run"
  except (OSError, ValueError):
    last, source = now - DEFAULT, "no record: last 24h"
  if now - last > CAP:
    last, source = now - CAP, "capped at 7 days"
  return last, source


def parse_time(words, now):
  """(start epoch, mail query term, label, words used) for a time in the argument, or None."""
  today = datetime.datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)
  text = " ".join(words)
  m = re.search(r"\b(?:last\s+)?(\d+)\s*(d|h|w|m|days?|hours?|weeks?|mins?|minutes?)\b", text)
  if m:
    n, unit = int(m.group(1)), m.group(2)[0]
    secs = n * {"m": 60, "d": 86400, "h": 3600, "w": 7 * 86400}[unit]
    start = now - secs
    query = f"newer_than:{n}d" if unit == "d" else (f"newer_than:{n * 7}d" if unit == "w" else None)
    return start, query, f"last {m.group(1)}{unit}", m.group(0).split()
  m = re.search(r"\bsince\s+(\S+)", text)
  if m:
    w = m.group(1)
    day = None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", w):
      day = datetime.datetime.strptime(w, "%Y-%m-%d")
    else:
      name = next((d for d in DAYS if d.startswith(w) and len(w) >= 3), None)
      if name:
        back = (today.weekday() - DAYS.index(name)) % 7
        day = today - datetime.timedelta(days=back)
      elif w in ("yesterday", "today"):
        day = today - datetime.timedelta(days=1 if w == "yesterday" else 0)
    if day:
      return int(day.timestamp()), None, f"since {day:%a %d %b}", ["since", w]
  for w, back in (("today", 0), ("yesterday", 1)):
    if w in words:
      day = today - datetime.timedelta(days=back)
      return int(day.timestamp()), None, w, [w]
  return None


def scope(arg, now=None, machine=None):
  now = int(now or time.time())
  machine = machine or pa.machine()
  words = [w for w in re.split(r"[\s,]+", (arg or "").lower().strip()) if w]
  used, sides, named = set(), set(), set()
  morning = "morning" in words
  unread = "unread" in words
  used |= {"morning", "unread"} & set(words)
  t = parse_time(words, now)
  if t:
    used |= set(t[3])
  for w in words:
    if w in SIDES:
      sides.add(w)
      used.add(w)
    elif w in NAMES:
      named |= NAMES[w]
      used.add(w)
  channels = set(TAG)
  if sides:
    channels = set().union(*(SIDES[s] for s in sides))
  if named:
    channels = (channels & named) if sides else named
  off = sorted(channels & MBP_ONLY, key=list(TAG).index) if machine != "macbook-pro" else []
  channels -= set(off)
  order = [c for c, _ in CHANNELS if c in channels]

  mail = {}
  for box in ("work", "personal"):
    if f"{box}-mail" in channels:
      q = "in:inbox"
      if t:
        q += " " + (t[1] or "after:" + datetime.datetime.fromtimestamp(t[0]).strftime("%Y/%m/%d"))
      if unread:
        q += " is:unread"
      via = "connector" if (box == "work" and machine == "macbook-pro") else "gog"
      mail[box] = {"query": q, "via": via}
  windows = {}
  for ch in ("slack", "whatsapp"):
    if ch not in channels:
      continue
    if t:
      start, source = t[0], t[2]
    else:
      start, source = last_run(ch, now)
    since = datetime.datetime.fromtimestamp(start)
    w = {"epoch": start, "since": since.strftime("%a %d %b %H:%M"), "source": source}
    if ch == "slack":
      w["after"] = (since.date() - datetime.timedelta(days=1)).isoformat()
    else:
      w["whatsapp_since"] = f"{max(1, (now - start + 59) // 60)}m"
      w["unread"] = unread
    windows[ch] = w
  invites = None
  if channels & {"invites-work", "invites-personal"}:
    d0 = datetime.date.fromtimestamp(now)
    invites = {"from": d0.isoformat(), "to": (d0 + datetime.timedelta(days=INVITE_DAYS)).isoformat()}
  return {
    "argument": arg or "", "made": now, "machine": machine, "morning": morning, "unread": unread,
    "channels": order, "tags": [TAG[c] for c in order], "off": off, "mail": mail,
    "windows": windows, "invites": invites,
    "not_understood": [w for w in words if w not in used],
  }


def describe(s):
  lines = [f"scope: {s['argument'] or '(everything)'}" + (" (morning run: notify Ian when the list is ready)"
                                                        if s["morning"] else ""),
           f"machine: {s['machine']}",
           "channels: " + (" · ".join(s["tags"]) or "none")]
  if s["off"]:
    lines.append("off on this machine (MacBook Pro only, not a failure): " + " · ".join(TAG[c] for c in s["off"]))
  for box, m in s["mail"].items():
    lines.append(f"mail {box}: `{m['query']}` via {m['via']}")
  w = s["windows"].get("slack")
  if w:
    lines.append(f"slack: since {w['since']} ({w['source']}); search after:{w['after']}, "
                 f"then slack-merge.py --since {w['epoch']}")
  w = s["windows"].get("whatsapp")
  if w:
    lines.append(f"whatsapp: since {w['since']} ({w['source']}); whatsapp.py chats --since {w['whatsapp_since']}"
                 + (" --unread" if w["unread"] else ""))
  if s["invites"]:
    lines.append(f"invites: {s['invites']['from']} to {s['invites']['to']}")
  if s["not_understood"]:
    lines.append("not understood (ask Ian): " + " ".join(s["not_understood"]))
  return lines


def save(s):
  os.makedirs(pa.STATE, exist_ok=True)
  with open(scope_file(), "w") as f:
    json.dump(s, f, ensure_ascii=False, indent=1)


def run_section(name, cmd, timeout):
  t0 = time.time()
  try:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    out = (p.stdout or "") + (("\n" + p.stderr) if p.stderr.strip() else "")
    ok, why = p.returncode == 0, f"exit {p.returncode}"
    if ok and "UNREACHABLE" in out:  # mail-gather.py reports a mailbox it can't reach and goes on
      ok, why = False, "a mailbox was unreachable"
  except subprocess.TimeoutExpired as e:
    out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    ok, why = False, f"timed out after {timeout}s"
  except OSError as e:
    out, ok, why = "", False, str(e)
  return name, out.rstrip(), ok, why, time.time() - t0


def sections(s, args):
  py = sys.executable
  gog_boxes = [b for b, m in s["mail"].items() if m["via"] == "gog"]
  out = []
  only = ["--only", "windows"]
  if gog_boxes:
    only += ["--only", "mail"]
    for b in gog_boxes:
      only += ["--mailbox", b]
  if "whatsapp" in s["channels"]:
    only += ["--only", "whatsapp"]
  out.append(("pa-env", [py, os.path.join(HERE, "pa-env.py"), "check", *only]))
  if gog_boxes:
    q = s["mail"][gog_boxes[0]]["query"]
    cmd = [py, os.path.join(HERE, "mail-gather.py"), "list", "--query", q, "--max", str(args.max)]
    for b in gog_boxes:
      cmd += ["--mailbox", b]
    out.append(("mail", cmd))
    cmd = [py, os.path.join(HERE, "gtd-label-tidy.py")] + (["--dry-run"] if args.tidy_dry_run else [])
    for b in gog_boxes:
      cmd += ["--mailbox", b]
    out.append(("tidy", cmd))
  w = s["windows"].get("whatsapp")
  if w and s["machine"] == "macbook-pro":
    cmd = [py, os.path.join(HERE, "whatsapp.py"), "chats", "--since", w["whatsapp_since"]]
    if w["unread"]:
      cmd.append("--unread")
    out.append(("whatsapp", cmd))
  return out


def still_to_do(s):
  todo = []
  if any(m["via"] == "connector" for m in s["mail"].values()):
    todo.append("work mail with the Gmail connector (search_threads, sent-mail check, write no-op)")
  if "slack" in s["channels"]:
    w = s["windows"]["slack"]
    todo.append(f"Slack: the three searches after:{w['after']} (response_format detailed), "
                f"then slack-merge.py --since {w['epoch']}")
  if s["invites"]:
    todo.append(f"pending invites: list_events {s['invites']['from']} to {s['invites']['to']}")
  if "linkedin" in s["channels"]:
    todo.append("LinkedIn in Chrome")
  if {"apps-work", "apps-personal"} & set(s["channels"]):
    todo.append("Google apps in Chrome")
  return todo


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  p = sub.add_parser("scope", help="channels and windows for a /comms argument")
  p.add_argument("arg", nargs="*", help='the /comms argument, e.g. "2d work"')
  p.add_argument("--json", action="store_true")
  p = sub.add_parser("run", help="scope, then the scripted gather sections")
  p.add_argument("arg", nargs="*")
  p.add_argument("--timeout", type=int, default=300, help="seconds per section")
  p.add_argument("--max", type=int, default=25, help="mail threads per mailbox")
  p.add_argument("--tidy-dry-run", action="store_true", help="the GTD-<N> tidy only reports")
  args = ap.parse_args()

  s = scope(" ".join(args.arg))
  save(s)
  if args.cmd == "scope":
    print(pa.as_json(s) if args.json else "\n".join(describe(s)))
    return

  print("▶ scope")
  print("\n".join(describe(s)))
  print("◀ scope: ok")
  todo = sections(s, args)
  with concurrent.futures.ThreadPoolExecutor(max_workers=len(todo)) as ex:
    results = list(ex.map(lambda nc: run_section(nc[0], nc[1], args.timeout), todo))
  failed = []
  for name, out, ok, why, secs in results:
    print(f"\n▶ {name}")
    if out:
      print(out)
    print(f"◀ {name}: {'ok' if ok else 'FAILED (' + why + ')'} in {secs:.0f}s")
    if not ok:
      failed.append(name)
  print()
  names = ", ".join(n for n, *_ in results)
  print(f"comms-gather: ran {names}; " + (f"FAILED: {', '.join(failed)} (see each section above; the "
                                            f"others are fine)" if failed else "all ok"))
  rest = still_to_do(s)
  if rest:
    print("still to do with connectors: " + "; ".join(rest))


if __name__ == "__main__":
  main()
