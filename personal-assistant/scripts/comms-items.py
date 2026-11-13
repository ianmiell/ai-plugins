#!/usr/bin/env python3
"""The triage list's ledger: numbers items, prints the tables, turns Ian's answer into actions.

  comms-items.py add --reset <<'EOF'
  {"bucket": "act", "ch": "W✉+S", "who": "Jane Doe (Acme), Contract renewal", "what": "Wants sign-off by Fri", "tags": "🗂 → new task", "rec": "Draft asking for the redline; 👀 on the ping", "go": ["draft", "task", "react"], "mail": [3], "slack": ["https://containersolutions.slack.com/archives/D1/p1794300000000100"], "draft": "Jane - can you send the redline? Ian", "task": "CS: Sign off Acme renewal"}
  {"bucket": "fyi", "ch": "P✉", "who": "GitHub", "what": "Notifications", "rec": "Archive", "go": ["archive"], "mail": [7, 8, 9], "group": "notifications"}
  EOF
  comms-items.py render                 # the /comms tables, numbered across every channel
  comms-items.py render --mail          # the /mail layout: work, then personal
  comms-items.py expand "go except 5, archive 8–14, 2: say I'll call tonight"
  comms-items.py show 3 7-9             # what a number stands for (ids, draft, task)
  comms-items.py next                   # the command for each mailbox's next batch
  comms-items.py notify --failed slack  # the morning run's one-line notification

`add` reads one JSON object per line (stdin or a file). Fields:
  bucket   instructions, act, waiting, schedule, apps, delegate, ack, later, fyi, junk,
           suspicious (or their headings: "Act now", "Read later", "FYI / done", ...)
  ch       channel tag(s): W✉ P✉ S WA LI "📅 W" "📅 P" "🔑 W" "🔑 P", "W✉+S" or a list
  who, what, tags, rec      the table's cells (one line each)
  go       what "go" does for this item: archive, keep, trash, spam, label:<Name>, draft,
           task, note, react[:emoji], accept, decline, tentative, add, keep-app (never cut:
           an app is only cut when Ian names it). Missing: from the bucket (fyi archive,
           junk trash, later keep, suspicious spam, act/delegate draft when there's a draft)
  mail     the item's threads: mail-gather.py list numbers (3), "personal 1a2b...",
           ["work", "1a2b..."] or {"mailbox": ..., "thread": ...}. Every W✉/P✉ item needs one.
  slack    message links; whatsapp: the chat; linkedin: the conversation or post;
           event: the calendar event; app: the Google app's name
  draft    the proposed reply text; task: an existing task number, or a new task's subject
  when     ISO date or epoch, oldest first within a bucket; group: rows with the same group
           in a bucket share one row with a range (11–17)
All lines are checked first; if any is wrong nothing is added. A ledger left over from more
than 12 hours ago, or --reset, starts a new one.

`render` numbers the new items after the ones already shown (so a next batch carries on
from the last number), in bucket order (Instructions from Ian, Act now, Waiting on Ian,
Schedule, Google apps, Delegate, Acknowledge, Read later, FYI / done, Junk, Suspicious), then
channel order, then oldest first, and prints the bold header and the markdown tables as the
comms skill shows them. --mail numbers and shows work, then personal, as the mail skill does.
It records which threads were shown (PA_STATE/comms-shown.tsv, for the next batch).

`expand` reads Ian's answer: go / yes / ok (all), go 1 3, except / skip / leave N, archive,
keep, star, unstar, trash, spam, label <Name>, draft, task, note, react / 👀 / ✅ / 👍, accept,
decline, tentative, add, cut, numbers as 7, 7-14, 7–14, 3,5 and "the rest", and `N: free
text` for an instruction about one item. An explicit word for an item replaces what "go"
would do for it. It prints the mail-apply.py plan (with a `keep` for every shown thread
that stays in the inbox, rules/star-processed-inbox.md) and saves it in
PA_STATE/comms-mail-plan.txt, the connector steps for work mail on the MacBook Pro, then
the drafts, Slack, WhatsApp, LinkedIn, calendar, gtd and Google apps steps. Words it doesn't
know are printed as not understood and nothing is saved (exit 1): ask Ian, never guess.

`notify` builds the morning run's message (under 200 characters, one line) from the
counts and the first Act now item, sends it with pa-notify.py, and prints it for
PushNotification. --dry-run only prints it.
"""

import argparse
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
STALE = 12 * 3600

