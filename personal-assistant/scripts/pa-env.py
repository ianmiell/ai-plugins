#!/usr/bin/env python3
"""Start-of-run checks and time windows for the personal-assistant skills, in one call.

  pa-env.py check                 # machine, gog mailboxes, WhatsApp, Slack/WhatsApp windows
  pa-env.py check --only mail     # or windows, whatsapp; repeatable
  pa-env.py mark slack whatsapp   # after Ian has seen the list: record this run

`check` prints:
  machine     macbook-pro or other (the mail skill's "Which machine")
  mail        for each mailbox gog serves here (personal always; work off the MacBook Pro):
              the sent-mail account check and the write no-op (removing STARRED from an
              unstarred thread). On the MacBook Pro the work mailbox's connector checks
              are still the skill's to do.
  whatsapp    MacBook Pro only: whether whatsapp.py can read the app's database
  windows     Slack and WhatsApp: since the last run (~/.claude/personal-assistant/
              <channel>-last-run), the last 24 hours if there's none, capped at 7 days;
              with the Slack `after:` date (Slack's after: is exclusive, so it's the day
              before) and the whatsapp.py `--since` value
Exits 1 if any check failed (the rest still run).
"""

import argparse
import datetime
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CHANNELS = ("slack", "whatsapp")
CAP = 7 * 86400
DEFAULT = 86400


def window(channel, now):
  path = os.path.join(pa.STATE, f"{channel}-last-run")
  try:
    with open(path) as f:
      last = int(f.read().strip())
    source = "last run"
  except (OSError, ValueError):
    last, source = now - DEFAULT, "no record: last 24h"
  if now - last > CAP:
    last, source = now - CAP, "capped at 7 days"
  start = datetime.datetime.fromtimestamp(last)
  return {"channel": channel, "since": start, "epoch": last, "source": source,
          "slack_after": (start.date() - datetime.timedelta(days=1)).isoformat(),
          "whatsapp_since": f"{max(1, (now - last + 59) // 60)}m"}


def check_mailbox(mb):
  addr = pa.mailbox_address(mb)
  res = {"mailbox": mb, "address": addr}
  try:
    sent = pa.search(mb, "in:sent from:me", 1)
    if not sent:
      res["account"] = "no sent mail found"
    else:
      data = pa.gog(mb, "gmail", "thread", "get", sent[0]["id"])
      msgs = data.get("thread", data).get("messages", [])
      ok = any("SENT" in m.get("labelIds", []) and addr in pa.addresses(pa.headers(m).get("from"))
               for m in msgs)
      res["account"] = "ok" if ok else f"thread {sent[0]['id']} has no SENT message from {addr}"
  except pa.GogError as e:
    res["account"] = f"error: {e}"
    if "invalid_grant" in str(e) or "token" in str(e).lower():
      res["fix"] = f"! gog auth add {addr} --services gmail --force-consent"
    return res
  try:
    unstarred = pa.search(mb, "-is:starred", 1)
    if unstarred:
      pa.gog(mb, "gmail", "thread", "modify", unstarred[0]["id"], "--remove", "STARRED")
      res["write"] = "ok"
    else:
      res["write"] = "no unstarred thread to test on"
  except pa.GogError as e:
    res["write"] = f"error: {e}"
  return res


def check_whatsapp():
  p = subprocess.run([sys.executable, os.path.join(HERE, "whatsapp.py"), "chats", "--limit", "1"],
                     capture_output=True, text=True, timeout=60)
  return "ok" if p.returncode == 0 else f"error: {(p.stderr or p.stdout).strip()}"


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  p = sub.add_parser("check")
  p.add_argument("--only", action="append", choices=["mail", "whatsapp", "windows"])
  p.add_argument("--json", action="store_true")
  p = sub.add_parser("mark")
  p.add_argument("channels", nargs="+", choices=CHANNELS)
  args = ap.parse_args()

  now = int(time.time())
  if args.cmd == "mark":
    os.makedirs(pa.STATE, exist_ok=True)
    for c in args.channels:
      with open(os.path.join(pa.STATE, f"{c}-last-run"), "w") as f:
        f.write(f"{now}\n")
      print(f"{c}-last-run = {now} ({datetime.datetime.fromtimestamp(now):%a %d %b %H:%M})")
    return

  only = set(args.only or ["mail", "whatsapp", "windows"])
  m = pa.machine()
  out, failed = {"machine": m}, False
  if "mail" in only:
    gog_boxes = ["personal"] if m == "macbook-pro" else ["work", "personal"]
    out["mail"] = [check_mailbox(mb) for mb in gog_boxes]
    failed |= any(r.get("account") != "ok" or r.get("write") != "ok" for r in out["mail"])
    if m == "macbook-pro":
      out["mail_note"] = "work mailbox: Gmail connector; do its sent-mail check and write no-op"
  if "whatsapp" in only:
    out["whatsapp"] = check_whatsapp() if m == "macbook-pro" else "off on this machine (MacBook Pro only)"
    failed |= out["whatsapp"].startswith("error")
  if "windows" in only:
    out["windows"] = [window(c, now) for c in CHANNELS]

  if args.json:
    print(pa.as_json(out))
  else:
    print(f"machine: {m}")
    for r in out.get("mail", []):
      print(f"mail {r['mailbox']} ({r['address']}) via gog: account {r['account']}, write {r.get('write', '-')}"
            + (f"  fix: {r['fix']}" if r.get("fix") else ""))
    if out.get("mail_note"):
      print(out["mail_note"])
    if "whatsapp" in out:
      print(f"whatsapp: {out['whatsapp']}")
    for w in out.get("windows", []):
      use = (f"search after:{w['slack_after']}, then drop results before epoch {w['epoch']}"
             if w["channel"] == "slack" else f"whatsapp.py --since {w['whatsapp_since']}")
      print(f"{w['channel']} window: since {w['since']:%a %d %b %H:%M} ({w['source']}); {use}")
  sys.exit(1 if failed else 0)


if __name__ == "__main__":
  main()
