#!/usr/bin/env python3
"""Today's interviews on Ian's work calendar, with what the interview skill needs for each.

  interview-gather.py --work W.json                  # a saved list_events result for the day
  interview-gather.py --gog                          # fetch today's work calendar with gog
  interview-gather.py --work W.json --date 2026-11-11 --mail-file thread1.txt --mail-file thread2.txt
  interview-gather.py --gog --json

An interview is any event that day with "interview" in the title (as interview-morning.sh
matches). Each one is marked `from Ivana: yes` when ivana@container-solutions.com organised or
created it, the skill's trigger; the others are listed too, marked `no`, for the skill to ask
Ian about rather than prep or drop silently. Declined and cancelled events are still listed,
with Ian's response, so nothing goes missing without a word.

For each: London time, title, stage from the title (pairing, technical, culture fit,
consultant, final, screening), organiser, Ian's response, co-interviewers (other
container-solutions.com attendees) and theirs, the candidate (an outside attendee, or else the
title with the interview words taken out, marked as such), the Meet link, the links in the
description and attachments, CE-N Jira tickets, and `people-note.py find` for the candidate.

--mail-file FILE (repeatable) scans saved email text (e.g. a thread read with
`mail-gather.py read`) for GitHub handles that are literally there: github.com/<handle> links,
or "GitHub: handle" / "GitHub handle: handle". It never guesses one. Each is shown with the
line it came from, and the CE-N tickets in the mail are added too.

Also prints the subject for `pa-mail-html.py --kind interview` (`--detail`). Exit 0 either
way; "no interviews" when there are none. --now stands in for the clock (tests).
"""

import argparse
import datetime
import html
import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402


def load_module(name, file):
  spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
  mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(mod)
  return mod


ce = load_module("calendar_events", "calendar-events.py")
IVANA = "ivana@container-solutions.com"
CS_DOMAIN = "@container-solutions.com"
JIRA = "https://container-solutions.atlassian.net/browse/"
TICKET_RE = re.compile(r"\bCE-\d+\b")
STAGES = [(r"\bpair(ing)?\b", "pairing"), (r"\btech(nical)?\b", "technical"), (r"\bculture\b", "culture fit"),
          (r"\bconsultant\b", "consultant interview"), (r"\bfinal\b", "final"),
          (r"\b(screen(ing)?|intro(duction)?|first)\b", "screening")]
TITLE_NOISE = re.compile(r"\b(interview(s|er)?|pair(ing)?|tech(nical)?|culture( fit)?|consultant|final|screen(ing)?|"
                         r"intro(duction)?|first|second|third|stage|round|session|call|with|and|for|"
                         r"container solutions|cs)\b|[|:<>()\[\]/+&,–—-]", re.I)
GITHUB_RESERVED = {"containersolutions", "orgs", "settings", "features", "about", "login", "notifications", "pulls",
                   "issues", "marketplace", "sponsors", "topics", "apps", "enterprise", "pricing", "site", "security",
                   "explore", "join", "new", "search", "collections", "events", "trending", "readme", "github"}
GH_URL_RE = re.compile(r"github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))(?![A-Za-z0-9-])", re.I)
GH_SAID_RE = re.compile(r"\bgit ?hub(?:\s+(?:handle|username|user\s?name|user|account|profile|id))?\s*(?:is|:|=|-)\s*@?"
                        r"([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))\b", re.I)


def stage(title):
  for pat, name in STAGES:
    if re.search(pat, title, re.I):
      return name
  return "unknown"


def name_from_title(title):
  rest = " ".join(TITLE_NOISE.sub(" ", title).split())
  words = rest.split()
  if 1 < len(words) <= 4 and all(w[:1].isupper() for w in words):
    return rest
  return None


def links_of(ev):
  text = html.unescape(ev["description"])
  urls = re.findall(r'href="([^"]+)"', text) + ce.links_in(re.sub(r"<[^>]+>", " ", text))
  out, seen = [], set()
  for a in ev["attachments"]:
    if a["url"] and a["url"] not in seen:
      seen.add(a["url"])
      out.append((a["title"] or "attachment", a["url"]))
  for u in urls:
    u = u.rstrip(".,;")
    if u in seen or (ev["meet"] and u.startswith(ev["meet"])) or "meet.google.com" in u:
      continue
    seen.add(u)
    out.append((kind_of(u), u))
  return out


def kind_of(u):
  for pat, k in (("docs.google.com/document", "doc"), ("docs.google.com/spreadsheets", "sheet"),
                 ("drive.google.com", "drive"), ("atlassian.net", "jira"), ("linkedin.com", "linkedin"),
                 ("github.com", "github"), ("trello.com", "board")):
    if pat in u:
      return k
  return "link"


def people_find(name, email):
  if not name:
    return []
  cmd = [sys.executable, os.path.join(HERE, "people-note.py"), "find", name] + (["--email", email] if email else [])
  try:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
  except (OSError, subprocess.TimeoutExpired) as e:
    return [f"(people-note.py failed: {e})"]
  out = (p.stdout or p.stderr).strip()
  return [pa.one_line(l, 140) for l in out.splitlines()[:4]] or ["(no file)"]


def scan_mail(paths):
  handles, tickets = {}, set()
  for path in paths:
    try:
      text = open(os.path.expanduser(path), encoding="utf-8", errors="replace").read()
    except OSError as e:
      handles.setdefault("(error)", []).append(f"{path}: {e}")
      continue
    for line in text.splitlines():
      tickets.update(TICKET_RE.findall(line))
      for m in list(GH_URL_RE.finditer(line)) + list(GH_SAID_RE.finditer(line)):
        h = m.group(1)
        if h.lower() in GITHUB_RESERVED:
          continue
        handles.setdefault(h, [])
        if len(handles[h]) < 2:
          handles[h].append(f"{os.path.basename(path)}: {pa.one_line(line.strip(), 120)}")
  return handles, sorted(tickets, key=lambda t: int(t[3:]))