BUCKETS = [
  ("instructions", "Instructions from Ian"), ("act", "Act now"), ("waiting", "Waiting on Ian"),
  ("schedule", "Schedule"), ("apps", "Google apps"), ("delegate", "Delegate"),
  ("ack", "Acknowledge"), ("later", "Read later"), ("fyi", "FYI / done"), ("junk", "Junk"),
  ("suspicious", "Suspicious"),
]
HEADING = dict(BUCKETS)
SHARED = ("later", "fyi", "junk")  # small buckets that share one table
BUCKET_ALIASES = {
  "instructions from ian": "instructions", "instruction": "instructions", "ai": "instructions",
  "act now": "act", "waiting on ian": "waiting", "waiting on you": "waiting",
  "google apps": "apps", "app": "apps", "acknowledge": "ack", "read later": "later",
  "fyi / done": "fyi", "fyi/done": "fyi", "done": "fyi", "noise": "fyi",
  "unsubscribe / junk": "junk", "unsubscribe": "junk",
}
CHANNELS = ["W✉", "P✉", "S", "WA", "LI", "📅 W", "📅 P", "🔑 W", "🔑 P"]
CH_ALIASES = {
  "w✉": "W✉", "w": "W✉", "work": "W✉", "work-mail": "W✉", "wm": "W✉",
  "p✉": "P✉", "p": "P✉", "personal": "P✉", "personal-mail": "P✉", "pm": "P✉",
  "s": "S", "slack": "S", "wa": "WA", "whatsapp": "WA", "li": "LI", "linkedin": "LI",
  "📅w": "📅 W", "📅 w": "📅 W", "invites-work": "📅 W", "cal w": "📅 W",
  "📅p": "📅 P", "📅 p": "📅 P", "invites-personal": "📅 P", "cal p": "📅 P",
  "🔑w": "🔑 W", "🔑 w": "🔑 W", "apps-work": "🔑 W", "🔑p": "🔑 P", "🔑 p": "🔑 P", "apps-personal": "🔑 P",
}
MAIL_TAG = {"work": "W✉", "personal": "P✉"}
MAIL_MOVES = ("archive", "keep", "trash", "spam", "unstar")
ACTIONS = set(MAIL_MOVES) | {"label", "draft", "task", "note", "react", "accept", "decline", "tentative",
                              "add", "cut", "keep-app", "none"}
DEFAULT_GO = {"fyi": ["archive"], "junk": ["trash"], "later": ["keep"], "suspicious": ["spam"]}

VERBS = {
  "archive": "archive", "keep": "keep", "star": "keep", "unstar": "unstar", "trash": "trash",
  "delete": "trash", "bin": "trash", "spam": "spam", "draft": "draft", "reply": "draft",
  "drafts": "draft", "task": "task", "tasks": "task", "note": "note", "react": "react",
  "ack": "react", "👀": "react:eyes", "✅": "react:white_check_mark", "👍": "react:+1",
  "accept": "accept", "decline": "decline", "tentative": "tentative", "maybe": "tentative",
  "add": "add", "cut": "cut", "remove": "cut", "label": "label",
  "skip": "none", "leave": "none", "ignore": "none", "except": "none", "not": "none",
  "but not": "none", "apart from": "none", "nothing for": "none", "no": "none",
}
GO_WORDS = ("go", "yes", "ok", "okay", "approve", "approved", "do it", "go ahead", "all", "yes all",
            "go all", "as proposed", "fine", "agreed", "sure", "yep", "yup", "do all", "all of it")
REST = ("the rest", "rest", "others", "the others", "all others", "everything else", "all the rest")


def state_path(name):
  return os.path.join(pa.STATE, name)


LEDGER = "comms-items.json"


def load():
  try:
    with open(state_path(LEDGER), encoding="utf-8") as f:
      return json.load(f)
  except (OSError, ValueError):
    return None


def new_ledger():
  return {"made": int(time.time()), "touched": int(time.time()), "items": [], "batches": []}


def save(led):
  led["touched"] = int(time.time())
  os.makedirs(pa.STATE, exist_ok=True)
  tmp = state_path(LEDGER + ".tmp")
  with open(tmp, "w", encoding="utf-8") as f:
    json.dump(led, f, ensure_ascii=False, indent=1)
  os.replace(tmp, state_path(LEDGER))


def need():
  led = load()
  if not led or not led.get("items"):
    pa.die("no items: add them first with `comms-items.py add`", 2)
  return led


def one_line(text):
  return " ".join(str(text or "").split())


def cell(text):
  return one_line(text).replace("|", "\\|")


# ── add ──────────────────────────────────────────────────────────────────────────────────

def gathered():
  """{n: (mailbox, thread, from, subject)} from the last mail-gather.py list."""
  try:
    with open(state_path("mail-gather-last.json"), encoding="utf-8") as f:
      boxes = json.load(f)
  except (OSError, ValueError):
    return {}
  out = {}
  for b in boxes:
    for t in b.get("threads", []):
      out[t["n"]] = (b["mailbox"], t["thread"], t.get("from", ""), t.get("subject", ""))
  return out


def norm_channels(ch):
  parts = ch if isinstance(ch, list) else re.split(r"\s*\+\s*", str(ch or "").strip())
  out = []
  for p in parts:
    p = str(p).strip()
    if not p:
      continue
    tag = p if p in CHANNELS else CH_ALIASES.get(p.lower())
    if not tag:
      raise ValueError(f"unknown channel {p!r} (use {' '.join(CHANNELS)})")
    if tag not in out:
      out.append(tag)
  return out


