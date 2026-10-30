#!/usr/bin/env python3
"""State and bookkeeping for the linkedin-sync skill: the invite window, queue and log, and
the local evidence for new people's levels.

  linkedin-state.py window                    # NOW and LAST (step 4.1)
  linkedin-state.py budget [--per-day 40]     # invitations sent in the last 24 hours, and LEFT
  linkedin-state.py queue < viewers.txt       # step 4.4: who to invite, in order
  linkedin-state.py suggestions < page.txt    # step 5.3: suggested people to invite, in order
  linkedin-state.py log sent URL "Name"       # after each connect-profile.js result
  linkedin-state.py follows < page.txt        # step 5b: followers to follow back, in order
  linkedin-state.py log --follows followed URL "Name"  # after each follow-follower.js result
  linkedin-state.py defer < rest.tsv          # everyone not yet tried, as deferred
  linkedin-state.py done NOW                  # write NOW to linkedin-sync-last
  linkedin-state.py evidence < created.txt    # step 7: meetings and people notes per person
  linkedin-state.py connections [OUT] < page.txt  # step 2.3: the connections JSON for the import
  linkedin-state.py export                    # step 6: newest data export, and what to do
  linkedin-state.py correspondents --gog personal [< to-cc.txt]  # step 3b: who Ian emailed, not in people/
  linkedin-state.py match "Name" [--company X] < results.json   # step 3b: pick the profile from a search
  linkedin-state.py log --email a@b.com sent URL "Name"         # after each step 3b result

State is in ~/.local/state/personal-assistant (PA_LINKEDIN_STATE overrides it):
linkedin-sync-last (UTC time of the last sync), linkedin-invites.log (one line per viewer
tried: time, status, url, name; tab-separated) and linkedin-follows.log (the same, one line per
follower followed back or tried). The follows have their own log so that following someone never
changes whether they're invited.

`follows` reads the get_page_text output of the followers page after extract-followers.js
(FOLLOWERS-BEGIN ... FOLLOWERS-END <count>), checks the count, and prints `url<TAB>name` lines
newest first, leaving out anyone the follows log has as followed, already or not-followed
(LinkedIn wouldn't let Ian follow them: tried once, then left to Ian). After --per-day
(25) less the follows of the last 24 hours, it prints `# over the cap` and the rest, which the
next run picks up from the page again.

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

`correspondents` lists the people Ian has emailed since LAST (sent mail: anyone he wrote to,
including the senders he replied to), from the To and Cc of his sent messages. `--gog MAILBOX`
(repeatable) reads a mailbox's sent mail through gog; anything on stdin is read too, one line
per sent message with its To and Cc addresses (for a mailbox read through the Gmail connector).
It leaves out Ian's own addresses, no-reply and role addresses (info@, support@, ...), the
senders in rules/senders.tsv, company names (Acme Ltd), messages to more than --max-recipients people (mailouts), anyone
without a first and last name, anyone already in people/ (the address in a note, or a file
named for them: people-note.py find), and anyone the correspondents log has, unless deferred or
stopped by a limit or error. It prints `email<TAB>name<TAB>company<TAB>mailbox<TAB>search-url` lines,
deferred ones first, with a `# over the cap` line after --max (20): pass the rest to
`defer --email`. company is the mail domain's name (acme for jane@mail.acme.co.uk), empty for
webmail; mailbox is work if Ian wrote to them from work at all (stdin counts as
--stdin-mailbox, default work), else personal; the search URL is LinkedIn's people search for the name and company.

`match` reads extract-search.js's JSON ({results: [{url, name, headline, degree}]}) and picks
the result that is the person: their first and last names match, and when there are several,
the one whose headline names the company. It prints `MATCH <degree> <url> <name>`,
`AMBIGUOUS <n>` followed by the candidates (`url<TAB>name<TAB>headline`), or `NONE`. Without a
company only a single result with their name is a MATCH.

`log --email ADDRESS` logs a step 3b result to linkedin-correspondents.log (time, status, email,
name, url) and, for a connect-profile.js status, to the invitations log too, so the daily budget
and steps 4 and 5 count it.

`export` finds the newest *LinkedInDataExport*.zip in ~/Downloads (PA_DOWNLOADS overrides it)
and prints `EXPORT <path> <age>d` (or `EXPORT none`), then `ACTION import` when it's less than
7 days old, `ACTION request` when there's none or it's more than 30 days old, else
`ACTION none`.
"""

