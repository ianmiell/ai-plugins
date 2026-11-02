#!/usr/bin/env python3
"""Who Ian's Google Drive files and calendars are shared with, for /comms to review daily.

  google-shares.py list                   # both accounts: shares not yet kept, grouped by person
  google-shares.py list --account personal --all   # one account, including the kept ones
  google-shares.py apply [--dry-run] < plan        # cut or keep shares Ian chose

`list` scans My Drive on each account with gog's read-only sharing audit (about two minutes
an account, in parallel) and the sharing rules of the calendars Ian owns. It prints JSON:
  {"people": [{"who", "kind", "new", "shares": [...]}], "kept": N, "errors": [...]}
one entry per grantee (a person, a group, a domain, or "anyone with the link"), newest first.
Each share has account, fileId, permissionId (or calendarId and ruleId), name, path, role,
url, firstSeen and new (first seen in this scan). Left out: Ian's own addresses; on the
work account, shares inside container-solutions.com; on the work calendar, the company's
default free/busy rule; and anything Ian kept, unless --all.

`apply` reads one line per action:
  cut <account> <fileId> <permissionId>   # remove that Drive share (gog drive unshare)
  keep <account> <fileId> <permissionId>  # stop asking about this share
  keep-person <who>                       # stop asking about anyone's shares with <who>
                                          # (an address, domain:<d>, or anyone)
<account> is work or personal; calendar shares use calendar:<calendarId> for <fileId> and
the rule id for <permissionId>. gog can't remove calendar shares, so a calendar cut is
refused: Ian removes it in Google Calendar's settings (list gives the link).
Exits 1 if any account or action failed (the rest still run).

State (first seen, kept) is in ~/.claude/personal-assistant/google-shares.json (PA_STATE).
"""

import argparse
import base64
import concurrent.futures
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

STATE_FILE = os.path.join(pa.STATE, "google-shares.json")
WORK_DOMAIN = "container-solutions.com"
# gog's audit only reports shares outside the account's domain, and for the personal account
# that domain is gmail.com, which would hide every friend with a Gmail address. A domain
# nobody has makes every share external; the work account keeps its own so colleagues
# aren't listed.
INTERNAL_DOMAIN = {"work": WORK_DOMAIN, "personal": "invalid.invalid"}
ANYONE = "anyone"


def load_state():
  try:
    with open(STATE_FILE) as f:
      s = json.load(f)
  except (OSError, ValueError):
    s = {}
  s.setdefault("seen", {})
  s.setdefault("kept", {})
  s.setdefault("keptPeople", {})
  return s


def save_state(s):
  os.makedirs(pa.STATE, exist_ok=True)
  tmp = STATE_FILE + ".tmp"
  with open(tmp, "w") as f:
    json.dump(s, f, indent=1, sort_keys=True)
  os.replace(tmp, STATE_FILE)


def key(account, file_id, perm_id):
  return f"{account}|{file_id}|{perm_id}"


def grantee(p):
  """(who, kind) for a Drive permission or calendar rule scope."""
  kind = p.get("permissionType") or p.get("type")
  if kind == "anyone" or kind == "default":
    return ANYONE, "anyone with the link" if "permissionType" in p else "public calendar"
  if kind == "domain":
    return f"domain:{p.get('domain') or p.get('value')}", "domain"
  return (p.get("email") or p.get("value") or "?").lower(), kind


def drive_shares(mb):
  found = pa.gog(mb, "--readonly", "drive", "audit", "sharing", "--max", "0", "--depth", "0",
                 "--internal-domain", INTERNAL_DOMAIN[mb]) or []
  out = []
  for f in found:
    who, kind = grantee(f)
    if who in pa.IAN_ADDRESSES:
      continue
    out.append({"account": mb, "who": who, "kind": kind, "fileId": f["fileId"],
                "permissionId": f["permissionId"], "name": f.get("fileName", ""),
                "path": f.get("path", ""), "role": f.get("role", ""),
                "url": f"https://drive.google.com/open?id={f['fileId']}&authuser={pa.mailbox_address(mb)}"})
  return out


def calendar_settings_url(cal_id, mb):
  b = base64.urlsafe_b64encode(cal_id.encode()).decode().rstrip("=")
  return f"https://calendar.google.com/calendar/r/settings/calendar/{b}?authuser={pa.mailbox_address(mb)}"