def norm_mail(raw, gat):
  if raw is None:
    return []
  if isinstance(raw, (int, str, dict)) or (isinstance(raw, list) and len(raw) == 2 and raw[0] in pa.MAILBOXES
                                           and isinstance(raw[1], str) and not raw[1].isdigit()):
    raw = [raw]
  out = []
  for r in raw:
    if isinstance(r, int) or (isinstance(r, str) and r.strip().isdigit()):
      n = int(r)
      if n not in gat:
        raise ValueError(f"mail {n}: not a number in the last mail-gather.py list")
      out.append([gat[n][0], gat[n][1]])
    elif isinstance(r, dict):
      if r.get("mailbox") not in pa.MAILBOXES or not r.get("thread"):
        raise ValueError(f"mail {r}: want mailbox (work/personal) and thread")
      out.append([r["mailbox"], str(r["thread"])])
    elif isinstance(r, (list, tuple)) and len(r) == 2 and r[0] in pa.MAILBOXES:
      out.append([r[0], str(r[1])])
    elif isinstance(r, str) and len(r.split()) == 2 and r.split()[0] in pa.MAILBOXES:
      out.append(r.split())
    else:
      raise ValueError(f"mail {r!r}: give a list number, 'mailbox threadId' or [mailbox, threadId]")
  return out


def norm_go(go):
  out = []
  for g in go if isinstance(go, list) else [go]:
    g = str(g).strip()
    base = g.split(":")[0].lower()
    if base not in ACTIONS:
      raise ValueError(f"go {g!r}: not one of {', '.join(sorted(ACTIONS))}")
    if base == "cut":
      raise ValueError("go can't cut a Google app: only Ian naming it does (cut N)")
    out.append(g if ":" in g else base)
  return out


def parse_when(w):
  if w in (None, ""):
    return None
  if isinstance(w, (int, float)) or re.fullmatch(r"\d+(\.\d+)?", str(w)):
    return float(w) / (1000 if float(w) > 1e11 else 1)
  try:
    return datetime.datetime.fromisoformat(str(w)).timestamp()
  except ValueError:
    raise ValueError(f"when {w!r}: give an ISO date or epoch")


def normalise(obj, gat):
  if not isinstance(obj, dict):
    raise ValueError("not a JSON object")
  b = str(obj.get("bucket", "")).strip().lower()
  b = BUCKET_ALIASES.get(b, b)
  if b not in HEADING:
    raise ValueError(f"bucket {obj.get('bucket')!r}: use {', '.join(HEADING)}")
  it = {"bucket": b}
  it["mail"] = norm_mail(obj.get("mail", obj.get("thread") and [obj.get("mailbox"), obj.get("thread")]), gat)
  ch = norm_channels(obj.get("ch") or obj.get("channel") or [])
  for mb, _ in it["mail"]:
    if MAIL_TAG[mb] not in ch:
      ch.append(MAIL_TAG[mb])
  if not ch:
    raise ValueError("no channel (ch)")
  for tag in ("W✉", "P✉"):
    box = "work" if tag == "W✉" else "personal"
    if tag in ch and not any(mb == box for mb, _ in it["mail"]):
      raise ValueError(f"{tag} item without a {box} thread in mail")
  it["ch"] = ch
  first = next((gat[n] for n in ([obj["mail"]] if isinstance(obj.get("mail"), int) else obj.get("mail") or [])
                if isinstance(n, int) and n in gat), None)
  it["who"] = one_line(obj.get("who") or (first and re.sub(r"\s*<[^>]*>", "", first[2])) or "")
  it["what"] = one_line(obj.get("what") or (first and first[3]) or "")
  if not it["who"] and not it["what"]:
    raise ValueError("needs who or what")
  for k in ("tags", "rec", "group", "draft", "whatsapp", "linkedin", "event", "app", "reply_on"):
    if obj.get(k) not in (None, ""):
      it[k] = obj[k] if k == "draft" else one_line(obj[k]) if isinstance(obj[k], str) else obj[k]
  sl = obj.get("slack")
  it["slack"] = [sl] if isinstance(sl, str) else list(sl or [])
  if obj.get("task") not in (None, ""):
    t = obj["task"]
    it["task"] = int(t) if isinstance(t, int) or str(t).isdigit() else one_line(t)
  it["when"] = parse_when(obj.get("when"))
  if "go" in obj:
    it["go"] = norm_go(obj["go"])
  else:
    it["go"] = list(DEFAULT_GO.get(b, []))
    if b in ("act", "delegate") and it.get("draft"):
      it["go"].append("draft")
  return it


def cmd_add(args):
  text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
  gat = gathered()
  items, errors = [], []
  for i, line in enumerate(text.splitlines(), 1):
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("//"):
      continue
    try:
      items.append(normalise(json.loads(line), gat))
    except ValueError as e:
      errors.append(f"line {i}: {e}")
  if errors:
    print("\n".join(errors))
    print("nothing added: fix those lines and add them all again")
    sys.exit(2)
  led = load()
  fresh = args.reset or not led or time.time() - led.get("touched", 0) > STALE
  if fresh:
    led = new_ledger()
  base = len(led["items"])
  for k, it in enumerate(items):
    it["idx"] = base + k
    it["n"] = None
  led["items"] += items
  save(led)
  pending = sum(1 for it in led["items"] if it["n"] is None)
  print(f"added {len(items)} item(s){' to a new ledger' if fresh else ''}; {pending} waiting for `render`")


# ── render ───────────────────────────────────────────────────────────────────────────────