import argparse
import concurrent.futures
import datetime
import email.utils
import importlib.util
import json
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

STATE = os.path.expanduser(os.environ.get("PA_LINKEDIN_STATE", "~/.local/state/personal-assistant"))
LAST = os.path.join(STATE, "linkedin-sync-last")
LOG = os.path.join(STATE, "linkedin-invites.log")
FOLLOWS_LOG = os.path.join(STATE, "linkedin-follows.log")
CORRESPONDENTS_LOG = os.path.join(STATE, "linkedin-correspondents.log")
DOWNLOADS = os.path.expanduser(os.environ.get("PA_DOWNLOADS", "~/Downloads"))
DONE = {"sent", "pending", "connected"}
INVITE_STATUSES = ["sent", "connected", "pending", "no-connect", "needs-email", "limit", "unexpected", "error",
                   "deferred"]


def utc_now():
  return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_log(path=LOG):
  """url -> (latest status, name)."""
  latest = {}
  try:
    with open(path, encoding="utf-8") as f:
      for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 3:
          latest[parts[2]] = (parts[1], parts[3] if len(parts) > 3 else "")
  except OSError:
    pass
  return latest


def append_log(status, url, name, path=LOG):
  os.makedirs(STATE, exist_ok=True)
  with open(path, "a", encoding="utf-8") as f:
    f.write(f"{utc_now()}\t{status}\t{url}\t{' '.join(name.split())}\n")


def count_recent(status, path, hours=24):
  """How many `status` lines the log has from the last `hours`."""
  since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
  n = 0
  try:
    with open(path, encoding="utf-8") as f:
      for line in f:
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1] == status:
          try:
            at = datetime.datetime.strptime(parts[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
          except ValueError:
            continue
          n += at >= since
  except OSError:
    pass
  return n


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
  sent = count_recent("sent", LOG)
  print(f"SENT {sent}")
  print(f"LEFT {max(0, args.per_day - sent)}")


def cmd_follows(args):
  people = read_page(sys.stdin.read(), "FOLLOWERS-END")
  log = read_log(FOLLOWS_LOG)
  followed = count_recent("followed", FOLLOWS_LOG)
  left = max(0, args.per_day - followed)
  queue, seen = [], set()
  for p in people:
    url = p.get("url")
    if not url or url in seen or log.get(url, ("",))[0] in FOLLOW_DONE:
      continue
    seen.add(url)
    queue.append((url, p.get("name", "")))
  print(f"# {len(people)} follower(s) not followed back on the page, {len(queue)} to follow; "
        f"FOLLOWED {followed} in the last 24 hours, LEFT {left}")
  for i, (url, name) in enumerate(queue):
    if i == left:
      print("# over the cap: the next run picks these up")
    print(f"{url}\t{name}")


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


# Step 3b: people Ian has emailed who aren't in people/

CORRESPONDENT_STATUSES = INVITE_STATUSES + ["ambiguous", "no-match"]
CORRESPONDENT_RETRY = ("deferred", "limit", "unexpected", "error")  # not done yet: try again next run
NOREPLY_RE = re.compile(r"(no-?reply|do-?not-?reply|notifications?|mailer-daemon|postmaster|bounces?|alerts?)@", re.I)
ROLE_RE = re.compile(r"^(accounts?|admin|billing|careers|contact|enquir(y|ies)|events|finance|hello|help|hi|hr|"
                     r"info|invoices?|jobs|legal|marketing|news|office|orders|payroll|press|privacy|reception|"
                     r"sales|security|shop|store|support|team|webmaster)@", re.I)
SKIP_DOMAINS = ("calendar.google.com", "googlegroups.com", "docs.google.com", "reply.github.com",
                "linkedin.com", "slack.com", "zoom.us", "calendly.com")
WEBMAIL = {"gmail.com", "googlemail.com", "hotmail.com", "hotmail.co.uk", "outlook.com", "live.com", "live.co.uk",
           "msn.com", "yahoo.com", "yahoo.co.uk", "ymail.com", "icloud.com", "me.com", "mac.com", "aol.com",
           "protonmail.com", "proton.me", "pm.me", "gmx.com", "gmx.de", "gmx.net", "web.de", "btinternet.com",
           "sky.com", "virginmedia.com", "fastmail.com", "hey.com", "mail.com", "zoho.com", "qq.com", "163.com"}
COMPANY_RE = re.compile(r"\b(ltd|limited|inc|llc|llp|plc|gmbh|bv|group|team|services|solutions)\.?$", re.I)
SECOND_LEVEL = {"co", "com", "org", "net", "ac", "gov", "edu", "ltd", "plc"}
SENDERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "rules", "senders.tsv")


def people_note():
  """scripts/people-note.py, for its find()."""
  path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "people-note.py")
  spec = importlib.util.spec_from_file_location("people_note", path)
  mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(mod)
  return mod


