#!/usr/bin/env python3
"""State and bookkeeping for the linkedin-sync skill: the invite window, queue and log, and
the local evidence for new people's levels.

  linkedin-state.py window                    # NOW and LAST (step 4.1)
  linkedin-state.py budget [--per-day 20] [--per-week 150]  # invitations sent lately, and LEFT
  linkedin-state.py queue --from-download     # step 4.4: who to invite, in order (or < page.txt)
  linkedin-state.py suggestions --from-download  # step 5.3: suggested people to invite, in order
  linkedin-state.py log sent URL "Name"       # after each connect-profile.js result: may say STOP
  linkedin-state.py follows --from-download   # step 5b: followers to follow back, in order
  linkedin-state.py log --follows followed URL "Name"  # after each follow-follower.js result
  linkedin-state.py defer --rest              # the saved queue's untried people, as deferred
  linkedin-state.py defer < rest.tsv          # these people, as deferred
  linkedin-state.py done NOW                  # write NOW to linkedin-sync-last
  linkedin-state.py evidence --events work.json --events personal.json < import.txt  # step 7
  linkedin-state.py mail-query < import.txt   # step 7: Gmail queries, 10 names each
  linkedin-state.py connections --from-download [OUT]  # step 2.3: the connections JSON for the import
  linkedin-state.py export [--import]         # step 6: newest data export, and what to do
  linkedin-state.py correspondents --gog personal [--threads-json sent.json]  # step 3b
  linkedin-state.py match "Name" [--company X] < results.json   # step 3b: pick the profile from a search
  linkedin-state.py log --email a@b.com sent URL "Name"         # after each step 3b result
  linkedin-state.py feed --from-download      # step 5c: posts in Ian's feed worth a response

Hand-off from the page: each extract-*.js saves what it read as a download,
~/Downloads/pa-linkedin-<kind>-<YYYYMMDDTHHMMSSZ>.json ({kind, count, rows}; PA_DOWNLOADS overrides
the folder), and `--from-download` on connections (kind connections), queue (viewers),
suggestions, follows (followers) and feed reads the newest one of its kind, checks the count,
and moves it to <state>/downloads so it's never read twice. It waits up to --wait (10) seconds
for the download, and refuses one more than 3 hours old (from an earlier run). Without
--from-download they read the get_page_text output on stdin, as before.

`log` also says what to do next, from the statuses logged lately (the last 3 hours, deferred
lines aside): `STOP <status>` after a limit, unexpected or error, or after three not-profile in a
row (stop all inviting); `BUDGET` once the viewers queue's --max invitations are sent; and with
either, the saved queue's people not yet tried, which `defer --rest` (`defer --email --rest` in
step 3b) logs as deferred. For --follows: `STOP` after a limit, unexpected or error, and `RERUN`
after three missing in a row (run extract-followers.js again). `queue` and `correspondents` save
the queue they print (linkedin-queue.tsv, linkedin-correspondents-queue.tsv) for this.

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

`budget` counts the `sent` lines of the last 24 hours and of the last 7 days in the log and
prints `SENT <n>`, `WEEK <w>` and `LEFT <the smaller of per-day - n and per-week - w>` (at
least 0): about 20 invitations a day with Premium, 10 without, and never more than 150 in any
7 days, which keeps under LinkedIn's own weekly invitation limit.

`suggestions` reads the get_page_text output of the Grow page (SUGGESTIONS-BEGIN ...
SUGGESTIONS-END <count>), checks the count, and prints `url<TAB>name<TAB>mutual` lines in the
page's order (most mutual connections first), leaving out anyone the log has at all: a
suggestion is tried once, and never deferred.

`evidence` reads `gtd import-connections --auto` output (the `Created <file> | <name> | ...`
and `Pending ...` lines) or one name per line, and for each person lists meeting transcripts
of the last 30 days whose name or text has their full name, and other people files that
mention them. With `--events FILE` (repeatable: the calendar connector's list_events JSON,
saved as is) it also finds them among the events' attendees, by display name or by address
(first.last@, flast@, firstlast@), leaving out anyone who declined; `--attendees FILE` takes
calendar-events.py attendees output instead (its text or --json). Mail is still
the skill's to search: `mail-query` prints the Gmail queries for it, `newer_than:30d ("Name
One" OR "Name Two" ...)`, 10 names to a query. The suggested level is `met` with a transcript
or an event, `in-touch` with a mention, otherwise `forgotten?` (until mail has been searched).

`connections` reads the get_page_text output of the connections page after
extract-connections.js (GTD-SYNC-BEGIN ... GTD-SYNC-END <count>), checks the count, and writes
the JSON lines, as they are, to OUT (default $TMPDIR/linkedin-connections-<YYYYMMDD>.json) for
`gtd import-connections --auto`. It refuses without the GTD-SYNC-END line.

`correspondents` lists the people Ian has emailed since LAST (sent mail: anyone he wrote to,
including the senders he replied to), from the To and Cc of his sent messages. `--gog MAILBOX`
(repeatable) reads a mailbox's sent mail through gog; when gog fails it says which mailbox and
stops, listing nothing. `--threads-json FILE` (repeatable) reads the Gmail connector's
search_threads or get_thread results, saved as they are, and takes the To and Cc of each
message from Ian (from one of his addresses, or labelled SENT). Anything on stdin is read too,
one line per sent message with its To and Cc addresses.
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

`feed` reads the get_page_text output of the feed's Network tab after extract-feed.js
(FEED-BEGIN ... FEED-END <count>), checks the count, and picks the posts Ian should respond to.
Each post scores for how close its author is to Ian (their people/ note, found by LinkedIn URL:
close 5, met 3, in-touch 2), how significant it is (FEED_SIGNALS: a new job or role, looking for
work, hard news, a launch or achievement, a milestone, speaking, hiring) and how popular
(reactions + 3 x comments + 2 x reposts, on a log scale: about 1 at 30, 2 at 100, 3 at 350, 4
at 1500, at most 5). So a close friend's post always makes it, a met or in-touch one's when it's
news or popular, anyone's when it's big news or goes viral. It keeps each author's best post,
those scoring at least --min (3.5), at most --max (15),
best first, and prints `score<TAB>name<TAB>level<TAB>why<TAB>age<TAB>url<TAB>text` lines, where
why says what counted ("close; new job; 134 reactions, 60 comments") and url is the post itself
(postUrl), or the author's recent activity when the page didn't give it. A `#` line first says how many were read and kept.

`export` finds the newest *LinkedInDataExport*.zip in ~/Downloads (PA_DOWNLOADS overrides it;
no shell glob, which zsh turns into an error when nothing matches) and prints
`EXPORT <path> <age>d` (or `EXPORT none`), then `ACTION import` when it's less than 7 days old,
`ACTION request` when there's none or it's more than 30 days old, else `ACTION none`. With
--import and `ACTION import`, it then runs `bin/gtd import-connections --auto <zip>` and prints
its output (safe to repeat: known people are skipped).
"""