def ch_rank(it):
  return min(CHANNELS.index(c) for c in it["ch"])


PEOPLE_BUCKETS = ("act", "waiting", "schedule", "delegate", "ack", "suspicious")


def sort_key(it, mail_mode):
  """Display order: (mail: work, then personal), bucket, then people waiting longest first in
  the buckets about people, channel and group elsewhere."""
  box = 0
  if mail_mode and it["bucket"] != "instructions":
    box = 1 if any(mb == "work" for mb, _ in it["mail"]) else 2
  when = it["when"] if it["when"] is not None else float("inf")
  inner = ((when, ch_rank(it)) if it["bucket"] in PEOPLE_BUCKETS else (ch_rank(it), it.get("group") or "", when))
  return (box, [b for b, _ in BUCKETS].index(it["bucket"])) + inner + (it["idx"],)


def rows(items):
  """Items grouped into table rows: consecutive items with one group share a row."""
  out = []
  for it in items:
    if out and it.get("group") and out[-1][0].get("group") == it["group"] and out[-1][0]["bucket"] == it["bucket"]:
      out[-1].append(it)
    else:
      out.append([it])
  return out


def num_cell(group):
  a, b = group[0]["n"], group[-1]["n"]
  return str(a) if a == b else f"{a}–{b}"


def row_cells(group, with_ch=True):
  it = group[0]
  chs = []
  for g in group:
    for c in g["ch"]:
      if c not in chs:
        chs.append(c)
  whos = list(dict.fromkeys(g["who"] for g in group if g["who"]))
  who = whos[0] if len(whos) == 1 else ", ".join(whos[:3]) + (", …" if len(whos) > 3 else "")
  cells = [num_cell(group)] + (["+".join(chs)] if with_ch else []) + [who, it["what"], it.get("tags", ""),
                                                                       it.get("rec", "")]
  return "| " + " | ".join(cell(c) for c in cells) + " |"


def table(groups, with_ch=True):
  head = ["#"] + (["Ch"] if with_ch else []) + ["Who", "What", "Tags", "→"]
  lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
  return lines + [row_cells(g, with_ch) for g in groups]


def scope_info():
  try:
    with open(state_path("comms-scope.json"), encoding="utf-8") as f:
      s = json.load(f)
    if time.time() - s.get("made", 0) < STALE:
      return s
  except (OSError, ValueError):
    pass
  return None


def header(items):
  s = scope_info()
  counts = {c: 0 for c in CHANNELS}
  threads = {"work": 0, "personal": 0}
  for it in items:
    for c in it["ch"]:
      counts[c] += 1
    for mb, _ in it["mail"]:
      threads[mb] += 1
  parts = []
  inscope = set(s["tags"]) if s else set()
  for c in CHANNELS:
    if not counts[c] and c not in inscope:
      continue
    if c in ("W✉", "P✉"):
      parts.append(f"{c} {threads['work' if c == 'W✉' else 'personal']}")
    elif c in ("S", "WA"):
      w = (s or {}).get("windows", {}).get("slack" if c == "S" else "whatsapp")
      parts.append(f"{c} since {w['since']}" if w else f"{c} {counts[c]}")
    elif c.startswith("📅"):
      continue
    elif c.startswith("🔑"):
      continue
    else:
      parts.append(f"{c} {counts[c]}")
  inv = counts["📅 W"] + counts["📅 P"]
  if inv or {"📅 W", "📅 P"} & inscope:
    parts.append(f"📅 {inv} invite{'s' if inv != 1 else ''}")
  apps = counts["🔑 W"] + counts["🔑 P"]
  if apps or {"🔑 W", "🔑 P"} & inscope:
    parts.append(f"🔑 {apps} app{'s' if apps != 1 else ''}")
  return parts


def cmd_render(args):
  led = need()
  mail_mode = args.mail or led.get("mode") == "mail"
  led["mode"] = "mail" if mail_mode else "comms"
  new = [it for it in led["items"] if it["n"] is None]
  if new:
    start = max([it["n"] for it in led["items"] if it["n"] is not None] or [0]) + 1
    new.sort(key=lambda it: sort_key(it, mail_mode))
    for k, it in enumerate(new):
      it["n"] = start + k
    led["batches"].append({"rendered": int(time.time()), "numbers": [it["n"] for it in new]})
  batch = set(led["batches"][-1]["numbers"]) if led["batches"] else set()
  shown = sorted((it for it in led["items"] if it["n"] in batch or args.all), key=lambda it: it["n"])
  save(led)
  with open(state_path("comms-shown.tsv"), "w", encoding="utf-8") as f:
    for it in led["items"]:
      if it["n"] is not None:
        for mb, t in it["mail"]:
          f.write(f"{mb}\t{t}\n")
  print_tables(shown, mail_mode)