def sender_rules():
  rules = set()
  try:
    with open(SENDERS, encoding="utf-8") as f:
      for line in f:
        if line.strip() and not line.startswith("#"):
          rules.add(line.split("\t")[0].strip().lower())
  except OSError:
    pass
  return rules


def company_of(address):
  domain = address.rsplit("@", 1)[-1].lower()
  if domain in WEBMAIL:
    return ""
  parts = domain.split(".")
  if len(parts) >= 3 and parts[-2] in SECOND_LEVEL and len(parts[-1]) == 2:
    return parts[-3]
  return parts[-2] if len(parts) >= 2 else ""


def person_name(display, address):
  """'First Last' from a display name, or from first.last@; '' if there's no first and last name."""
  name = re.sub(r"\s*[(\[|].*$", "", (display or "").strip().strip("'\""))  # "Jane Doe (Acme)", "Jane | Acme"
  if "@" in name:
    name = ""
  if "," in name:  # "Doe, Jane"
    last, _, first = name.partition(",")
    name = f"{first.strip()} {last.strip()}"
  if len(name.split()) < 2:  # no name, or just "Jane": try jane.doe@
    local = address.split("@")[0].split("+")[0]
    bits = [b for b in re.split(r"[._-]", local) if b]
    if len(bits) == 2 and all(b.isalpha() and len(b) > 1 for b in bits):
      name = " ".join(b.capitalize() for b in bits)
  name = " ".join(name.split())
  return name if len(name.split()) >= 2 and not COMPANY_RE.search(name) else ""


def sent_recipients(mailbox, since):
  """One list of (display, address) per message Ian sent from a mailbox since `since`."""
  epoch = int(datetime.datetime.strptime(since, "%Y-%m-%dT%H:%M:%SZ")
              .replace(tzinfo=datetime.timezone.utc).timestamp())
  msgs = pa.gog(mailbox, "gmail", "messages", "search", "--max", 500, "--", f"in:sent after:{epoch}") or []

  def one(m):
    h = (pa.gog(mailbox, "gmail", "get", m["id"], "--format", "metadata") or {}).get("headers") or {}
    return email.utils.getaddresses([h.get("to", ""), h.get("cc", "")])

  with concurrent.futures.ThreadPoolExecutor(6) as ex:
    return list(ex.map(one, msgs))