import argparse
import concurrent.futures
import datetime
import email.utils
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
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
QUEUE = os.path.join(STATE, "linkedin-queue.tsv")
CORRESPONDENTS_QUEUE = os.path.join(STATE, "linkedin-correspondents-queue.tsv")
CONSUMED = os.path.join(STATE, "downloads")
DOWNLOADS = os.path.expanduser(os.environ.get("PA_DOWNLOADS", "~/Downloads"))
DONE = {"sent", "pending", "connected"}
INVITE_STATUSES = ["sent", "connected", "pending", "no-connect", "needs-email", "not-profile", "limit", "unexpected",
                   "error", "deferred"]
STOPS = ("limit", "unexpected", "error")
RECENT_HOURS = 3        # log lines this recent count as this run's, for STOP and RERUN
QUEUE_MAX_AGE = 12 * 3600
DOWNLOAD_MAX_AGE = 3 * 3600
# What each command reads from a download, and the end line of the same list in the page text
DOWNLOAD_KINDS = {"connections": "GTD-SYNC-END", "viewers": "VIEWERS-END", "suggestions": "SUGGESTIONS-END",
                  "followers": "FOLLOWERS-END", "feed": "FEED-END"}


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


def list_downloads():
  try:
    return os.listdir(DOWNLOADS)
  except FileNotFoundError:
    return []
  except OSError as e:
    pa.die(f"can't read {DOWNLOADS} ({e.strerror}): macOS may need to let this app read Downloads "
           "(System Settings > Privacy & Security > Files and Folders); tell Ian")