def print_tables(items, mail_mode):
  if not items:
    print("(nothing to show)")
    return
  out = []
  if mail_mode:
    out.append("**MAIL — " + " · ".join(p for p in header(items) if p.startswith(("W✉", "P✉"))) + "**")
  else:
    out.append("**COMMS — " + " · ".join(header(items)) + "**")
  out.append("")
  by_bucket = {}
  for it in items:
    by_bucket.setdefault(it["bucket"], []).append(it)
  instr = by_bucket.pop("instructions", [])
  if instr:
    out += [f"#### {HEADING['instructions']}", ""] + table(rows(instr), not mail_mode) + [""]
  if not by_bucket.get("act"):
    out += ["Nothing in Act now" + (" in either mailbox." if mail_mode else " on any channel."), ""]

  def buckets(its, level):
    bb = {}
    for it in its:
      bb.setdefault(it["bucket"], []).append(it)
    res, shared = [], [b for b in SHARED if b in bb]
    for b, _ in BUCKETS:
      if b == "instructions" or b not in bb:
        continue
      if b in SHARED:
        if b == shared[0]:  # one table for the small buckets, where the first of them goes
          title = " / ".join(HEADING[x].replace(" / done", "") if len(shared) > 1 else HEADING[x] for x in shared)
          res += [f"{level} {title}", ""] + table(rows([i for x in shared for i in bb[x]]), not mail_mode) + [""]
        continue
      res += [f"{level} {HEADING[b]}", ""] + table(rows(bb[b]), not mail_mode) + [""]
    return res

  rest = [it for it in items if it["bucket"] != "instructions"]
  if mail_mode:
    for box in ("work", "personal"):
      its = [it for it in rest if (1 if any(mb == "work" for mb, _ in it["mail"]) else 2) == (1 if box == "work" else 2)]
      if its:
        out += [f"### {box.upper()} ({pa.MAILBOXES[box]}) — {len(its)} thread(s)", ""] + buckets(its, "####")
  else:
    out += buckets(rest, "####")
  more = next_batches()
  if more:
    out.append("More mail after this batch in " + ", ".join(m for m, _ in more) + ": `comms-items.py next`.")
  print("\n".join(out).rstrip())


# ── expand ───────────────────────────────────────────────────────────────────────────────

NUM_RE = re.compile(r"#?(\d+)(?:\s*(?:-|–|—|to|\.\.)\s*#?(\d+))?")


FREE_RE = re.compile(r"^\s*#?\d+\s*(?:[-–]\s*\d+\s*)?:")


def split_clauses(reply):
  """[(clause, is free text)], split at commas, `and` and `then`, except that free text keeps
  its commas ("2: say yes, thanks") until what follows is `N:`, a word followed by numbers
  ("archive 8", "except 5", "label X 3", "trash the rest") or a go word, and a list of
  numbers stays with its word ("trash 3, 5", "draft 1 and 2")."""
  words = "|".join(re.escape(v) for v in sorted(VERBS, key=len, reverse=True))
  gos = "|".join(re.escape(g) for g in sorted(GO_WORDS, key=len, reverse=True))
  rest = "|".join(re.escape(r) for r in sorted(REST, key=len, reverse=True))
  starter = (r"(?=#?\d+\s*(?:[-–]\s*\d+\s*)?:"
             r"|(?:" + words + r")\s*(?:\S+\s+)?(?:#?\d|(?:" + rest + r")\b)"
             r"|(?:" + gos + r")\s*(?:$|[,;]|except\b|but\b|#?\d))")
  starts = re.compile(r"\s*" + starter, re.I)
  out = []
  for seg in re.split(r"[;\n]+", reply):
    parts = re.split(r"(,|\band\b|\bthen\b)", seg, flags=re.I)
    cur = parts[0]
    for sep, piece in zip(parts[1::2], parts[2::2]):
      free = bool(FREE_RE.match(cur))
      if not starts.match(piece) and (free or re.fullmatch(r"[\s#\d\-–—.]*|\s*to\s+\d+\s*", piece)):
        cur += sep + piece  # free text with a comma in it, or more numbers for the same word
      else:
        if cur.strip():
          out.append((cur.strip(), bool(FREE_RE.match(cur))))
        cur = piece
    if cur.strip():
      out.append((cur.strip(), bool(FREE_RE.match(cur))))
  return out


def numbers(text, known):
  """(set of numbers, text with them taken out). Ranges keep only numbers that exist."""
  found = set()
  for m in NUM_RE.finditer(text):
    a, b = int(m.group(1)), int(m.group(2) or m.group(1))
    found |= {n for n in range(min(a, b), max(a, b) + 1) if n in known or a == b}
  return found, NUM_RE.sub(" ", text)