def calendar_shares(mb):
  out = []
  for cal in pa.gog(mb, "--readonly", "calendar", "calendars") or []:
    cid = cal.get("id", "")
    # Only calendars this account itself owns: the personal account also owns the work
    # calendar through a share, and that one is the work account's to report.
    if cal.get("accessRole") != "owner" or not (cid == pa.mailbox_address(mb)
                                                or cid.endswith("@group.calendar.google.com")):
      continue
    for r in pa.gog(mb, "--readonly", "calendar", "acl", cid) or []:
      scope = r.get("scope", {})
      who, kind = grantee(scope)
      if who in pa.IAN_ADDRESSES or (mb == "work" and who == f"domain:{WORK_DOMAIN}"):
        continue
      out.append({"account": mb, "who": who, "kind": kind, "fileId": f"calendar:{cid}",
                  "permissionId": r.get("id", ""), "name": f"Calendar: {cal.get('summary', cid)}",
                  "path": "", "role": r.get("role", ""), "url": calendar_settings_url(cid, mb)})
  return out


def scan(mb):
  return drive_shares(mb) + calendar_shares(mb)


def cmd_list(args):
  state = load_state()
  now = int(time.time())
  shares, errors = [], []
  with concurrent.futures.ThreadPoolExecutor(len(args.account)) as ex:
    futs = {ex.submit(scan, mb): mb for mb in args.account}
    for fut in concurrent.futures.as_completed(futs):
      try:
        shares += fut.result()
      except pa.GogError as e:
        errors.append(f"{futs[fut]}: {e}")
  people, kept, seen_keys = {}, 0, set()
  for s in shares:
    k = key(s["account"], s["fileId"], s["permissionId"])
    if k in seen_keys:
      continue
    seen_keys.add(k)
    s["new"] = k not in state["seen"]
    s["firstSeen"] = time.strftime("%Y-%m-%d", time.localtime(state["seen"].setdefault(k, now)))
    if not args.all and (k in state["kept"] or s["who"] in state["keptPeople"]):
      kept += 1
      continue
    kind, who = s.pop("kind"), s.pop("who")
    p = people.setdefault(who, {"who": who, "kind": kind, "new": False, "shares": []})
    p["new"] |= s["new"]
    p["shares"].append(s)
  # Forget shares that no longer exist, so one shared again later counts as new. Only for
  # accounts that scanned cleanly.
  failed = {e.split(":")[0] for e in errors}
  scanned = tuple(f"{mb}|" for mb in args.account if mb not in failed)
  state["seen"] = {k: v for k, v in state["seen"].items() if k in seen_keys or not k.startswith(scanned)}
  state["kept"] = {k: v for k, v in state["kept"].items() if k in seen_keys or not k.startswith(scanned)}
  state["lastScan"] = now
  save_state(state)
  order = sorted(people.values(), key=lambda p: (not p["new"], p["who"] != ANYONE, p["who"]))
  for p in order:
    p["shares"].sort(key=lambda s: (not s["new"], s["account"], s["path"] or s["name"]))
  print(pa.as_json({"people": order, "kept": kept, "errors": errors}))
  return 1 if errors else 0


def cmd_apply(args):
  state = load_state()
  now = int(time.time())
  bad = 0
  for line in sys.stdin:
    parts = line.split()
    if not parts or parts[0].startswith("#"):
      continue
    try:
      if parts[0] == "keep-person" and len(parts) == 2:
        who = parts[1].lower()
        print(f"{'would keep' if args.dry_run else 'kept'} everything shared with {who}")
        if not args.dry_run:
          state["keptPeople"][who] = now
        continue
      if parts[0] not in ("cut", "keep") or len(parts) != 4:
        raise ValueError(f"can't read: {line.strip()}")
      act, mb, fid, pid = parts
      if mb not in pa.MAILBOXES:
        raise ValueError(f"unknown account {mb!r}: use work or personal")
      if act == "keep":
        print(f"{'would keep' if args.dry_run else 'kept'} {mb} {fid} {pid}")
        if not args.dry_run:
          state["kept"][key(mb, fid, pid)] = now
        continue
      if fid.startswith("calendar:"):
        raise ValueError(f"gog can't remove calendar shares: remove {pid} from {fid[9:]} in "
                         f"Google Calendar settings ({calendar_settings_url(fid[9:], mb)})")
      pa.gog(mb, "--force", "drive", "unshare", fid, pid, dry_run=args.dry_run)
      if not args.dry_run:
        print(f"cut {mb} {fid} {pid}")
        state["seen"].pop(key(mb, fid, pid), None)
    except (ValueError, pa.GogError) as e:
      print(f"FAILED: {e}", file=sys.stderr)
      bad += 1
  if not args.dry_run:
    save_state(state)
  return 1 if bad else 0


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  p = sub.add_parser("list")
  p.add_argument("--account", action="append", choices=sorted(pa.MAILBOXES))
  p.add_argument("--all", action="store_true", help="include shares Ian kept")
  p = sub.add_parser("apply")
  p.add_argument("--dry-run", action="store_true")
  args = ap.parse_args()
  if args.cmd == "list":
    args.account = args.account or sorted(pa.MAILBOXES)
    return cmd_list(args)
  return cmd_apply(args)


if __name__ == "__main__":
  sys.exit(main())
