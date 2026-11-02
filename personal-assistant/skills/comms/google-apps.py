#!/usr/bin/env python3
"""Bookkeeping for /comms' Google apps check: which apps Ian has given his Google accounts to.

  google-apps.py record < page.txt       # the GOOGLE-APPS-BEGIN … END lines for one account
  google-apps.py keep work "HubSpot"     # Ian keeps it: don't ask again unless its access grows
  google-apps.py cut work "HubSpot"      # Ian removed it in Google: forget it, so a re-grant is new
  google-apps.py show [--account work]   # the last record, without changing anything

`record` saves the account's list and prints JSON:
  {"account", "apps": [{"name", "signIn", "linked", "access", "firstSeen", "new", "grew", "kept"}],
   "gone": [names],
   "counts": {"total", "withAccess", "toReview"}}
new: not in the last record (every app, the first time). grew: Ian kept it, but it can now
reach more than when he kept it. kept: kept and not grown. gone: in the last record and not
this one (removed in Google, or by the app). access is the lines Google's page gives for
what the app can do (empty for Sign in with Google only). Apps are sorted to review first: new, grew, then
unkept apps with account access (most products first), then unkept sign-in only, then kept.

State is in ~/.claude/personal-assistant/google-apps.json (PA_STATE).
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

STATE_FILE = os.path.join(pa.STATE, "google-apps.json")


def load():
  try:
    with open(STATE_FILE) as f:
      s = json.load(f)
  except (OSError, ValueError):
    s = {}
  return s


def save(s):
  os.makedirs(pa.STATE, exist_ok=True)
  tmp = STATE_FILE + ".tmp"
  with open(tmp, "w") as f:
    json.dump(s, f, indent=1, sort_keys=True)
  os.replace(tmp, STATE_FILE)


def account(name):
  if name in pa.MAILBOXES:
    return name
  for k, v in pa.MAILBOXES.items():
    if v == name:
      return k
  pa.die(f"unknown account {name!r}: use work or personal", 2)


def parse(text):
  """The lines extract-google-apps.js puts on the page (get_page_text may add more around them)."""
  lines = [l.strip() for l in text.splitlines()]
  try:
    b = next(i for i, l in enumerate(lines) if l.startswith("GOOGLE-APPS-BEGIN "))
    e = next(i for i, l in enumerate(lines) if i > b and l.startswith("GOOGLE-APPS-END "))
  except StopIteration:
    pa.die("no GOOGLE-APPS-BEGIN … GOOGLE-APPS-END block: run extract-google-apps.js, then get_page_text")
  try:
    apps = [json.loads(l) for l in lines[b + 1:e] if l]
  except ValueError as ex:
    pa.die(f"can't read an app line: {ex}")
  if str(len(apps)) != lines[e].split()[1]:
    pa.die(f"read {len(apps)} apps but the page says {lines[e].split()[1]}: the text was cut short?")
  return {"account": lines[b].split(None, 1)[1], "apps": apps}


def today():
  return time.strftime("%Y-%m-%d")


def report(acct, a, gone=()):
  apps = []
  for name, x in a.get("apps", {}).items():
    kept = a.get("kept", {}).get(name)
    grew = kept is not None and not set(x["access"]) <= set(kept["access"])
    apps.append({"name": name, "signIn": x.get("signIn", False), "linked": x.get("linked", False),
                 "access": x["access"], "firstSeen": x["firstSeen"],
                 "new": x.get("new", False), "grew": grew, "kept": kept is not None and not grew})

  def order(x):
    return (not x["new"], not x["grew"], x["kept"], not x["access"], -len(x["access"]), x["name"].lower())
  apps.sort(key=order)
  return {"account": acct, "lastRecord": a.get("lastRecord"), "apps": apps, "gone": sorted(gone),
          "counts": {"total": len(apps), "withAccess": sum(1 for x in apps if x["access"]),
                     "toReview": sum(1 for x in apps if not x["kept"])}}


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  sub.add_parser("record")
  for c in ("keep", "cut"):
    p = sub.add_parser(c)
    p.add_argument("account")
    p.add_argument("name")
  p = sub.add_parser("show")
  p.add_argument("--account", action="append")
  args = ap.parse_args()
  s = load()

  if args.cmd == "record":
    page = parse(sys.stdin.read())
    acct = account(page.get("account", ""))
    a = s.setdefault(acct, {})
    old = a.get("apps", {})
    first = not old and "lastRecord" not in a
    apps = {}
    for x in page.get("apps", []):
      name = x["name"].strip()
      prev = old.get(name)
      apps[name] = {"access": sorted(set(x.get("access", []))), "signIn": bool(x.get("signIn")),
                    "linked": bool(x.get("linked")),
                    "firstSeen": prev["firstSeen"] if prev else today(), "new": prev is None and not first}
    gone = [n for n in old if n not in apps]
    a["apps"] = apps
    # A kept app that's gone no longer needs its keep: if it comes back, it's a new grant.
    a["kept"] = {n: k for n, k in a.get("kept", {}).items() if n in apps}
    a["lastRecord"] = today()
    save(s)
    out = report(acct, a, gone)
    if first:
      out["firstRecord"] = True
    print(pa.as_json(out))
    return 0

  if args.cmd in ("keep", "cut"):
    acct = account(args.account)
    a = s.get(acct, {})
    if args.name not in a.get("apps", {}):
      pa.die(f"no app {args.name!r} in the last {acct} record")
    if args.cmd == "keep":
      a.setdefault("kept", {})[args.name] = {"access": a["apps"][args.name]["access"], "on": today()}
      print(f"kept {acct} {args.name}")
    else:
      a["apps"].pop(args.name)
      a.get("kept", {}).pop(args.name, None)
      a.setdefault("cut", []).append({"name": args.name, "on": today()})
      print(f"cut {acct} {args.name}")
    save(s)
    return 0

  for acct in [account(x) for x in (args.account or sorted(pa.MAILBOXES))]:
    print(pa.as_json(report(acct, s.get(acct, {}))))
  return 0


if __name__ == "__main__":
  sys.exit(main())