def parse_reply(reply, known, batch):
  """{n: [actions]} explicit, set go, set rest-verbs, free {n: text}, not understood."""
  explicit, go, free, bad, rest_actions = {}, set(), {}, [], []
  for clause, is_free in split_clauses(reply):
    if is_free:
      m = re.match(r"^\s*(#?\d+(?:\s*[-–]\s*\d+)?)\s*:\s*(.*)$", clause, re.S)
      nums, _ = numbers(m.group(1), known)
      for n in nums:
        free[n] = m.group(2).strip()
      continue
    low = clause.lower().strip().rstrip(".!")
    rest = False
    for r in sorted(REST, key=len, reverse=True):
      if re.search(r"(?<!\w)" + re.escape(r) + r"(?!\w)", low):
        low = re.sub(r"(?<!\w)" + re.escape(r) + r"(?!\w)", " ", low)
        rest = True
        break
    orig_words = clause
    nums, words = numbers(low, known)
    words = " ".join(w for w in re.split(r"[\s,]+", words) if w and w not in ("and", "&", "to", "+"))
    # go [N...] [except N...]
    gm = re.match(r"^(" + "|".join(re.escape(g) for g in sorted(GO_WORDS, key=len, reverse=True)) + r")\b(.*)$", words)
    if gm and not rest:
      tail = gm.group(2).strip()
      if not tail:
        go |= nums or set(batch)
        continue
      em = re.match(r"^(except|but not|apart from|not|bar|excluding|skip|leave)\b(.*)$", tail)
      if em and not em.group(2).strip():
        # "go except 5": all, minus the numbers
        go |= set(batch)
        for n in nums:
          explicit.setdefault(n, []).append("none")
        continue
      bad.append(clause)
      continue
    verb = None
    for v in sorted(VERBS, key=len, reverse=True):
      if words == v or words.startswith(v + " ") or (not v.isascii() and words.startswith(v)):
        verb, arg = VERBS[v], words[len(v):].strip()
        break
    if verb is None:
      bad.append(clause)
      continue
    if verb == "label":
      lm = re.search(r"\blabel\s+(\S+)", orig_words, re.I)
      if not lm or lm.group(1).isdigit():
        bad.append(clause)
        continue
      verb, arg = "label:" + lm.group(1), ""
    elif verb == "react" and arg:
      emo = {"👀": "eyes", "✅": "white_check_mark", "👍": "+1"}.get(arg, arg.strip(":"))
      verb, arg = "react:" + emo, ""
    if arg:
      bad.append(clause)
      continue
    if rest:
      rest_actions.append(verb)
      continue
    if not nums:
      bad.append(clause)
      continue
    for n in nums:
      explicit.setdefault(n, []).append(verb)
  mentioned = set(explicit) | set(free) | (go if go != set(batch) else set())
  for n in batch:
    if rest_actions and n not in mentioned:
      explicit.setdefault(n, []).extend(rest_actions)
  unknown = sorted((set(explicit) | set(free) | go) - set(known))
  if unknown:
    bad.append("no item " + ", ".join(map(str, unknown)))
  return explicit, go, free, bad


def gog_boxes():
  return ["personal"] if pa.machine() == "macbook-pro" else ["work", "personal"]


def connector_step(move):
  return {"archive": "unlabel_thread [INBOX, STARRED]", "keep": "label_thread [STARRED]",
          "trash": "trash_thread", "spam": "mark_thread_spam", "unstar": "unlabel_thread [STARRED]"}.get(
            move, f"label_thread {move[6:]!r} (list_labels for its id), then unlabel_thread [INBOX, STARRED]"
            if move.startswith("label:") else move)


def cmd_expand(args):
  led = need()
  by_n = {it["n"]: it for it in led["items"] if it["n"] is not None}
  if not by_n:
    pa.die("nothing rendered yet: run `comms-items.py render` and show Ian the list first", 2)
  batch = led["batches"][-1]["numbers"] if led["batches"] else sorted(by_n)
  explicit, go, free, bad = parse_reply(args.reply, set(by_n), batch)

  plans, conflicts = {}, []
  for n in sorted(set(batch) | set(explicit) | set(free) | go):
    it = by_n.get(n)
    if not it:
      continue
    if n in explicit or n in free:
      acts = [a for a in explicit.get(n, []) if a != "none"]
    elif n in go:
      acts = list(it["go"])
    else:
      acts = []
    plans[n] = acts

  gogb = gog_boxes()
  mail_lines, connector, other, notes = [], [], [], []
  untouched = []
  for n in sorted(plans):
    it, acts = by_n[n], plans[n]
    label = f"{n} {'+'.join(it['ch'])} {it['who'] or it['what']}"
    moves = [a for a in acts if a in MAIL_MOVES or a.startswith("label:")]
    if it["bucket"] == "apps" or any(c.startswith("🔑") for c in it["ch"]):
      moves = [a for a in moves if a != "keep"]
      acts = ["keep-app" if a == "keep" else a for a in acts]
    if len(set(m for m in moves if m != "keep")) > 1:
      conflicts.append(f"{n}: {' and '.join(moves)}")
      continue
    move = next((m for m in moves if m != "keep"), "keep")
    for mb, t in it["mail"]:
      if mb in gogb:
        if move.startswith("label:"):
          mail_lines.append(f"{mb} label {move[6:]} {t}  # {label}")
        else:
          mail_lines.append(f"{mb} {move} {t}  # {label}")
      else:
        connector.append(f"{label}: {mb} thread {t}: {connector_step(move)}")
    if moves and not it["mail"]:
      notes.append(f"{label}: {', '.join(moves)} has no email in this item; nothing done for it")
    rest = [a for a in acts if a not in MAIL_MOVES and not a.startswith("label:")]
    if n in free:
      other.append(f"{label}: Ian says: \"{free[n]}\" (do it on {(it.get('reply_on') or it['ch'][0])}; "
                   f"a reply is a draft, voice-checked)" + ids_note(it))
    for a in rest:
      other.append(step(n, it, a, label))
    if not acts and n not in free:
      untouched.append(str(n))

  print(f"Ian's answer: {one_line(args.reply)}")
  if bad or conflicts:
    for b in bad:
      print(f"? not understood: \"{b}\"")
    for c in conflicts:
      print(f"? conflicting: {c}")
  plan_path = state_path("comms-mail-plan.txt")
  if mail_lines:
    print(f"\nmail-apply.py plan ({len(mail_lines)} line(s); `keep` = stays in the inbox, starred):")
    print("\n".join(mail_lines))
  if connector:
    print("\nwork mail through the Gmail connector (then the star rules: kept threads starred):")
    print("\n".join(connector))
  if other:
    print("\nother steps (each by its channel skill's Execute step):")
    print("\n".join(other))
  if notes:
    print("\nnotes:")
    print("\n".join(notes))
  if untouched:
    print(f"\nno action (mail stays in the inbox, starred): {', '.join(untouched)}")
  if bad or conflicts:
    print("\nNothing saved. Ask Ian about the lines marked ?, then run expand again with his whole answer.")
    sys.exit(1)
  if mail_lines:
    with open(plan_path, "w", encoding="utf-8") as f:
      f.write("\n".join(mail_lines) + "\n")
    print(f"\nrun: python3 {os.path.join(HERE, 'mail-apply.py')} < {plan_path}")