def last_sync():
  try:
    return open(LAST).read().strip()
  except OSError:
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_correspondents(args):
  messages = []  # (mailbox, [(display, address)]) per sent message
  for mb in args.gog or []:
    try:
      messages += [(mb, r) for r in sent_recipients(mb, args.since or last_sync())]
    except pa.GogError as e:
      pa.die(f"gog: {e}")
  if not sys.stdin.isatty():
    for line in sys.stdin:
      line = re.sub(r"^\s*(to|cc)\s*:\s*", "", line.strip(), flags=re.I)
      if line and not line.startswith("#"):
        messages.append((args.stdin_mailbox, email.utils.getaddresses([line])))
  rules, log = sender_rules(), read_log(CORRESPONDENTS_LOG)
  pn = people_note()
  known = set()
  for f in os.listdir(pn.PEOPLE) if os.path.isdir(pn.PEOPLE) else []:
    if f.endswith(".md"):
      with open(os.path.join(pn.PEOPLE, f), encoding="utf-8", errors="replace") as fh:
        known.update(pa.addresses(fh.read()))
  people, skipped = {}, {"mailout": 0, "no name": 0, "in people/": 0, "tried before": 0}
  for mailbox, recips in messages:
    recips = [(d, a.lower()) for d, a in recips if "@" in a]
    if len(recips) > args.max_recipients:
      skipped["mailout"] += 1
      continue
    for display, address in recips:
      domain = address.rsplit("@", 1)[1]
      if (address in pa.IAN_ADDRESSES or NOREPLY_RE.search(address) or ROLE_RE.match(address)
              or address in rules or f"@{domain}" in rules
              or any(domain == d or domain.endswith("." + d) for d in SKIP_DOMAINS)):
        continue
      old = people.get(address, ("", "personal"))
      # Anyone Ian has written to from work counts as work
      people[address] = (display or old[0], "work" if "work" in (mailbox, old[1]) else "personal")
  rows = []
  for address, (display, mailbox) in people.items():
    status = log.get(address, ("",))[0]
    if status and status not in CORRESPONDENT_RETRY:
      skipped["tried before"] += 1
      continue
    if address in known:
      skipped["in people/"] += 1
      continue
    name = person_name(display, address)
    if not name:
      skipped["no name"] += 1
      continue
    if [f for f, why, _ in pn.find(name, None) if why != "first name + surname initial"]:
      skipped["in people/"] += 1
      continue
    company = company_of(address)
    url = ("https://www.linkedin.com/search/results/people/?keywords="
           + urllib.parse.quote(f"{name} {company}".strip()))
    rows.append((status != "deferred", address, name, company, mailbox, url))
  rows.sort(key=lambda r: r[0])  # deferred first, otherwise in the order they were found
  print(f"# {len(people)} correspondent(s), {len(rows)} to look up; skipped: "
        + ", ".join(f"{v} {k}" for k, v in skipped.items()))
  for i, row in enumerate(rows):
    if i == args.max:
      print("# over the cap: pass the lines below to `defer --email`")
    print("\t".join(row[1:]))


def name_tokens(name):
  name = re.sub(r"\s*[,(|].*$", "", name or "")  # "Jane Doe, PhD", "Jane Doe (she/her)"
  return [t for t in re.split(r"[\s.-]+", people_note().fold(name)) if t and t.isalpha()]


def cmd_match(args):
  data = json.loads(sys.stdin.read())
  if "error" in data:
    pa.die(f"the search page said: {data['error']}")
  want = name_tokens(args.name)
  company = (args.company or "").lower()
  found = []
  for r in data.get("results") or []:
    got = name_tokens(r.get("name", ""))
    if want and got and got[0] == want[0] and got[-1] == want[-1]:
      found.append(r)
  if company and len(found) > 1:
    at = [r for r in found if company in (r.get("headline") or "").lower().replace(" ", "")]
    found = at or found
  if not found:
    print("NONE")
  elif len(found) == 1 and (company or len(data.get("results") or []) == 1):
    r = found[0]
    print(f"MATCH {r.get('degree') or '-'} {r['url']} {r.get('name', '')}")
  else:
    print(f"AMBIGUOUS {len(found)}")
    for r in found:
      print(f"{r['url']}\t{r.get('name', '')}\t{r.get('headline', '')}")


