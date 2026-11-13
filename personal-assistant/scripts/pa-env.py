#!/usr/bin/env python3
"""Start-of-run checks and time windows for the personal-assistant skills, in one call.

  pa-env.py check                 # machine, gog mailboxes, WhatsApp, Slack/WhatsApp windows
  pa-env.py check --only mail     # or auth, windows, whatsapp; repeatable
  pa-env.py check --mailbox personal  # just that gog mailbox (repeatable)
  pa-env.py auth                  # just the gog logins, one line per mailbox gog serves here
  pa-env.py auth --notify         # the same, plus a macOS notification if one has expired
  pa-env.py mark slack whatsapp   # after Ian has seen the list: record this run

`check` prints:
  machine     macbook-pro or other (the mail skill's "Which machine")
  mail        for each mailbox gog serves here (personal always; work off the MacBook Pro):
              the sent-mail account check and the write no-op (removing STARRED from an
              unstarred thread). On the MacBook Pro the work mailbox's connector checks
              are still the skill's to do. An expired login shows as
              `account auth expired: run gog auth add <address> --services ... --force-consent`.
  auth        (only with --only auth) the gog login of each of those mailboxes: `ok` or
              `auth expired: run ...`
  whatsapp    MacBook Pro only: whether whatsapp.py can read the app's database
  windows     Slack and WhatsApp: since the last run (~/.claude/personal-assistant/
              <channel>-last-run), the last 24 hours if there's none, capped at 7 days;
              with the Slack `after:` date (Slack's after: is exclusive, so it's the day
              before) and the whatsapp.py `--since` value

Each check stands alone: one that fails, hangs past its timeout or crashes shows as
`error: <reason>` and is tried once more, and the others still run. Exits 1 if any check
failed. `auth` exits 1 if any login is expired or gog can't be reached.

PA_WHATSAPP (a stand-in for whatsapp.py), PA_CHECK_TIMEOUT (seconds per WhatsApp or gog
call, 45) and PA_RETRY_WAIT (seconds before the second try, 3) are for the tests.
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
WHATSAPP = os.environ.get("PA_WHATSAPP") or os.path.join(HERE, "whatsapp.py")
TIMEOUT = float(os.environ.get("PA_CHECK_TIMEOUT") or 45)
RETRY_WAIT = float(os.environ.get("PA_RETRY_WAIT") or 3)
pa.GOG_TIMEOUT = TIMEOUT

# The whole set, always: a consent replaces the account's scopes (mail skill, "Which gog
# services to authorise").
GOG_SERVICES = "gmail,calendar,drive,sheets,docs,slides,contacts,people"
AUTH_ERRORS = ("invalid_grant", "token expired", "token has been expired", "expired or revoked",
               "unauthorized", "invalid_token", "unreachable", "no token", "token not found",
               "refresh token")
NETWORK_ERRORS = ("network is unreachable", "host is unreachable", "no such host",
                  "dial tcp", "connection refused", "i/o timeout", "no answer from gog")


def auth_fix(addr):
  return f"run gog auth add {addr} --services {GOG_SERVICES} --force-consent"


def is_auth_error(text):
  t = (text or "").lower()
  if any(n in t for n in NETWORK_ERRORS):
    return False
  return any(a in t for a in AUTH_ERRORS)


def short(text, width=160):
  """An error as one short line: the last non-empty line usually says what went wrong."""
  lines = [l.strip() for l in str(text).splitlines() if l.strip()]
  return pa.one_line(lines[-1] if lines else str(text) or "unknown error", width)


def reason(e):
  if isinstance(e, subprocess.TimeoutExpired):
    return f"no answer after {int(e.timeout)}s"
  if isinstance(e, OSError):
    return f"{e.strerror or e}"
  if isinstance(e, pa.GogError):
    return short(e.detail)
  return f"{type(e).__name__}: {short(e)}"


def isolated(fn, *args, failed=lambda r: False):
  """Run one check so nothing it does can stop the others: any exception becomes
  `error: <reason>`. A failure (an exception, or failed(result)) is tried once more."""
  for attempt in (1, 2):
    try:
      res = fn(*args)
      if not failed(res) or attempt == 2:
        return res
    except Exception as e:  # noqa: BLE001 - one check must never take the rest down
      res = f"error: {reason(e)}"
      if attempt == 2:
        return res
    time.sleep(RETRY_WAIT)
  return res


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


def check_auth(mb):
  """`ok`, `auth expired: run gog auth add ...`, or `error: <reason>`."""
  addr = pa.mailbox_address(mb)
  try:
    pa.gog(mb, "gmail", "labels", "list")
    return "ok"
  except pa.GogError as e:
    return f"auth expired: {auth_fix(addr)}" if is_auth_error(e.detail) else f"error: {short(e.detail)}"


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
    if is_auth_error(e.detail):
      res["account"] = f"auth expired: {auth_fix(addr)}"
      res["fix"] = f"! gog auth add {addr} --services {GOG_SERVICES} --force-consent"
    else:
      res["account"] = f"error: {short(e.detail)}"
    return res
  try:
    unstarred = pa.search(mb, "-is:starred", 1)
    if unstarred:
      pa.gog(mb, "gmail", "thread", "modify", unstarred[0]["id"], "--remove", "STARRED")
      res["write"] = "ok"
    else:
      res["write"] = "no unstarred thread to test on"
  except pa.GogError as e:
    res["write"] = f"error: {short(e.detail)}"
  return res


def mailbox_isolated(mb):
  """check_mailbox, tried twice on an error (not on an expired login, which a retry won't fix)."""
  res = isolated(check_mailbox, mb,
                 failed=lambda r: str(r.get("account", "")).startswith("error")
                 or str(r.get("write", "")).startswith("error"))
  if isinstance(res, str):  # it raised twice
    res = {"mailbox": mb, "address": pa.mailbox_address(mb), "account": res}
  return res


def check_whatsapp():
  p = subprocess.run([sys.executable, WHATSAPP, "chats", "--limit", "1"],
                     capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
  return "ok" if p.returncode == 0 else f"error: {short(p.stderr or p.stdout or f'exit {p.returncode}')}"


def gog_mailboxes(m):
  return ["personal"] if m == "macbook-pro" else ["work", "personal"]


def notify(title, message):
  """A macOS notification through pa-notify.py; never fails the run."""
  try:
    p = subprocess.run([sys.executable, os.path.join(HERE, "pa-notify.py"), "--title", title, message],
                       capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
  except (OSError, subprocess.TimeoutExpired) as e:
    print(f"could not send the notification: {reason(e)}", file=sys.stderr)
    return
  if p.returncode == 0:
    print(f"notified: {title}: {p.stdout.strip()}")
  else:
    print(f"could not send the notification: {short(p.stderr or p.stdout)}", file=sys.stderr)


def cmd_auth(args, m):
  results = [(mb, isolated(check_auth, mb, failed=lambda r: r.startswith("error"))) for mb in gog_mailboxes(m)]
  bad = [(mb, r) for mb, r in results if r != "ok"]
  if args.json:
    print(pa.as_json({"machine": m, "auth": [{"mailbox": mb, "address": pa.mailbox_address(mb), "status": r}
                                             for mb, r in results]}))
  else:
    for mb, r in results:
      print(f"auth {mb} ({pa.mailbox_address(mb)}): {r}")
  if bad and args.notify:
    expired = [pa.mailbox_address(mb) for mb, r in bad if r.startswith("auth expired")]
    if expired:
      notify("gog login expired", f"Run gog auth add for {' and '.join(expired)} (see /mail setup)")
    else:
      notify("gog check failed", "; ".join(f"{mb}: {r}" for mb, r in bad))
  sys.exit(1 if bad else 0)


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  p = sub.add_parser("check")
  p.add_argument("--only", action="append", choices=["mail", "auth", "whatsapp", "windows"])
  p.add_argument("--mailbox", action="append", choices=list(pa.MAILBOXES),
                 help="check only these gog mailboxes (repeatable; default all gog serves here)")
  p.add_argument("--json", action="store_true")
  p = sub.add_parser("auth", help="check the gog logins only")
  p.add_argument("--notify", action="store_true", help="send a macOS notification if one fails")
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

  m = pa.machine()
  if args.cmd == "auth":
    cmd_auth(args, m)
    return

  only = set(args.only or ["mail", "whatsapp", "windows"])
  boxes = [mb for mb in gog_mailboxes(m) if not args.mailbox or mb in args.mailbox]
  out, failed = {"machine": m}, False
  if "auth" in only:
    out["auth"] = [{"mailbox": mb, "address": pa.mailbox_address(mb),
                    "status": isolated(check_auth, mb, failed=lambda r: r.startswith("error"))}
                   for mb in boxes]
    failed |= any(r["status"] != "ok" for r in out["auth"])
  if "mail" in only:
    out["mail"] = [mailbox_isolated(mb) for mb in boxes]
    failed |= any(r.get("account") != "ok" or r.get("write") != "ok" for r in out["mail"])
    if m == "macbook-pro" and (not args.mailbox or "work" in args.mailbox):
      out["mail_note"] = "work mailbox: Gmail connector; do its sent-mail check and write no-op"
  if "whatsapp" in only:
    if m == "macbook-pro":
      out["whatsapp"] = isolated(check_whatsapp, failed=lambda r: r.startswith("error"))
    else:
      out["whatsapp"] = "off on this machine (MacBook Pro only)"
    failed |= out["whatsapp"].startswith("error")
  if "windows" in only:
    res = isolated(lambda: [window(c, now) for c in CHANNELS])
    if isinstance(res, str):
      out["windows_error"] = res
      failed = True
    else:
      out["windows"] = res

  if args.json:
    print(pa.as_json(out))
  else:
    print(f"machine: {m}")
    for r in out.get("auth", []):
      print(f"auth {r['mailbox']} ({r['address']}): {r['status']}")
    for r in out.get("mail", []):
      print(f"mail {r['mailbox']} ({r['address']}) via gog: account {r['account']}, write {r.get('write', '-')}"
            + (f"  fix: {r['fix']}" if r.get("fix") and "auth expired" not in r["account"] else ""))
    if out.get("mail_note"):
      print(out["mail_note"])
    if "whatsapp" in out:
      print(f"whatsapp: {out['whatsapp']}")
    for w in out.get("windows", []):
      use = (f"search after:{w['slack_after']}, then drop results before epoch {w['epoch']}"
             if w["channel"] == "slack" else f"whatsapp.py --since {w['whatsapp_since']}")
      print(f"{w['channel']} window: since {w['since']:%a %d %b %H:%M} ({w['source']}); {use}")
    if out.get("windows_error"):
      print(f"windows: {out['windows_error']}")
  sys.exit(1 if failed else 0)


if __name__ == "__main__":
  main()