def ids_note(it):
  bits = []
  if it["mail"]:
    bits.append("mail " + ", ".join(f"{mb} {t}" for mb, t in it["mail"]))
  if it["slack"]:
    bits.append("slack " + ", ".join(it["slack"]))
  for k in ("whatsapp", "linkedin", "event", "app"):
    if it.get(k):
      bits.append(f"{k} {it[k]}")
  return (" [" + "; ".join(bits) + "]") if bits else ""


def step(n, it, a, label):
  S = HERE
  on = it.get("reply_on") or next((c for c in it["ch"] if not c.startswith(("📅", "🔑"))), it["ch"][0])
  draft = f" text: \"{one_line(it['draft'])}\"" if it.get("draft") else " (no draft text yet: write it in Ian's voice)"
  if a == "draft":
    if on in ("W✉", "P✉") and it["mail"]:
      mb, t = next(((mb, t) for mb, t in it["mail"] if MAIL_TAG[mb] == on), it["mail"][0])
      return f"{label}: draft reply: python3 {S}/mail-draft.py {mb} {t} <<'EOF' ... EOF;{draft}"
    if on == "S":
      return f"{label}: slack_send_message_draft in {', '.join(it['slack']) or '(no Slack link)'};{draft}"
    if on == "WA":
      return f"{label}: python3 {S}/whatsapp.py draft \"{it.get('whatsapp', '?')}\" (one at a time, last);{draft}"
    if on == "LI":
      return f"{label}: show the draft for Ian to paste in LinkedIn ({it.get('linkedin', '?')});{draft}"
    return f"{label}: draft on {on}?{draft}"
  if a == "task":
    subj = it["task"] if isinstance(it.get("task"), str) else "<PREFIX: what to do>"
    if isinstance(it.get("task"), int):
      return f"{label}: already task {it['task']}: a note instead? (note {n})"
    src = (f"--mailbox {it['mail'][0][0]} --thread {it['mail'][0][1]}" if it["mail"] and it["mail"][0][0] in gog_boxes()
           else f"--link {it['slack'][0]}" if it["slack"] else
           f"--link \"WhatsApp: {it['whatsapp']}\"" if it.get("whatsapp") else "--link <source link>")
    return f"{label}: python3 {S}/gtd-new-task.py --subject \"{subj}\" {src}  (notes on stdin)"
  if a == "note":
    if not isinstance(it.get("task"), int):
      return f"{label}: note: which task? (the item has no task number)"
    src = (f"--mailbox {it['mail'][0][0]} --thread {it['mail'][0][1]}" if it["mail"] and it["mail"][0][0] in gog_boxes()
           else f"--link {it['slack'][0]}" if it["slack"] else "--link <source link>")
    return f"{label}: python3 {S}/gtd-note.py {it['task']} {src}  (note on stdin)"
  if a.startswith("react"):
    emo = a.split(":", 1)[1] if ":" in a else "eyes"
    return f"{label}: slack_add_reaction {emo} on {', '.join(it['slack']) or '(no Slack link)'}"
  if a in ("accept", "decline", "tentative"):
    return f"{label}: calendar respond {a} to {it.get('event', it['what'])} (say who's notified)"
  if a == "add":
    return f"{label}: calendar add {it.get('event', it['what'])} to {'W' if '📅 W' in it['ch'] or 'W✉' in it['ch'] else 'P'}"
  if a in ("cut", "keep-app"):
    acct = "work" if "🔑 W" in it["ch"] else "personal"
    name = it.get("app") or it["who"]
    if a == "cut":
      return f"{label}: remove in Chrome (Google apps, Cut), then google-apps.py cut {acct} \"{name}\""
    return f"{label}: google-apps.py keep {acct} \"{name}\""
  return f"{label}: {a}"


# ── show, next, notify ───────────────────────────────────────────────────────────────────

