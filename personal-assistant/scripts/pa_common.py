"""Shared helpers for the personal-assistant scripts: mailboxes, gog, gtd paths, the machine.

Not run directly. The scripts next to it import it.
"""

import datetime
import json
import os
import platform
import re
import subprocess
import sys
import time

MAILBOXES = {
  "work": "ian.miell@container-solutions.com",
  "personal": "ian.miell@gmail.com",
}
IAN_ADDRESSES = set(MAILBOXES.values())

GTD = os.path.expanduser(os.environ.get("GTD_DIR", "~/git/gtd"))
STATE = os.path.expanduser(os.environ.get("PA_STATE", "~/.claude/personal-assistant"))
OPEN_STATUSES = ("todo", "waiting")
STATUSES = ("todo", "waiting", "background", "someday", "new", "closed")

# PA_GOG lets the tests put a fake gog in place of the real one.
GOG = os.environ.get("PA_GOG", "gog")


def die(msg, code=1):
  print(msg, file=sys.stderr)
  sys.exit(code)


def mailbox_address(name):
  if name in MAILBOXES:
    return MAILBOXES[name]
  if name in IAN_ADDRESSES:
    return name
  die(f"unknown mailbox {name!r}: use work or personal", 2)


def mailbox_name(address):
  for k, v in MAILBOXES.items():
    if v == address:
      return k
  return address


def machine():
  """'macbook-pro' or 'other', as the mail skill's "Which machine" check. PA_MACHINE overrides it
  (the tests set it, so they behave the same on every machine)."""
  if os.environ.get("PA_MACHINE"):
    return os.environ["PA_MACHINE"]
  if platform.system() != "Darwin":
    return "other"
  try:
    out = subprocess.run(["system_profiler", "SPHardwareDataType"], capture_output=True,
                         text=True, timeout=30).stdout
  except (OSError, subprocess.TimeoutExpired):
    return "other"
  return "macbook-pro" if "Model Name: MacBook Pro" in out else "other"


class GogError(Exception):
  pass


def gog(mailbox, *args, parse=True, dry_run=False):
  """Run gog for one mailbox, always with --gmail-no-send. Returns parsed JSON (or text)."""
  cmd = [GOG, "-a", mailbox_address(mailbox), "--gmail-no-send", "--no-input"]
  if parse:
    cmd += ["--json", "--results-only"]
  cmd += [str(a) for a in args]
  if dry_run:
    print("would run: " + " ".join(cmd[1:]))
    return None
  # Gmail's per-minute quota runs out on big batches: back off and retry.
  for wait in (5, 15, 30, 60, None):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if p.returncode == 0 or "rateLimitExceeded" not in (p.stderr + p.stdout) or wait is None:
      break
    time.sleep(wait)
  if p.returncode != 0:
    raise GogError(f"{' '.join(cmd[1:])}: {(p.stderr or p.stdout).strip()}")
  if not parse:
    return p.stdout
  out = p.stdout.strip()
  return json.loads(out) if out else None


def search(mailbox, query, max_n=25):
  """Thread search. The query goes after `--` so one starting with `-` isn't read as a flag."""
  return gog(mailbox, "gmail", "search", "--max", max_n, "--", query) or []


def headers(msg):
  """A Gmail API message's headers as a dict (first value wins, names lower case).

  gog leaves "value" out of an empty header, so a missing value reads as "".
  """
  h = {}
  for x in (msg.get("payload") or {}).get("headers") or []:
    if x.get("name"):
      h.setdefault(x["name"].lower(), x.get("value") or "")
  return h


ADDR_RE = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")


def addresses(text):
  return [a.lower() for a in ADDR_RE.findall(text or "")]


def task_status(n):
  for s in STATUSES:
    if os.path.lexists(os.path.join(GTD, "status", s, str(n))):
      return s
  return None


def task_subject(n):
  try:
    with open(os.path.join(GTD, "tasks", str(n), "notes.md"), encoding="utf-8", errors="replace") as f:
      return f.readline().lstrip("# ").strip()
  except OSError:
    return None


def task_reminder(n):
  try:
    with open(os.path.join(GTD, "tasks", str(n), ".remindme")) as f:
      return datetime.datetime.fromtimestamp(int(f.read().strip()))
  except (OSError, ValueError):
    return None


def open_tasks(statuses=OPEN_STATUSES):
  """(number, status) for every task in the given statuses."""
  for s in statuses:
    d = os.path.join(GTD, "status", s)
    try:
      names = os.listdir(d)
    except OSError:
      continue
    for n in names:
      if n.isdigit():
        yield int(n), s


def gtd_cmd(*args, stdin_text=None, extra_env=None, timeout=120):
  """Run bin/gtd the way the gtd skill says: web display context, no stdin, a timeout."""
  env = dict(os.environ, GTD_DISPLAY_CONTEXT="web")
  env.update(extra_env or {})
  p = subprocess.run([os.path.join(GTD, "bin", "gtd"), *args], cwd=GTD, env=env, text=True,
                     input=stdin_text if stdin_text is not None else "", capture_output=True,
                     timeout=timeout)
  out = re.sub(r"Processing \d+/\d+", "", p.stdout)
  return p.returncode, out, p.stderr


def as_json(obj):
  def default(o):
    if isinstance(o, (datetime.datetime, datetime.date)):
      return o.isoformat()
    raise TypeError(type(o))
  return json.dumps(obj, indent=1, ensure_ascii=False, default=default)


def one_line(text, width=100):
  text = " ".join((text or "").split())
  return text if len(text) <= width else text[:width - 1] + "…"