FOLLOW_STATUSES = ["followed", "already", "not-followed", "missing", "limit", "unexpected", "error"]
FOLLOW_DONE = ("followed", "already", "not-followed")  # tried once: never queued again


def cmd_log(args):
  if args.email:
    if args.status not in CORRESPONDENT_STATUSES:
      pa.die(f"--email status must be one of {', '.join(CORRESPONDENT_STATUSES)}", 2)
    os.makedirs(STATE, exist_ok=True)
    with open(CORRESPONDENTS_LOG, "a", encoding="utf-8") as f:
      f.write(f"{utc_now()}\t{args.status}\t{args.email.lower()}\t{' '.join(args.name.split())}\t{args.url}\n")
    if args.status in INVITE_STATUSES and args.status != "deferred" and "/in/" in args.url:
      append_log(args.status, args.url, args.name)
    print(f"logged {args.status} {args.email} (correspondents)")
  elif args.follows:
    if args.status not in FOLLOW_STATUSES:
      pa.die(f"--follows status must be one of {', '.join(FOLLOW_STATUSES)}", 2)
    append_log(args.status, args.url, args.name, FOLLOWS_LOG)
  else:
    if args.status not in INVITE_STATUSES:
      pa.die(f"status must be one of {', '.join(INVITE_STATUSES)}", 2)
    append_log(args.status, args.url, args.name)
  print(f"logged {args.status} {args.url}" + (" (follows)" if args.follows else ""))


def cmd_defer(args):
  n = 0
  os.makedirs(STATE, exist_ok=True)
  for line in sys.stdin:
    line = line.rstrip("\n")
    if not line or line.startswith("#"):
      continue
    if args.email:  # correspondents: email<TAB>name<TAB>...
      address, name = (line.split("\t") + [""])[:2]
      with open(CORRESPONDENTS_LOG, "a", encoding="utf-8") as f:
        f.write(f"{utc_now()}\tdeferred\t{address.lower()}\t{name}\t\n")
    else:
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
  p.add_argument("--follows", action="store_true", help="a follow-follower.js result, to the follows log")
  p.add_argument("--email", help="a step 3b result for this address, to the correspondents log")
  p.add_argument("status")
  p.add_argument("url")
  p.add_argument("name", nargs="?", default="")
  sub.add_parser("suggestions")
  p = sub.add_parser("follows")
  p.add_argument("--per-day", type=int, default=25)
  p = sub.add_parser("connections")
  p.add_argument("out", nargs="?", help="default $TMPDIR/linkedin-connections-<YYYYMMDD>.json")
  sub.add_parser("export")
  p = sub.add_parser("defer")
  p.add_argument("--email", action="store_true", help="correspondents lines (email<TAB>name...)")
  p = sub.add_parser("correspondents")
  p.add_argument("--gog", action="append", choices=["work", "personal"], help="read this mailbox's sent mail")
  p.add_argument("--stdin-mailbox", choices=["work", "personal"], default="work",
                 help="the mailbox the stdin lines come from (default work: the Gmail connector)")
  p.add_argument("--since", help="UTC time, as linkedin-sync-last (default LAST)")
  p.add_argument("--max", type=int, default=20)
  p.add_argument("--max-recipients", type=int, default=8)
  p = sub.add_parser("match")
  p.add_argument("name")
  p.add_argument("--company", default="")
  p = sub.add_parser("done")
  p.add_argument("now")
  p = sub.add_parser("evidence")
  p.add_argument("--days", type=int, default=30)
  args = ap.parse_args()
  {"window": cmd_window, "budget": cmd_budget, "queue": cmd_queue, "suggestions": cmd_suggestions, "log": cmd_log, "defer": cmd_defer,
   "done": cmd_done, "evidence": cmd_evidence, "connections": cmd_connections, "export": cmd_export,
   "follows": cmd_follows, "correspondents": cmd_correspondents, "match": cmd_match}[args.cmd](args)


if __name__ == "__main__":
  main()