def cmd_show(args):
  led = need()
  by_n = {it["n"]: it for it in led["items"] if it["n"] is not None}
  nums, rest = numbers(" ".join(args.numbers), set(by_n))
  if rest.strip(" ,"):
    pa.die(f"not numbers: {rest.strip()}", 2)
  for n in sorted(nums):
    it = by_n.get(n)
    if not it:
      print(f"{n}: no such item")
      continue
    print(f"{n} [{HEADING[it['bucket']]}] {'+'.join(it['ch'])} {it['who']}: {it['what']}" + ids_note(it))
    if it.get("task"):
      print(f"   task: {it['task']}")
    if it.get("draft"):
      print(f"   draft: {one_line(it['draft'])}")
    print(f"   go: {', '.join(it['go']) or '-'}")


def next_batches():
  try:
    with open(state_path("mail-gather-last.json"), encoding="utf-8") as f:
      boxes = json.load(f)
  except (OSError, ValueError):
    return []
  return [(b["mailbox"], b.get("query", "in:inbox")) for b in boxes if b.get("more")]


def cmd_next(args):
  more = next_batches()
  if not more:
    print("no more mail beyond this batch in the gog mailboxes (the work connector: check its search)")
    return
  for mb, q in more:
    print(f"{mb}: python3 {os.path.join(HERE, 'mail-gather.py')} list --mailbox {mb} --query '{q}' "
          f"--exclude {state_path('comms-shown.tsv')}")
  print("then `comms-items.py add` the new items and `render`: numbers carry on from the last batch")


def summary(items, failed):
  c = {}
  for it in items:
    c[it["bucket"]] = c.get(it["bucket"], 0) + 1
  parts = []
  if c.get("instructions"):
    parts.append(f"{c['instructions']} instruction{'s' if c['instructions'] > 1 else ''}")
  parts.append(f"{c['act']} act now" if c.get("act") else "nothing urgent")
  for b, word in (("waiting", "waiting on you"), ("schedule", "to schedule"), ("delegate", "to delegate"),
                  ("ack", "to acknowledge"), ("suspicious", "suspicious")):
    if c.get(b):
      parts.append(f"{c[b]} {word}")
  if c.get("apps"):
    parts.append(f"{c['apps']} Google app{'s' if c['apps'] > 1 else ''}")
  fyi = sum(c.get(b, 0) for b in SHARED)
  if fyi:
    parts.append(f"{fyi} FYI/junk")
  msg = f"Comms ready ({datetime.date.today():%a %d %b}): " + ", ".join(parts) + "."
  tail = ""
  if failed:
    tail = " " + ", ".join(f[:1].upper() + f[1:] for f in failed) + " failed."
  act = sorted((it for it in items if it["bucket"] == "act"), key=lambda it: it["n"] or 0)
  if act:
    who = act[0]["who"].split(",")[0].strip()
    top = f" Top: {who}: {act[0]['what']}".replace('"', "'")
    room = 199 - len(msg) - len(tail)
    if room > 20:
      top = top if len(top) <= room else top[:room - 1].rstrip() + "…"
      msg += top
  return (msg + tail).replace('"', "'")


def cmd_notify(args):
  led = need()
  batch = set(led["batches"][-1]["numbers"]) if led["batches"] else set()
  items = [it for it in led["items"] if it["n"] in batch]
  msg = summary(items, args.failed)
  cmd = [sys.executable, os.path.join(HERE, "pa-notify.py"), "--title", "Comms ready", "--sound", "Glass"]
  if args.dry_run:
    cmd.append("--dry-run")
  if not os.path.exists(cmd[1]):
    print(msg)
    print("(pa-notify.py isn't there: no macOS notification sent)")
    return
  p = subprocess.run(cmd + [msg], capture_output=True, text=True, timeout=60)
  sent = (p.stdout.strip().splitlines() or [msg])[-1]
  print(sent)
  if p.returncode != 0:
    print(f"(macOS notification failed: {(p.stderr or '').strip()})")
  print("Send the same text with PushNotification (status proactive).")


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  p = sub.add_parser("add", help="add items (JSON lines on stdin or in a file)")
  p.add_argument("file", nargs="?")
  p.add_argument("--reset", action="store_true", help="start a new ledger")
  p = sub.add_parser("render", help="number the new items and print the tables")
  p.add_argument("--mail", action="store_true", help="the mail skill's layout: work, then personal")
  p.add_argument("--all", action="store_true", help="every batch, not just the latest")
  p = sub.add_parser("expand", help="turn Ian's answer into the actions")
  p.add_argument("reply", nargs="+")
  p = sub.add_parser("show", help="what numbers stand for")
  p.add_argument("numbers", nargs="+")
  sub.add_parser("next", help="the command for the next mail batch")
  p = sub.add_parser("notify", help="the morning run's notification")
  p.add_argument("--failed", action="append", default=[], help="a channel that failed (repeatable)")
  p.add_argument("--dry-run", action="store_true")
  args = ap.parse_args()
  if args.cmd == "expand":
    args.reply = " ".join(args.reply)
  {"add": cmd_add, "render": cmd_render, "expand": cmd_expand, "show": cmd_show, "next": cmd_next,
   "notify": cmd_notify}[args.cmd](args)


if __name__ == "__main__":
  main()