def gather(ev):
  ian = next((a for a in ev["attendees"] if a["self"] or a["email"] in pa.IAN_ADDRESSES), None)
  others = [a for a in ev["attendees"] if a is not ian and not a["resource"]]
  co = [a for a in others if a["email"].endswith(CS_DOMAIN) and a["email"] != ev["organiser"]]
  outside = [a for a in others if a["email"] and not a["email"].endswith(CS_DOMAIN)]
  if outside:
    cand = [{"name": a["name"] or "", "email": a["email"], "how": "attendee"} for a in outside]
  else:
    n = name_from_title(ev["title"])
    cand = [{"name": n, "email": "", "how": "from the title"}] if n else []
  text = " ".join([ev["title"], html.unescape(ev["description"])] + [a["title"] for a in ev["attachments"]])
  tickets = sorted(set(TICKET_RE.findall(text)), key=lambda t: int(t[3:]))
  return {
    "title": ev["title"], "start": ev["start"], "end": ev["end"], "stage": stage(ev["title"]),
    "from_ivana": IVANA in (ev["organiser"], ev["creator"]), "organiser": ev["organiser_name"] or ev["organiser"],
    "organiser_email": ev["organiser"], "response": ev["response"] or "unknown",
    "co": [{"name": a["name"] or a["email"], "email": a["email"], "response": a["response"] or "unknown"} for a in co],
    "candidates": cand, "meet": ev["meet"], "links": links_of(ev), "tickets": tickets,
    "people": {c["name"] or c["email"]: people_find(c["name"], c["email"]) for c in cand if c["name"]},
  }


def response_text(r):
  return {"needsaction": "NOT RESPONDED", "accepted": "accepted", "declined": "DECLINED",
          "tentative": "tentative"}.get(r, r)


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("--work", action="append", default=[], metavar="FILE", help="list_events result for the work calendar")
  ap.add_argument("--gog", action="store_true", help="fetch the work calendar with gog")
  ap.add_argument("--date", help="YYYY-MM-DD (default today)")
  ap.add_argument("--mail-file", action="append", default=[])
  ap.add_argument("--json", action="store_true")
  ap.add_argument("--now", help=argparse.SUPPRESS)
  args = ap.parse_args()
  if not args.work and not args.gog:
    pa.die("give --work FILE (a list_events result) or --gog", 2)
  now = ce.now_london(args.now)
  day = datetime.date.fromisoformat(args.date) if args.date else now.date()
  win = ce.win_times(day, day + datetime.timedelta(days=1))
  events, info = ce.load(args.work, [], ["work"] if args.gog else [], win, keep_cancelled=True)
  found = [gather(e) | {"cancelled": e["status"] == "cancelled"} for e in events
           if "interview" in e["title"].lower() and not e["all_day"]]
  handles, mail_tickets = scan_mail(args.mail_file)
  ivana = [i for i in found if i["from_ivana"] and not i["cancelled"]]
  detail = ", ".join(f"{(i['candidates'][0]['name'] if i['candidates'] and i['candidates'][0]['name'] else i['title'])} "
                     f"{ce.hm(i['start'])}" for i in ivana)
  subject = f"Interview prep: {day:%a} {day.day} {day:%b}" + (f" - {detail}" if detail else "")
  errs = ce.errors(info)
  if args.json:
    print(pa.as_json({"date": day, "zone": ce.zone(day), "errors": errs, "subject": subject, "detail": detail,
                      "interviews": found, "github_from_mail": handles, "tickets_from_mail": mail_tickets}))
    return
  for e in errs:
    print(f"missing: {e}")
  print(f"INTERVIEWS {ce.day_label(day, True)} (all times {ce.zone(day)}): {len(found)} found, "
        f"{len(ivana)} from Ivana")
  if not found:
    print("no interviews")
  else:
    print(f"subject: {subject}")
  for n, i in enumerate(found, 1):
    print(f"\n{n}. {ce.hm(i['start'])}-{ce.hm(i['end'])} {i['title']}"
          + ("  [CANCELLED]" if i["cancelled"] else ""))
    print(f"   from Ivana: {'yes' if i['from_ivana'] else 'no (organiser ' + (i['organiser_email'] or 'unknown') + '): ask Ian'}")
    print(f"   stage: {i['stage']}; Ian: {response_text(i['response'])}")
    if i["co"]:
      print("   co-interviewers: " + ", ".join(f"{c['name']} ({response_text(c['response'])})" for c in i["co"]))
    for c in i["candidates"]:
      print(f"   candidate: {c['name'] or '?'}" + (f" <{c['email']}>" if c["email"] else "") + f" ({c['how']})")
    if not i["candidates"]:
      print("   candidate: not found in the attendees or title")
    print(f"   meet: {i['meet'] or 'none'}")
    for k, u in i["links"]:
      print(f"   link ({k}): {u}")
    for t in i["tickets"]:
      print(f"   ticket: {t} {JIRA}{t}")
    for who, lines in i["people"].items():
      print(f"   people/ {who}: " + " | ".join(lines))
  if args.mail_file:
    print("\nFROM THE MAIL")
    if not handles:
      print("  no GitHub handle written in the mail: ask Ian (never guess one)")
    for h, where in handles.items():
      print(f"  github: {h}  ({'; '.join(where)})")
    for t in mail_tickets:
      print(f"  ticket: {t} {JIRA}{t}")


if __name__ == "__main__":
  main()