def from_download(kind, wait):
  """The rows of the newest pa-linkedin-<kind>-*.json download, checked, then moved out of the way."""
  pat = re.compile(rf"pa-linkedin-{re.escape(kind)}-\d{{8}}T\d{{6}}Z(?: \(\d+\))?\.json$")
  deadline = time.time() + wait
  while True:
    files = [os.path.join(DOWNLOADS, f) for f in list_downloads() if pat.match(f)]
    if files or time.time() >= deadline:
      break
    time.sleep(0.5)
  if not files:
    pa.die(f"no pa-linkedin-{kind}-*.json in {DOWNLOADS} after {wait}s: did Chrome block or ask about the "
           "download (it asks before a site downloads several files)? Fall back to get_page_text and "
           "pass the page text on stdin")
  newest = max(files, key=os.path.getmtime)
  name, old = os.path.basename(newest), time.time() - os.path.getmtime(newest)
  if old > DOWNLOAD_MAX_AGE:
    pa.die(f"{name} is {old / 3600:.0f} hours old, from an earlier run: run the extract script again")
  try:
    with open(newest, encoding="utf-8") as f:
      data = json.load(f)
  except (OSError, ValueError) as e:
    pa.die(f"can't read {name}: {e}")
  rows = data.get("rows") if isinstance(data, dict) else None
  if not isinstance(rows, list) or data.get("kind") != kind:
    pa.die(f"{name} isn't a {kind} list ({{kind, count, rows}}) from extract-*.js")
  if data.get("count") != len(rows):
    pa.die(f"{name} says {data.get('count')} but has {len(rows)} rows: run the extract script again")
  os.makedirs(CONSUMED, exist_ok=True)
  for f in os.listdir(CONSUMED):  # keep a month of them, for looking back
    p = os.path.join(CONSUMED, f)
    if time.time() - os.path.getmtime(p) > 30 * 86400:
      os.remove(p)
  shutil.move(newest, os.path.join(CONSUMED, name))
  print(f"# {len(rows)} row(s) from {name}, now in {CONSUMED}", file=sys.stderr)
  return rows


def page_rows(args, kind):
  """The rows from the download (--from-download) or from the page text on stdin."""
  if getattr(args, "from_download", None):
    if args.from_download != kind:
      pa.die(f"`{args.cmd}` reads {kind} downloads, not {args.from_download}", 2)
    return from_download(kind, args.wait)
  return read_page(sys.stdin.read(), DOWNLOAD_KINDS[kind])


def cmd_budget(args):
  sent = count_recent("sent", LOG)
  week = count_recent("sent", LOG, hours=7 * 24)
  print(f"SENT {sent}")
  print(f"WEEK {week}")
  print(f"LEFT {max(0, min(args.per_day - sent, args.per_week - week))}")


def cmd_follows(args):
  people = page_rows(args, "followers")
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
  viewers = page_rows(args, "viewers")
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
  save_queue(QUEUE, args.max, [(url, name) for url, name in queue])
  for i, (url, name) in enumerate(queue):
    if i == args.max:
      print("# over the cap: pass the lines below to `defer`")
    print(f"{url}\t{name}")


def cmd_suggestions(args):
  people = page_rows(args, "suggestions")
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
  if args.from_download:
    lines = [json.dumps(r, ensure_ascii=False) for r in page_rows(args, "connections")]
  else:
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


def newest_export():
  """The newest LinkedIn data export zip in DOWNLOADS, or None."""
  zips = [os.path.join(DOWNLOADS, f) for f in list_downloads()
          if "linkedindataexport" in f.lower() and f.lower().endswith(".zip")]
  zips = [z for z in zips if os.path.isfile(z)]
  return max(zips, key=os.path.getmtime) if zips else None


def cmd_export(args):
  newest = newest_export()
  if not newest:
    print("EXPORT none")
    print("ACTION request")
    return
  age = int((time.time() - os.path.getmtime(newest)) // 86400)
  action = "import" if age < 7 else "request" if age > 30 else "none"
  print(f"EXPORT {newest} {age}d")
  print(f"ACTION {action}")
  if args.do_import and action == "import":
    try:
      code, out, err = pa.gtd_cmd("import-connections", "--auto", newest, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
      pa.die(f"gtd import-connections --auto {newest}: {e}")
    print(out.rstrip())
    if code:
      pa.die(f"gtd import-connections failed ({code}): {err.strip()}")


# Step 3b: people Ian has emailed who aren't in people/

CORRESPONDENT_STATUSES = INVITE_STATUSES + ["ambiguous", "no-match"]
CORRESPONDENT_RETRY = ("deferred", "limit", "unexpected", "error", "not-profile")  # not done yet: try again next run
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

  msgs = [m for m in msgs if isinstance(m, dict) and m.get("id")]

  with concurrent.futures.ThreadPoolExecutor(6) as ex:
    return list(ex.map(one, msgs))


def last_sync():
  try:
    return open(LAST).read().strip()
  except OSError:
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")


def addresses_in(value):
  """[(display, address)] from a header string, a {name, email} dict, or a list of either."""
  if isinstance(value, str):
    return email.utils.getaddresses([value])
  if isinstance(value, list):
    return [a for v in value for a in addresses_in(v)]
  if isinstance(value, dict):
    addr = value.get("email") or value.get("address") or value.get("emailAddress")
    if isinstance(addr, dict):
      return addresses_in(addr)
    name = value.get("name") or value.get("displayName") or ""
    return [(name, addr)] if isinstance(addr, str) else []
  return []


def json_docs(text):
  """The JSON in a saved tool result: the whole text, or one document per line."""
  try:
    return [json.loads(text)]
  except ValueError:
    docs = []
    for line in text.splitlines():
      try:
        docs.append(json.loads(line))
      except ValueError:
        pass
    return docs


def connector_messages(obj, out):
  """Every message in Gmail connector JSON as (id, sender, to, cc, labels), however it's nested.

  A message is a dict with a from (or sender) and a to or cc, or a Gmail API message with
  payload.headers. Strings that hold JSON (a tool result's text) are read too.
  """
  if isinstance(obj, str):
    t = obj.strip()
    if t[:1] in "{[":
      for doc in json_docs(t):
        connector_messages(doc, out)
    return
  if isinstance(obj, list):
    for v in obj:
      connector_messages(v, out)
    return
  if not isinstance(obj, dict):
    return
  low = {k.lower(): v for k, v in obj.items()}
  if "messages" not in low:
    h = pa.headers(obj) if isinstance(obj.get("payload"), dict) else {}
    sender = low.get("from") or low.get("sender") or h.get("from")
    to = low.get("to") or low.get("torecipients") or h.get("to")
    cc = low.get("cc") or low.get("ccrecipients") or h.get("cc")
    if sender and (to or cc):
      labels = low.get("labelids") or low.get("labels") or []
      out.append((low.get("id") or low.get("messageid"), sender, to, cc, labels))
      return
  for v in obj.values():
    connector_messages(v, out)


def threads_json_recipients(path):
  """One list of (display, address) per message from Ian in a saved connector result."""
  try:
    with open(path, encoding="utf-8") as f:
      text = f.read()
  except OSError as e:
    pa.die(f"can't read --threads-json {path}: {e.strerror}")
  found = []
  for doc in json_docs(text):
    connector_messages(doc, found)
  out, seen = [], set()
  for mid, sender, to, cc, labels in found:
    if mid and mid in seen:
      continue
    seen.add(mid)
    mine = any(a.lower() in pa.IAN_ADDRESSES for _, a in addresses_in(sender))
    if mine or (isinstance(labels, list) and "SENT" in labels):
      out.append(addresses_in(to) + addresses_in(cc))
  if not out:
    print(f"# no messages from Ian in {path} ({len(found)} message(s) in all): is it search_threads or "
          "get_thread output?", file=sys.stderr)
  return out


def gog_failed(mailbox, why):
  pa.die(f"gog couldn't read the {mailbox} mailbox's sent mail ({why}), so nothing was listed. Check gog can "
         f"read it (the mail skill's Mailboxes setup), or rerun without `--gog {mailbox}` and say in the "
         "report that its correspondents weren't looked up.")


def cmd_correspondents(args):
  messages = []  # (mailbox, [(display, address)]) per sent message
  for mb in args.gog or []:
    try:
      messages += [(mb, r) for r in sent_recipients(mb, args.since or last_sync())]
    except pa.GogError as e:
      detail = str(e).split(": ", 1)[-1].strip()  # GogError is "<command>: <what gog said>"
      gog_failed(mb, (detail.splitlines() or ["no output"])[-1][:300])
    except FileNotFoundError:
      gog_failed(mb, f"no {pa.GOG} command")
    except OSError as e:
      gog_failed(mb, f"{pa.GOG}: {e.strerror}")
    except subprocess.TimeoutExpired:
      gog_failed(mb, "it took more than 2 minutes")
    except (ValueError, KeyError, TypeError, AttributeError) as e:
      gog_failed(mb, f"output not understood: {type(e).__name__} {e}")
  for path in args.threads_json or []:
    messages += [(args.stdin_mailbox, r) for r in threads_json_recipients(path)]
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
  save_queue(CORRESPONDENTS_QUEUE, args.max, [(r[1], r[2]) for r in rows])
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


def save_queue(path, cap, rows):
  """The queue as printed (key<TAB>name), so `log` and `defer --rest` know who is left."""
  os.makedirs(STATE, exist_ok=True)
  with open(path, "w", encoding="utf-8") as f:
    f.write(f"# {utc_now()} max {cap}\n")
    f.writelines(f"{k}\t{' '.join(n.split())}\n" for k, n in rows)


def read_queue(path):
  """(time, max, [(key, name)]) of a saved queue; ("", 0, []) if there's none or it's stale."""
  try:
    with open(path, encoding="utf-8") as f:
      lines = f.read().splitlines()
  except OSError:
    return "", 0, []
  m = re.match(r"# (\S+) max (\d+)", lines[0] if lines else "")
  if not m or time.time() - os.path.getmtime(path) > QUEUE_MAX_AGE:
    return "", 0, []
  rows = [tuple((l.split("\t") + [""])[:2]) for l in lines[1:] if l and not l.startswith("#")]
  return m.group(1), int(m.group(2)), rows


def log_lines(path):
  try:
    with open(path, encoding="utf-8") as f:
      return [l.rstrip("\n").split("\t") for l in f if l.count("\t") >= 2]
  except OSError:
    return []


def remaining(email_mode):
  """The saved queue's people with no log line (other than deferred) since it was made."""
  at, cap, rows = read_queue(CORRESPONDENTS_QUEUE if email_mode else QUEUE)
  if not at:
    return [], 0, ""
  tried = {p[2].lower() for p in log_lines(CORRESPONDENTS_LOG if email_mode else LOG)
           if p[0] >= at and p[1] != "deferred"}
  return [(k, n) for k, n in rows if k.lower() not in tried], cap, at


def recent_statuses(path):
  """The statuses of the last RECENT_HOURS, oldest first, without deferred lines."""
  since = (datetime.datetime.now(datetime.timezone.utc)
           - datetime.timedelta(hours=RECENT_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
  return [p[1] for p in log_lines(path) if p[0] >= since and p[1] != "deferred"]


def invite_signal(email_mode):
  """STOP or BUDGET after an invitation result, with the people left to defer."""
  st = recent_statuses(LOG)
  last = st[-1] if st else ""
  if last == "limit":
    say = "STOP limit: LinkedIn's invitation limit: no more invitations this run (steps 3b, 4 and 5)"
  elif last == "unexpected":
    say = ("STOP unexpected: take a screenshot, send no more invitations this run (steps 3b, 4 and 5), "
           "and tell Ian what the page shows")
  elif last == "error":
    say = ("STOP error: not a profile page (signed out, or a security check?): take a screenshot and send "
           "no more invitations this run")
  elif st[-3:] == ["not-profile"] * 3:
    say = ("STOP not-profile: three profiles in a row didn't load as profiles: take a screenshot and send no "
           "more invitations this run, as for error")
  else:
    say = ""
    if not email_mode:
      left, cap, at = remaining(False)
      sent = sum(1 for p in log_lines(LOG) if at and p[0] >= at and p[1] == "sent")
      if at and sent >= cap and left:
        say = f"BUDGET: {sent} sent since the queue was made, its --max {cap}: stop sending"
  if not say:
    return
  print(say)
  left, _, _ = remaining(email_mode)
  rest = "defer --email --rest" if email_mode else "defer --rest"
  if left:
    print(f"# not yet tried ({len(left)}): `{rest}` logs them as deferred for the next run")
    for k, n in left:
      print(f"{k}\t{n}")
  else:
    print("# nobody left in the queue to defer")


def follow_signal():
  st = recent_statuses(FOLLOWS_LOG)
  last = st[-1] if st else ""
  if last == "limit":
    print("STOP limit: LinkedIn won't take more follows: stop following (the next run picks the rest up)")
  elif last in ("unexpected", "error"):
    print(f"STOP {last}: take a screenshot, stop following, and tell Ian what the page shows")
  elif st[-3:] == ["missing"] * 3:
    print("RERUN: three missing in a row: run extract-followers.js again, then `follows --from-download` "
          "for a fresh queue (after a second RERUN, stop following and say so)")


def cmd_log(args):
  if args.email:
    if args.status not in CORRESPONDENT_STATUSES:
      pa.die(f"--email status must be one of {', '.join(CORRESPONDENT_STATUSES)}", 2)
    os.makedirs(STATE, exist_ok=True)
    with open(CORRESPONDENTS_LOG, "a", encoding="utf-8") as f:
      f.write(f"{utc_now()}\t{args.status}\t{args.email.lower()}\t{' '.join(args.name.split())}\t{args.url}\n")
    invite = args.status in INVITE_STATUSES and args.status != "deferred" and "/in/" in args.url
    if invite:
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
  if args.follows:
    follow_signal()
  elif args.status != "deferred" and (not args.email or invite):
    invite_signal(bool(args.email))


def cmd_defer(args):
  n = 0
  os.makedirs(STATE, exist_ok=True)
  if args.rest:
    left, _, _ = remaining(args.email)
    lines = ["\t".join(r) for r in left]
    try:
      os.remove(CORRESPONDENTS_QUEUE if args.email else QUEUE)
    except OSError:
      pass
  else:
    lines = sys.stdin
  for line in lines:
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


def calendar_events(obj, out):
  """Every event (a dict with attendees) in saved list_events JSON, however it's nested."""
  if isinstance(obj, str):
    t = obj.strip()
    if t[:1] in "{[":
      for doc in json_docs(t):
        calendar_events(doc, out)
  elif isinstance(obj, list):
    for v in obj:
      calendar_events(v, out)
  elif isinstance(obj, dict):
    if isinstance(obj.get("attendees"), list) and ("start" in obj or "summary" in obj):
      out.append(obj)
    else:
      for v in obj.values():
        calendar_events(v, out)


def event_date(ev):
  start = ev.get("start")
  if isinstance(start, dict):
    start = start.get("dateTime") or start.get("date")
  return str(start or "")[:10]


def attendee_match(name, attendee):
  """Is this attendee the person: their display name, or first.last@, flast@, firstlast@ (and _ or -)."""
  want = name_tokens(name)
  if len(want) < 2 or not isinstance(attendee, dict):
    return False
  got = name_tokens(attendee.get("displayName") or attendee.get("name") or "")
  if got and got[0] == want[0] and got[-1] == want[-1]:
    return True
  local = (attendee.get("email") or "").split("@")[0].lower()
  first, last = want[0], want[-1]
  return local in {f"{first}.{last}", f"{first}_{last}", f"{first}-{last}", f"{first}{last}", f"{first[0]}{last}"}


def read_attendees(path):
  """{lower-case name: (count, last)} from calendar-events.py attendees output, as text
  ("Jane Doe: 2 event(s), last Tue 20 Oct 2026 "Title" (W), via ...") or --json."""
  out = {}
  try:
    with open(path, encoding="utf-8") as f:
      text = f.read()
  except OSError as e:
    pa.die(f"can't read --attendees {path}: {e.strerror}")
  try:
    rows = json.loads(text)
  except ValueError:
    rows = None
  if isinstance(rows, list):
    for r in rows:
      if isinstance(r, dict) and r.get("name"):
        last = r.get("last") or {}
        what = " ".join(x for x in (last.get("date"), f'"{last["title"]}"' if last.get("title") else "") if x)
        out[r["name"].lower()] = (int(r.get("count") or 0), what)
    return out
  for line in text.splitlines():
    m = re.match(r"\s*([^:\t#]+?)\s*(?::|\t)\s*(\d+)\b(.*)$", line)
    if m:
      last = re.search(r"\blast (.+?)(?:, next |, via |$)", m.group(3))
      out[m.group(1).lower()] = (int(m.group(2)), last.group(1).strip() if last else "")
  return out


def cmd_evidence(args):
  events = []
  for path in args.events or []:
    try:
      with open(path, encoding="utf-8") as f:
        text = f.read()
    except OSError as e:
      pa.die(f"can't read --events {path}: {e.strerror}")
    for doc in json_docs(text):
      calendar_events(doc, events)
    if not events:
      print(f"# no events with attendees in {path}: is it list_events output?", file=sys.stderr)
  attendees = {}
  for path in args.attendees or []:
    attendees.update(read_attendees(path))
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
    cal = []
    for e in sorted(events, key=event_date, reverse=True):
      if any(attendee_match(name, a) and (a.get("responseStatus") != "declined") for a in e["attendees"]):
        cal.append(f"calendar: {' '.join((e.get('summary') or '(no title)').split())} {event_date(e)}")
    count, last = attendees.get(key, (0, ""))
    if count:
      cal.insert(0, f"calendar: {count} event(s)" + (f", last {last}" if last else ""))
    level = "met" if met or cal else "in-touch" if mentioned else "forgotten?"
    ev = cal[:2] + [f"meetings/{f}" for f in met[:3]] + [f"people/{f}" for f in mentioned[:3]]
    print(f"{name}\t{level}\t{'; '.join(ev) or '-'}")


def cmd_mail_query(args):
  names = []
  for name, _ in people_in(sys.stdin.read()):
    name = " ".join(name.replace('"', "").split())
    if name and name not in names:
      names.append(name)
  for i in range(0, len(names), args.size):
    print(f"newer_than:{args.days}d (" + " OR ".join(f'"{n}"' for n in names[i:i + args.size]) + ")")


LEVEL_POINTS = {"close": 5, "met": 3, "in-touch": 2}
# What makes a post worth answering, besides who wrote it: (pattern, points, why); each counts once
FEED_SIGNALS = [
  (r"\b(passed away|rest in peace|\bRIP\b|funeral|cancer|diagnos|in hospital|grief|grieving|lost my)", 5, "hard news"),
  (r"(\bopen to work\b|laid off|made redundant|redundanc|looking for (my|a) (next|new) (role|job|opportunity)"
   r"|rejection)", 4, "looking for work"),
  (r"(starting a new position|started a new position|job update|new (role|job|chapter|position)|i('ve| have) joined"
   r"|joined .{0,40}\bas\b|\bpromoted\b|\bnew challenge|my last day|leaving .{0,30}after)", 4, "new job"),
  (r"\b(launch|launched|released|is here|is out|published|my (new )?book|raised|funding round|series [abc]\b"
   r"|crossed [\d,]+|award|we won|i won|acquired by|been acquired)", 3, "launch or achievement"),
  (r"(years in business|anniversary|\bturned \d+|birthday|graduated|\d+ years of|celebrat|wedding|married"
   r"|new baby|born)", 2, "milestone"),
  (r"\b(speaking at|to speak at|keynote|co-chair|my talk|giving a talk|on stage)", 1, "speaking"),
  (r"\b(hiring|we're looking for|job opening|open role)", 1, "hiring"),
]


def linkedin_slug(url):
  m = re.search(r"linkedin\.com/in/([^/?#\s)]+)", url or "")
  return urllib.parse.unquote(m.group(1)).strip("\u200b").lower() if m else None


def people_by_linkedin():
  """{slug: (file, name, level)} from the `- LinkedIn:` lines (or any profile link) in people/."""
  out, people_dir = {}, os.path.join(pa.GTD, "people")
  for f in sorted(os.listdir(people_dir)) if os.path.isdir(people_dir) else []:
    if not f.endswith(".md"):
      continue
    with open(os.path.join(people_dir, f), encoding="utf-8", errors="replace") as fh:
      text = fh.read()
    level = (re.search(r"^- Level:\s*(\S+)", text, re.M) or [None, ""])[1].lower()
    # The first heading that is a name, not a section ("## managed by linkedin_tools", "## LinkedIn messages")
    name = next((h.strip() for h in re.findall(r"^#+ (.+)$", text, re.M)
                 if not re.match(r"(managed by|linkedin messages|messages|notes|meetings?|log)\b", h.strip(), re.I)),
                f[:-3].replace("_", " "))
    for url in re.findall(r"https?://(?:[a-z]+\.)?linkedin\.com/in/[^/?#\s)]+", text):
      out.setdefault(linkedin_slug(url), (f, name, level))
  return out


def popularity(post):
  """Points for reactions, comments and reposts: comments weigh most, as they're conversations."""
  n = post.get("reactions", 0) + 3 * post.get("comments", 0) + 2 * post.get("reposts", 0)
  return 0.0 if n < 30 else min(5.0, round(1.8 * math.log10(n) - 1.6, 1))


def score_post(post, person):
  level = person[2] if person else ""
  why, score = [], LEVEL_POINTS.get(level, 0)
  if score:
    why.append(level)
  # The words that are the author's own: a reshare carries the other post after its author's
  # "Jane Doe • 2nd" header, and that post's news isn't theirs
  own = re.split(r"\s•\s*(?:1st|2nd|3rd\+?|Following)\b", post.get("text", ""), maxsplit=1)[0]
  words = " ".join(["open to work" if post.get("openToWork") else "", own[:400]])
  for pattern, points, label in FEED_SIGNALS:
    if re.search(pattern, words, re.I):
      score += points
      why.append(label)
  pop = popularity(post)
  if pop:
    score += pop
  if pop or post.get("comments"):
    why.append(f"{post.get('reactions', 0)} reactions, {post.get('comments', 0)} comments")
  return round(score, 1), why


def cmd_feed(args):
  posts = page_rows(args, "feed")
  people = people_by_linkedin()
  best = {}
  for post in posts:
    slug = linkedin_slug(post.get("url"))
    if not slug:
      continue
    person = people.get(slug)
    score, why = score_post(post, person)
    if score >= args.min and (slug not in best or score > best[slug][0]):
      # The name as the feed shows it (the person's own), without emoji or badges
      name = re.sub(r"^[^\w(]+|,\s*Open to work$", "", post.get("name", "")).strip() or (person or ["", "?"])[1]
      best[slug] = (score, name, (person[2] if person else "") or "-", "; ".join(why), post.get("age", ""),
                    post.get("postUrl") or
                    f"https://www.linkedin.com/in/{post['url'].rstrip('/').split('/in/')[1]}/recent-activity/all/",
                    re.sub(r"\s+", " ", post.get("text", ""))[:200], (person or [""])[0])
  order = sorted(best.values(), key=lambda r: -r[0])[:args.max]
  print(f"# {len(posts)} post(s) read, {len(best)} scoring {args.min:g} or more, showing {len(order)}")
  for r in order:
    print("\t".join([f"{r[0]:g}", *r[1:7]]))


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  sub.add_parser("window")
  p = sub.add_parser("budget")
  p.add_argument("--per-day", type=int, default=20)
  p.add_argument("--per-week", type=int, default=150)
  def from_download(p, kind):
    p.add_argument("--from-download", nargs="?", const=kind, metavar="KIND",
                   help=f"read the newest pa-linkedin-{kind}-*.json download, not stdin")
    p.add_argument("--wait", type=float, default=10, help="seconds to wait for the download (10)")

  p = sub.add_parser("queue")
  p.add_argument("--max", type=int, default=20)
  from_download(p, "viewers")
  p = sub.add_parser("log")
  p.add_argument("--follows", action="store_true", help="a follow-follower.js result, to the follows log")
  p.add_argument("--email", help="a step 3b result for this address, to the correspondents log")
  p.add_argument("status")
  p.add_argument("url")
  p.add_argument("name", nargs="?", default="")
  from_download(sub.add_parser("suggestions"), "suggestions")
  p = sub.add_parser("follows")
  p.add_argument("--per-day", type=int, default=25)
  from_download(p, "followers")
  p = sub.add_parser("connections")
  p.add_argument("out", nargs="?", help="default $TMPDIR/linkedin-connections-<YYYYMMDD>.json")
  from_download(p, "connections")
  p = sub.add_parser("export")
  p.add_argument("--import", dest="do_import", action="store_true",
                 help="with ACTION import, run gtd import-connections --auto on the zip")
  p = sub.add_parser("defer")
  p.add_argument("--email", action="store_true", help="correspondents lines (email<TAB>name...)")
  p.add_argument("--rest", action="store_true", help="the saved queue's people not yet tried, not stdin")
  p = sub.add_parser("correspondents")
  p.add_argument("--gog", action="append", choices=["work", "personal"], help="read this mailbox's sent mail")
  p.add_argument("--stdin-mailbox", choices=["work", "personal"], default="work",
                 help="the mailbox the stdin lines come from (default work: the Gmail connector)")
  p.add_argument("--since", help="UTC time, as linkedin-sync-last (default LAST)")
  p.add_argument("--max", type=int, default=20)
  p.add_argument("--max-recipients", type=int, default=8)
  p.add_argument("--threads-json", action="append", metavar="FILE",
                 help="saved Gmail connector search_threads/get_thread JSON (counts as --stdin-mailbox)")
  p = sub.add_parser("match")
  p.add_argument("name")
  p.add_argument("--company", default="")
  p = sub.add_parser("done")
  p.add_argument("now")
  p = sub.add_parser("evidence")
  p.add_argument("--days", type=int, default=30)
  p.add_argument("--events", action="append", metavar="FILE", help="saved calendar list_events JSON")
  p.add_argument("--attendees", action="append", metavar="FILE", help="calendar-events.py attendees output")
  p = sub.add_parser("mail-query")
  p.add_argument("--days", type=int, default=30)
  p.add_argument("--size", type=int, default=10, help="names to a query (10)")
  p = sub.add_parser("feed")
  p.add_argument("--min", type=float, default=3.5, help="the lowest score shown")
  p.add_argument("--max", type=int, default=15)
  from_download(p, "feed")
  args = ap.parse_args()
  {"window": cmd_window, "budget": cmd_budget, "queue": cmd_queue, "suggestions": cmd_suggestions, "log": cmd_log, "defer": cmd_defer,
   "done": cmd_done, "evidence": cmd_evidence, "connections": cmd_connections, "export": cmd_export,
   "follows": cmd_follows, "correspondents": cmd_correspondents, "match": cmd_match,
   "feed": cmd_feed, "mail-query": cmd_mail_query}[args.cmd](args)


if __name__ == "__main__":
  main()
