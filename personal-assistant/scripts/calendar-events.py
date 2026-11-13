#!/usr/bin/env python3
"""Ian's work (W) and personal (P) calendars from saved list_events results, as compact lines.

  calendar-events.py window week                      # startTime/endTime for list_events
  calendar-events.py window "week-of 2026-10-26"      # also today, tomorrow, next week, invites,
                                                      # thu, 2026-10-29, 2026-10-26..2026-10-30
  calendar-events.py agenda --work W.json --personal P.json [--window week] [--declined]
  calendar-events.py agenda --gog work --personal P.json --window today --fields minimal
  calendar-events.py free --work W.json --personal P.json --window "next week" --from 09:00 --to 17:30 --min 90
  calendar-events.py match 20261015_1130 --work W.json --personal P.json --meetings ~/git/gtd/meetings
  calendar-events.py attendees "Jane Doe" "Önsel Yilmaz" --work W.json --personal P.json
  calendar-events.py attendees --names-file names.txt --work W.json
  calendar-events.py verify --calendar W --start 2026-11-16T10:00 --end 2026-11-16T10:30 \\
      --title "Catch up" --attendee jane@acme.example --response accepted < get_event.json
  calendar-events.py access --work W.json --personal P.json

Inputs. `--work FILE` and `--personal FILE` (each repeatable, `-` for stdin) are what the Google
Calendar connector's list_events returned, saved to a file, in whatever wrapper: a list of
events, {"events": [...]}, {"items": [...]}, an MCP text block [{"type": "text", "text":
"<json>"}], the file the harness saves an oversized result to, or gog's --json output. Field
names may be camelCase or snake_case and enums any case (needsAction, NEEDS_ACTION).
`--gog work|personal` fetches that calendar with gog for the --window instead (read only, with
--gmail-no-send; PA_GOG points at a fake in the tests). The personal gog login may lack the
calendar scope: then use the connector for P.

Times are shown in Europe/London, per day (GMT or BST), whatever the input's offset.

agenda: one line per event: time, W / P / W+P (the same iCalUID, or the same title and start, on
both), title, flags, attendee count, organiser, Meet, location. Declined events (Ian's own
responseStatus) are left out unless --declined, and counted. Flags:
  CLASH   overlaps another busy event (events shown as free and all-day ones don't count)
  PENDING Ian hasn't responded (needsAction); listed again under NEEDS A DECISION
  TIGHT   starts within 15 minutes of the one before, at a different physical location
  FREE    marked free (transparent)
All-day events are listed first under each day. --fields picks columns from
time,cal,title,flags,att,org,meet,loc,id (`minimal` = time,cal,title,flags).

free: gaps of at least --min minutes between --from and --to on each weekday (--all-days for
weekends too), counting busy timed events on both calendars.

match: the meeting skill's rules for a recording stem (YYYYMMDD_HHMM, London time). Events from 3
hours before to 3 hours after; all-day, free and declined ones dropped. Score 0 if the stem falls
inside the event, else the minutes to its nearer edge; on a tie the one starting (at or after the
stem) wins, then one under way, then one that ended there, then the earlier start. --meetings DIR notes events that already have a recording
named after them that day (YYYYMMDD_*_<Title>.*). Prints the best 3, numbered, best marked *.

attendees: for each name, the events where an attendee's (or the organiser's) display name has
the first and last name, or whose address is first.last@, flast@, f.last@, firstlast@, first_last@
or first-last@ (accents folded), leaving out events Ian declined and attendees who declined.
One line per name: count, last and next date.

verify: compares a get_event result on stdin with what was meant, and prints OK or each differing
field (exit 1). access: the accessRole of each calendar and, when it can't be changed, the fix.

--json prints the same as JSON. --now YYYY-MM-DDTHH:MM (London) stands in for the clock.
"""

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

LONDON = ZoneInfo("Europe/London")
UTC = datetime.timezone.utc
CALS = {"W": pa.MAILBOXES["work"], "P": pa.MAILBOXES["personal"]}
GOG_TAG = {"work": "W", "personal": "P"}
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
TIGHT = datetime.timedelta(minutes=15)
FIELDS = ("time", "cal", "title", "flags", "att", "org", "meet", "loc")
ACCESS_FIX = ("The fix is in Google Calendar on the personal account: Settings -> ian.miell@gmail.com -> "
              "Share with specific people -> give ian.miell@container-solutions.com "
              "\"Make changes and manage sharing\".")
VIDEO_RE = re.compile(r"https?://(?:meet\.google\.com|[\w.-]*zoom\.us|teams\.microsoft\.com|teams\.live\.com)/\S*", re.I)


# --- small helpers ---------------------------------------------------------------------------

def key(name):
  return name.replace("_", "").replace("-", "").lower()


def g(d, *names, default=None):
  """d[name] for the first name present and not empty, ignoring case and underscores."""
  if not isinstance(d, dict):
    return default
  keys = {key(k): k for k in d}
  for n in names:
    k = keys.get(key(n))
    if k is not None and d[k] not in (None, "", [], {}):
      return d[k]
  return default


def enum(v):
  return key(str(v or ""))


FOLD_EXTRA = str.maketrans({"ı": "i", "ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ß": "ss",
                            "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE"})


def fold(text):
  text = unicodedata.normalize("NFKD", (text or "").translate(FOLD_EXTRA))
  return "".join(c for c in text if not unicodedata.combining(c)).lower()


def zone(d):
  """GMT or BST on a date (at noon, so a clock-change day reads as the zone most of it is in)."""
  return datetime.datetime(d.year, d.month, d.day, 12, tzinfo=LONDON).tzname()


def midnight(d):
  return datetime.datetime(d.year, d.month, d.day, tzinfo=LONDON)


def day_label(d, year=False):
  return f"{d:%a} {d.day} {d:%b}" + (f" {d.year}" if year else "")


def hm(dt):
  return dt.astimezone(LONDON).strftime("%H:%M")


def now_london(s=None):
  if s:
    dt = datetime.datetime.fromisoformat(s)
    return dt.astimezone(LONDON) if dt.tzinfo else dt.replace(tzinfo=LONDON)
  return datetime.datetime.now(LONDON)


def parse_dt(s, tz=None):
  s = str(s).strip()
  if s.endswith("Z"):
    s = s[:-1] + "+00:00"
  dt = datetime.datetime.fromisoformat(s)
  if dt.tzinfo is None:
    try:
      dt = dt.replace(tzinfo=ZoneInfo(tz) if tz else LONDON)
    except (KeyError, ValueError):
      dt = dt.replace(tzinfo=LONDON)
  return dt.astimezone(LONDON)


def parse_when(v, tz=None):
  """(datetime, None) for a timed start/end, (None, date) for an all-day one, (None, None) if unknown."""
  if isinstance(v, dict):
    if "year" in v and "month" in v and "day" in v:
      return None, datetime.date(int(v["year"]), int(v["month"]), int(v["day"]))
    dt = g(v, "dateTime")
    if dt:
      return parse_dt(dt, g(v, "timeZone") or tz), None
    d = g(v, "date")
    if isinstance(d, dict):
      return parse_when(d)
    if d:
      return None, datetime.date.fromisoformat(str(d)[:10])
    return None, None
  if isinstance(v, str) and v:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
      return None, datetime.date.fromisoformat(v.strip())
    return parse_dt(v, tz), None
  return None, None


# --- reading the files -----------------------------------------------------------------------

def json_values(text):
  """Every JSON value in text: the whole of it, or each object or list embedded in other text."""
  text = text.strip()
  if not text:
    return []
  try:
    return [json.loads(text)]
  except ValueError:
    pass
  dec, out, i = json.JSONDecoder(), [], 0
  while True:
    m = re.compile(r"[\[{]").search(text, i)
    if not m:
      return out
    try:
      v, end = dec.raw_decode(text, m.start())
      out.append(v)
      i = end
    except ValueError:
      i = m.start() + 1


def looks_like_event(d):
  return isinstance(d, dict) and g(d, "start", "startTime") is not None and \
    g(d, "summary", "title", "id", "eventId") is not None


def walk(obj, events, meta, depth=0):
  if depth > 12:
    return
  if isinstance(obj, str):
    if obj.lstrip()[:1] in ("{", "["):
      for v in json_values(obj):
        walk(v, events, meta, depth + 1)
    return
  if isinstance(obj, list):
    for x in obj:
      walk(x, events, meta, depth + 1)
    return
  if not isinstance(obj, dict):
    return
  if looks_like_event(obj):
    events.append(obj)
    return
  role = g(obj, "accessRole")
  if role:
    meta.setdefault("access", []).append(str(role))
  for v in obj.values():
    walk(v, events, meta, depth + 1)


def read_raw(path):
  text = sys.stdin.read() if path == "-" else open(os.path.expanduser(path), encoding="utf-8", errors="replace").read()
  events, meta = [], {}
  for v in json_values(text):
    walk(v, events, meta)
  return events, meta


def person(d):
  return {"email": str(g(d, "email", default="")).lower(), "name": str(g(d, "displayName", "name", default="")),
          "self": bool(g(d, "self", default=False)), "organizer": bool(g(d, "organizer", default=False)),
          "response": enum(g(d, "responseStatus", "response", default="")),
          "resource": bool(g(d, "resource", default=False)) or "resource.calendar.google.com" in str(g(d, "email", default="")),
          "optional": bool(g(d, "optional", default=False))}


def links_in(text):
  return re.findall(r"https?://[^\s\"'<>)\]]+", text or "")


def norm(raw, cal):
  """One event in a fixed shape, times in London."""
  tz = g(raw, "timeZone")
  start, sdate = parse_when(g(raw, "start", "startTime"), tz)
  end, edate = parse_when(g(raw, "end", "endTime"), tz)
  all_day = start is None
  if all_day:
    if sdate is None:
      return None
    edate = edate if edate and edate > sdate else sdate + datetime.timedelta(days=1)
  elif end is None:
    end = start
  attendees = [person(a) for a in (g(raw, "attendees", default=[]) or []) if isinstance(a, dict)]
  org = person(g(raw, "organizer", default={}) or {})
  creator = person(g(raw, "creator", default={}) or {})
  own = CALS.get(cal)
  me = next((a for a in attendees if a["self"]), None) or \
    next((a for a in attendees if own and a["email"] == own), None) or \
    next((a for a in attendees if a["email"] in pa.IAN_ADDRESSES), None)
  if me:
    response = me["response"]
  elif not attendees or org["self"] or org["email"] in pa.IAN_ADDRESSES or not org["email"]:
    response = "accepted"
  else:
    response = ""
  conf = g(raw, "conferenceData", default={}) or {}
  meet = g(raw, "hangoutLink", "meetLink", "meetingLink", default="")
  if not meet:
    for ep in g(conf, "entryPoints", default=[]) or []:
      if enum(g(ep, "entryPointType")) == "video" and g(ep, "uri"):
        meet = g(ep, "uri")
        break
  location = str(g(raw, "location", default=""))
  description = str(g(raw, "description", default=""))
  if not meet:
    m = VIDEO_RE.search(location) or VIDEO_RE.search(description)
    meet = m.group(0) if m else ""
  attachments = [{"title": str(g(a, "title", default="")), "url": str(g(a, "fileUrl", "url", default=""))}
                 for a in (g(raw, "attachments", default=[]) or []) if isinstance(a, dict)]
  return {
    "cal": cal, "id": str(g(raw, "id", "eventId", default="")), "ical": str(g(raw, "iCalUID", "icalUid", default="")),
    "title": str(g(raw, "summary", "title", default="(no title)")).strip() or "(no title)",
    "start": start, "end": end, "all_day": all_day, "sdate": sdate if all_day else start.date(),
    "edate": edate if all_day else end.date(),
    "transparent": enum(g(raw, "transparency")) == "transparent", "response": response,
    "status": enum(g(raw, "status")), "event_type": enum(g(raw, "eventType")),
    "organiser": org["email"], "organiser_name": org["name"], "organiser_self": org["self"],
    "creator": creator["email"], "attendees": attendees,
    "n_att": len([a for a in attendees if not a["resource"]]),
    "location": location, "meet": meet, "description": description, "attachments": attachments,
    "copies": [cal],
  }


class Missing(Exception):
  pass


def gog_events(tag, start, end):
  box = "work" if tag == "W" else "personal"
  try:
    res = pa.gog(box, "calendar", "events", CALS[tag], "--from", start.isoformat(), "--to", end.isoformat(),
                 "--all-pages", "--max", "250", "--readonly")
  except (pa.GogError, OSError, ValueError) as e:
    raise Missing(f"{tag} via gog: {pa.one_line(str(e), 200)}")
  events, meta = [], {}
  walk(res, events, meta)
  return events, meta


def load(work=(), personal=(), gog=(), win=None, keep_cancelled=False):
  """(events, info) from the files and gog. info[tag] = {count, access, error}. Events are deduped
  by id within a calendar and sorted; with a window, only those overlapping it are kept."""
  info, events = {}, []
  sources = [("W", f) for f in work or ()] + [("P", f) for f in personal or ()] + \
            [(GOG_TAG.get(x, x), None) for x in gog or ()]
  for tag, path in sources:
    i = info.setdefault(tag, {"count": 0, "access": [], "errors": []})
    try:
      if path is None:
        if not win:
          raise Missing(f"{tag} via gog: needs --window")
        raw, meta = gog_events(tag, win[0], win[1])
      else:
        raw, meta = read_raw(path)
    except Missing as e:
      i["errors"].append(str(e))
      continue
    except (OSError, ValueError) as e:
      i["errors"].append(f"{tag} {path}: {e}")
      continue
    i["access"] += meta.get("access", [])
    seen = set()
    for r in raw:
      try:
        ev = norm(r, tag)
      except (ValueError, TypeError) as e:
        i["errors"].append(f"{tag}: skipped an event ({e})")
        continue
      if not ev or (ev["status"] == "cancelled" and not keep_cancelled):
        continue
      k = ev["id"] or (ev["title"], str(ev["start"] or ev["sdate"]))
      if k in seen:
        continue
      seen.add(k)
      if win and not overlaps(ev, win[0], win[1]):
        continue
      events.append(ev)
      i["count"] += 1
  events.sort(key=sort_key)
  return events, info


def sort_key(ev):
  return (ev["start"] or midnight(ev["sdate"]), not ev["all_day"], ev["cal"] == "P", ev["title"])


def overlaps(ev, start, end):
  if ev["all_day"]:
    return midnight(ev["sdate"]) < end and midnight(ev["edate"]) > start
  if ev["start"] == ev["end"]:
    return start <= ev["start"] < end
  return ev["start"] < end and ev["end"] > start


def merge(events):
  """The same event on both calendars once, tagged W+P: the same iCalUID, or the same title and start."""
  out, by = [], {}
  for ev in events:
    keys = [("i", ev["ical"])] if ev["ical"] else []
    keys.append(("t", fold(ev["title"]).strip(), str(ev["start"] or ev["sdate"]), ev["all_day"]))
    hit = next((by[k] for k in keys if k in by and ev["cal"] not in by[k]["copies"]), None)
    if hit:
      hit["copies"].append(ev["cal"])
      hit["cal"] = "W+P"
      hit["responses"].append(ev["response"])
      hit["transparent"] = hit["transparent"] and ev["transparent"]
      if not hit["meet"]:
        hit["meet"] = ev["meet"]
      hit["n_att"] = max(hit["n_att"], ev["n_att"])
      continue
    ev = dict(ev, copies=[ev["cal"]], responses=[ev["response"]])
    for k in keys:
      by.setdefault(k, ev)
    out.append(ev)
  for ev in out:
    rs = ev.pop("responses")
    if any(r in ("accepted", "") for r in rs):
      ev["response"] = "accepted" if "accepted" in rs else ""
    elif "tentative" in rs:
      ev["response"] = "tentative"
    elif "needsaction" in rs:
      ev["response"] = "needsaction"
    else:
      ev["response"] = rs[0]
  return out


def declined(ev):
  return ev["response"] == "declined"


def busy(ev):
  return not ev["all_day"] and not ev["transparent"] and not declined(ev) and ev["end"] > ev["start"]


def physical(loc):
  loc = (loc or "").strip()
  return bool(loc) and not VIDEO_RE.search(loc) and not loc.lower().startswith("http") and \
    not re.search(r"\b(zoom|teams|meet|online|virtual|remote|tbc|tbd)\b", loc, re.I)


def flag(events):
  """Add flags (CLASH, PENDING, TIGHT, FREE) and clash partners to the events, in place."""
  for ev in events:
    ev["flags"], ev["clash_with"] = [], []
    if ev["response"] == "needsaction":
      ev["flags"].append("PENDING")
    if ev["transparent"] and not ev["all_day"]:
      ev["flags"].append("FREE")
    if ev["response"] == "tentative":
      ev["flags"].append("tentative")
    if declined(ev):
      ev["flags"].append("declined")
  timed = sorted((e for e in events if busy(e)), key=sort_key)
  for i, a in enumerate(timed):
    for b in timed[i + 1:]:
      if b["start"] >= a["end"]:
        break
      a["clash_with"].append(b)
      b["clash_with"].append(a)
  for ev in events:
    if ev["clash_with"]:
      ev["flags"].insert(0, "CLASH")
  for a, b in zip(timed, timed[1:]):
    gap = b["start"] - a["end"]
    if datetime.timedelta(0) <= gap <= TIGHT and physical(a["location"]) and physical(b["location"]) and \
       fold(a["location"]).strip() != fold(b["location"]).strip():
      b["flags"].append("TIGHT")
      b["tight_after"] = a
  return events


# --- windows ---------------------------------------------------------------------------------

def window(arg, today):
  """(first day, day after the last) for a scope word, in London dates."""
  a = " ".join((arg or "default").lower().replace("-", " ").split())
  mon = today - datetime.timedelta(days=today.weekday())
  one = datetime.timedelta(days=1)
  if a == "default":
    return today, today + 2 * one
  if a == "today":
    return today, today + one
  if a == "tomorrow":
    return today + one, today + 2 * one
  if a in ("week", "this week"):
    return mon, mon + 7 * one
  if a == "next week":
    return mon + 7 * one, mon + 14 * one
  if a in ("invites", "4 weeks"):
    return today, today + 28 * one
  if a in ("weekend", "this weekend"):
    sat = mon + 5 * one
    return sat, sat + 2 * one
  m = re.fullmatch(r"week of (\d{4} \d{2} \d{2})", a)
  if m:
    d = datetime.date.fromisoformat(m.group(1).replace(" ", "-"))
    d -= datetime.timedelta(days=d.weekday())
    return d, d + 7 * one
  m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\s*\.\.\s*(\d{4}-\d{2}-\d{2})", (arg or "").strip())
  if m:
    a1, a2 = (datetime.date.fromisoformat(x) for x in m.groups())
    return a1, a2 + one
  if re.fullmatch(r"\d{4} \d{2} \d{2}", a):
    d = datetime.date.fromisoformat(a.replace(" ", "-"))
    return d, d + one
  for i, name in enumerate(DAYS):
    full = datetime.date(2026, 11, 16 + i).strftime("%A").lower()
    if len(a) >= 3 and full.startswith(a):
      d = today + datetime.timedelta(days=(i - today.weekday()) % 7)
      return d, d + one
  pa.die(f"unknown window {arg!r}: today, tomorrow, week, next week, invites, a day name, "
         "YYYY-MM-DD, week-of YYYY-MM-DD or YYYY-MM-DD..YYYY-MM-DD", 2)


def win_times(first, after):
  return midnight(first), midnight(after)


def zones_text(first, after):
  """'GMT', 'BST', or 'BST until Sat 24 Oct, GMT from Sun 25 Oct'."""
  d, parts, last = first, [], None
  while d < after:
    z = zone(d)
    if z != last:
      parts.append((z, d))
      last = z
    d += datetime.timedelta(days=1)
  if len(parts) == 1:
    return parts[0][0]
  bits = []
  for i, (z, d) in enumerate(parts):
    if i + 1 < len(parts):
      end = parts[i + 1][1] - datetime.timedelta(days=1)
      bits.append(f"{z} {'until' if i == 0 else 'from ' + day_label(d) + ' to'} {day_label(end)}")
    else:
      bits.append(f"{z} from {day_label(d)}")
  return ", ".join(bits)


def cmd_window(args, now):
  first, after = window(" ".join(args.scope) if args.scope else None, now.date())
  start, end = win_times(first, after)
  last = after - datetime.timedelta(days=1)
  res = {"first": first.isoformat(), "last": last.isoformat(),
         "startTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "endTime": end.strftime("%Y-%m-%dT%H:%M:%S"),
         "start": start.isoformat(), "end": end.isoformat(), "zones": zones_text(first, after)}
  if args.json:
    print(json.dumps(res, indent=1))
    return
  span = day_label(first, True) + ("" if last == first else f" to {day_label(last, True)}")
  print(f"window: {span} (London: {res['zones']})")
  print(f"list_events: startTime {res['startTime']} endTime {res['endTime']} (no offset, no timeZone)")
  print(f"with offsets: {res['start']} to {res['end']}")


def get_window(args, now):
  if getattr(args, "window", None):
    return window(args.window, now.date())
  return None


# --- agenda ----------------------------------------------------------------------------------

def att_text(ev):
  return f"{ev['n_att']} att" if ev["n_att"] else ""


def org_text(ev):
  if ev["organiser_self"] or ev["organiser"] in pa.IAN_ADDRESSES or not ev["organiser"]:
    return ""
  return "org " + (ev["organiser_name"] or ev["organiser"])


def ev_line(ev, fields, day=None):
  bits = []
  if "time" in fields:
    if ev["all_day"]:
      t = "all day"
      if ev["edate"] - ev["sdate"] > datetime.timedelta(days=1):
        t += f" (to {day_label(ev['edate'] - datetime.timedelta(days=1))})"
      bits.append(f"{t:<11}")
    else:
      t = f"{hm(ev['start'])}-{hm(ev['end'])}"
      if day and ev["end"].date() != ev["start"].date():
        t += f" (ends {day_label(ev['end'].date())})"
      bits.append(t)
  if "cal" in fields:
    bits.append(f"{ev['cal']:<3}")
  if "id" in fields:
    bits.append(ev["id"])
  if "title" in fields:
    bits.append(pa.one_line(ev["title"], 60))
  if "flags" in fields and ev.get("flags"):
    f = []
    for x in ev["flags"]:
      if x == "CLASH":
        f.append("CLASH with " + ", ".join(f"{c['cal']} \"{pa.one_line(c['title'], 30)}\" "
                                             f"{hm(c['start'])}-{hm(c['end'])}" for c in ev["clash_with"]))
      elif x == "TIGHT":
        f.append(f"TIGHT after \"{pa.one_line(ev['tight_after']['title'], 30)}\"")
      else:
        f.append(x)
    bits.append("[" + "; ".join(f) + "]")
  extra = []
  if "att" in fields and att_text(ev):
    extra.append(att_text(ev))
  if "org" in fields and org_text(ev):
    extra.append(org_text(ev))
  if "meet" in fields and ev["meet"]:
    extra.append("Meet" if "meet.google" in ev["meet"] else "video")
  if "loc" in fields and ev["location"] and not VIDEO_RE.fullmatch(ev["location"].strip()):
    extra.append("@ " + pa.one_line(ev["location"], 40))
  if extra:
    bits.append("· " + " · ".join(extra))
  return " ".join(bits)


def parse_fields(s):
  if not s:
    return set(FIELDS)
  if s == "minimal":
    return {"time", "cal", "title", "flags"}
  out = {x.strip() for x in s.split(",") if x.strip()}
  bad = out - set(FIELDS) - {"id"}
  if bad:
    pa.die(f"unknown field(s) {', '.join(sorted(bad))}: use {','.join(FIELDS)},id or minimal", 2)
  return out


def summary(info, hidden=0, merged=0):
  bits = []
  for tag in ("W", "P"):
    if tag not in info:
      bits.append(f"{tag} not given")
      continue
    i = info[tag]
    roles = sorted(set(i["access"]))
    bits.append(f"{tag} {i['count']} events" + (f" ({'/'.join(roles)})" if roles else ""))
  if merged:
    bits.append(f"{merged} on both (W+P)")
  if hidden:
    bits.append(f"{hidden} declined hidden")
  return "; ".join(bits)


def errors(info):
  return [e for i in info.values() for e in i["errors"]]


def days_of(events, win):
  if win:
    first, after = win
  elif events:
    first = min(e["sdate"] for e in events)
    after = max(e["sdate"] for e in events) + datetime.timedelta(days=1)
  else:
    return []
  out, d = [], first
  while d < after:
    out.append(d)
    d += datetime.timedelta(days=1)
  return out


def on_day(ev, d):
  if ev["all_day"]:
    return ev["sdate"] <= d < ev["edate"]
  return ev["start"].date() == d


def prepare(args, now):
  win = get_window(args, now)
  times = win_times(*win) if win else None
  events, info = load(args.work, args.personal, args.gog, times)
  n = len(events)
  events = merge(events)
  merged = n - len(events)
  hidden = 0
  if not getattr(args, "declined", True):
    hidden = len([e for e in events if declined(e)])
    events = [e for e in events if not declined(e)]
  flag(events)
  return events, info, win, merged, hidden


def plain(ev):
  out = {k: v for k, v in ev.items() if k not in ("clash_with", "tight_after", "description", "attendees")}
  out["clash_with"] = [f"{c['cal']} {c['title']}" for c in ev.get("clash_with", [])]
  out["start"] = ev["start"].isoformat() if ev["start"] else None
  out["end"] = ev["end"].isoformat() if ev["end"] else None
  out["sdate"], out["edate"] = ev["sdate"].isoformat(), ev["edate"].isoformat()
  return out


def cmd_agenda(args, now):
  events, info, win, merged, hidden = prepare(args, now)
  if args.json:
    print(pa.as_json({"summary": summary(info, hidden, merged), "errors": errors(info),
                      "events": [plain(e) for e in events]}))
    return
  fields = parse_fields(args.fields)
  for e in errors(info):
    print(f"missing: {e}")
  print(summary(info, hidden, merged))
  clashes = []
  for e in events:
    for c in e["clash_with"]:
      if sort_key(e) < sort_key(c):
        clashes.append((e, c))
  if clashes:
    print(f"\nCLASHES ({len(clashes)})")
    for a, b in clashes:
      print(f"  {day_label(a['start'].date())} {hm(a['start'])}-{hm(a['end'])} {a['cal']} "
            f"\"{pa.one_line(a['title'], 40)}\" overlaps {hm(b['start'])}-{hm(b['end'])} {b['cal']} "
            f"\"{pa.one_line(b['title'], 40)}\"")
  pending = [e for e in events if "PENDING" in e["flags"]]
  for d in days_of(events, win):
    todays = [e for e in events if on_day(e, d)]
    if not todays and not win:
      continue
    print(f"\n{day_label(d).upper()} ({zone(d)})")
    if not todays:
      print("  (nothing)")
    for e in sorted(todays, key=lambda e: (not e["all_day"], sort_key(e))):
      mark = "⚠ " if "CLASH" in e["flags"] or "TIGHT" in e["flags"] else "  "
      print(mark + ev_line(e, fields, d))
  if pending:
    print("\nNEEDS A DECISION")
    for i, e in enumerate(pending, 1):
      when = day_label(e["sdate"]) + ("" if e["all_day"] else " " + hm(e["start"]))
      who = org_text(e)
      print(f"  {i}. {pa.one_line(e['title'], 50)} ({e['cal']}, {when}{', ' + who if who else ''}) -> accept / decline?")


# --- free ------------------------------------------------------------------------------------

def parse_hm(s):
  m = re.fullmatch(r"(\d{1,2}):?(\d{2})", s.strip())
  if not m:
    pa.die(f"bad time {s!r}: use HH:MM", 2)
  return int(m.group(1)), int(m.group(2))


def free_gaps(events, d, frm, to, min_minutes):
  """Gaps on day d between frm and to ((h, m) pairs) of at least min_minutes, as (start, end)."""
  lo = datetime.datetime(d.year, d.month, d.day, *frm, tzinfo=LONDON)
  hi = datetime.datetime(d.year, d.month, d.day, *to, tzinfo=LONDON)
  spans = sorted((max(e["start"], lo), min(e["end"], hi)) for e in events
                 if busy(e) and e["start"] < hi and e["end"] > lo)
  gaps, t = [], lo
  for s, e in spans:
    if s > t:
      gaps.append((t, s))
    t = max(t, e)
  if hi > t:
    gaps.append((t, hi))
  return [(s, e) for s, e in gaps if (e - s) >= datetime.timedelta(minutes=min_minutes)]


def dur(a, b):
  m = int((b - a).total_seconds() // 60)
  return f"{m // 60}h{m % 60:02d}" if m >= 60 else f"{m}m"


def cmd_free(args, now):
  if not args.window:
    args.window = "week"
  events, info, win, _, _ = prepare(args, now)
  frm, to = parse_hm(args.start), parse_hm(args.stop)
  res = []
  for d in days_of(events, win):
    if d.weekday() >= 5 and not args.all_days:
      continue
    res.append((d, free_gaps(events, d, frm, to, args.min)))
  if args.json:
    print(pa.as_json([{"date": d.isoformat(), "free": [[s.isoformat(), e.isoformat()] for s, e in gaps]} for d, gaps in res]))
    return
  for e in errors(info):
    print(f"missing: {e}")
  print(f"free {args.start}-{args.stop}, at least {args.min} min ({summary(info)})")
  for d, gaps in res:
    allday = [e["title"] for e in events if e["all_day"] and on_day(e, d) and not declined(e)]
    note = f"  (all day: {'; '.join(pa.one_line(t, 30) for t in allday)})" if allday else ""
    print(f"  {day_label(d)} ({zone(d)}): " + (", ".join(f"{hm(s)}-{hm(e)} ({dur(s, e)})" for s, e in gaps) or "none")
          + note)


# --- match -----------------------------------------------------------------------------------

def describe(title):
  """The recording name's description, as rename_files_with_calendar.sh makes it."""
  return "".join(c for c in title.replace(" ", "_") if c == "_" or (c.isascii() and c.isalnum()))


def recorded(meetings, stem, title):
  desc = describe(title)
  if not meetings or not desc:
    return None
  try:
    names = sorted(os.listdir(os.path.expanduser(meetings)))
  except OSError:
    return None
  pat = re.compile(rf"{stem[:8]}_\d{{4}}_{re.escape(desc)}\.")
  return next((n for n in names if pat.match(n) and not n.startswith(stem + "_")), None)


def candidates(events, t, hours=3):
  lo, hi = t - datetime.timedelta(hours=hours), t + datetime.timedelta(hours=hours)
  out = []
  for e in events:
    if e["all_day"] or e["transparent"] or declined(e) or not (e["start"] <= hi and e["end"] >= lo):
      continue
    if e["start"] <= t <= e["end"]:
      score = 0
    else:
      score = int(round(min(abs((e["start"] - t).total_seconds()), abs((e["end"] - t).total_seconds())) / 60))
    # On a tie the one starting (at or after the stem) wins, then one under way, then one that ended.
    rank = 0 if e["start"] >= t else (1 if e["end"] > t else 2)
    out.append(dict(e, score=score, starting=rank == 0, rank=rank))
  out.sort(key=lambda e: (e["score"], e["rank"], e["start"]))
  return out


def cmd_match(args, now):
  if not re.fullmatch(r"\d{8}_\d{4}", args.stem):
    pa.die(f"{args.stem!r} isn't a YYYYMMDD_HHMM stem", 2)
  t = datetime.datetime.strptime(args.stem, "%Y%m%d_%H%M").replace(tzinfo=LONDON)
  events, info = load(args.work, args.personal, args.gog,
                      (t - datetime.timedelta(hours=3), t + datetime.timedelta(hours=3)))
  cands = candidates(merge(events), t)[:3]
  for c in cands:
    c["recorded"] = recorded(args.meetings, args.stem, c["title"])
  if args.json:
    print(pa.as_json({"stem": args.stem, "time": t.isoformat(), "errors": errors(info),
                      "candidates": [{"cal": c["cal"], "title": c["title"], "start": c["start"].isoformat(),
                                      "end": c["end"].isoformat(), "score": c["score"], "n_att": c["n_att"],
                                      "recorded": c["recorded"], "description": describe(c["title"])}
                                     for c in cands]}))
    return
  for e in errors(info):
    print(f"missing: {e}")
  print(f"recording {args.stem} = {day_label(t.date(), True)} {hm(t)} {t.tzname()}")
  if not cands:
    print("  no timed event within 3 hours on the calendars given")
  for i, c in enumerate(cands, 1):
    if c["score"] == 0:
      where = "starts at the recording" if c["start"] == t else ("ends at the recording" if c["end"] == t
                                                                  else "recording inside it")
    else:
      where = f"{c['score']} min {'before it starts' if c['starting'] else 'after it ended'}"
    note = f"  (already recorded: {c['recorded']})" if c["recorded"] else ""
    print(f"{'*' if i == 1 else ' '} {i}. {c['cal']:<3} {hm(c['start'])}-{hm(c['end'])}  "
          f"{pa.one_line(c['title'], 60)}  ({c['n_att']} att; {where}){note}")
  if len(cands) > 1 and cands[0]["recorded"] and cands[0]["score"] == cands[1]["score"] and not cands[1]["recorded"]:
    print(f"  note: 1 already has a recording and 2 is as close: 2 may be the one")
  print("  n  type a name\n  x  no_calendar_match")


# --- attendees -------------------------------------------------------------------------------

def name_forms(name):
  parts = [p for p in re.split(r"[\s.]+", fold(name)) if p]
  parts = [re.sub(r"[^a-z0-9'-]", "", p) for p in parts]
  parts = [p for p in parts if p]
  if not parts:
    return None
  first, last = parts[0], parts[-1]
  f, l = first.replace("'", ""), last.replace("'", "")
  emails = {f"{f}.{l}", f"{f[0]}{l}", f"{f[0]}.{l}", f"{f}{l}", f"{f}_{l}", f"{f}-{l}"} if len(parts) > 1 else {f}
  return {"first": first, "last": last, "emails": emails, "single": len(parts) == 1}


def person_matches(forms, p):
  local = fold(p["email"].split("@")[0]) if p["email"] else ""
  if local and local in forms["emails"]:
    return True
  words = re.findall(r"[a-z0-9']+", fold(p["name"]))
  if forms["single"]:
    return False
  return forms["first"] in words and forms["last"] in words


def cmd_attendees(args, now):
  names = list(args.names)
  if args.names_file:
    with open(os.path.expanduser(args.names_file), encoding="utf-8") as f:
      names += [l.strip() for l in f if l.strip() and not l.startswith("#")]
  if not names:
    pa.die("give names, or --names-file", 2)
  win = get_window(args, now)
  events, info = load(args.work, args.personal, args.gog, win_times(*win) if win else None)
  events = merge(events)
  res = []
  for name in names:
    forms = name_forms(name)
    hits, via = [], set()
    for e in events if forms else []:
      if declined(e):
        continue
      people = [a for a in e["attendees"] if a["response"] != "declined"] + \
        ([{"email": e["organiser"], "name": e["organiser_name"]}] if e["organiser"] else [])
      matched = [p for p in people if p["email"] not in pa.IAN_ADDRESSES and person_matches(forms, p)]
      if matched:
        hits.append(e)
        via.update(p["email"] for p in matched if p["email"])
    past = [e for e in hits if (e["start"] or midnight(e["sdate"])) <= now]
    future = [e for e in hits if (e["start"] or midnight(e["sdate"])) > now]
    res.append({"name": name, "count": len(hits), "emails": sorted(via),
                "last": past[-1] if past else None, "next": future[0] if future else None})
  if args.json:
    print(pa.as_json([{"name": r["name"], "count": r["count"], "emails": r["emails"],
                       "last": r["last"] and {"date": r["last"]["sdate"], "title": r["last"]["title"], "cal": r["last"]["cal"]},
                       "next": r["next"] and {"date": r["next"]["sdate"], "title": r["next"]["title"], "cal": r["next"]["cal"]}}
                      for r in res]))
    return
  for e in errors(info):
    print(f"missing: {e}")
  for r in res:
    if not r["count"]:
      print(f"{r['name']}: none")
      continue
    bits = [f"{r['name']}: {r['count']} event(s)"]
    for k in ("last", "next"):
      e = r[k]
      if e:
        bits.append(f"{k} {day_label(e['sdate'], True)} \"{pa.one_line(e['title'], 50)}\" ({e['cal']})")
    if r["emails"]:
      bits.append("via " + ", ".join(r["emails"][:3]))
    print(", ".join(bits))


# --- verify and access -----------------------------------------------------------------------

def cmd_verify(args, now):
  events, meta = [], {}
  for v in json_values(sys.stdin.read()):
    walk(v, events, meta)
  if not events:
    pa.die("no event in the input (pipe the get_event result in)", 2)
  ev = norm(events[0], args.calendar)
  diffs = []

  def want_time(field, value, got):
    if not value:
      return
    w_dt, w_d = parse_when(value)
    if w_dt is not None:
      if got is None or w_dt != got:
        diffs.append(f"{field}: expected {w_dt:%a %d %b %H:%M %Z}, got "
                     f"{got.strftime('%a %d %b %H:%M %Z') if got else 'an all-day event'}")
    else:
      have = ev["sdate"] if field == "start" else ev["edate"]
      if not ev["all_day"] or have != w_d:
        diffs.append(f"{field}: expected all day {w_d}, got {got.isoformat() if got else have}")
  want_time("start", args.start, ev["start"])
  want_time("end", args.end, ev["end"])
  if args.title is not None and ev["title"].strip() != args.title.strip():
    diffs.append(f"title: expected {args.title!r}, got {ev['title']!r}")
  have = {a["email"] for a in ev["attendees"]}
  for a in args.attendee or []:
    if a.lower() not in have:
      diffs.append(f"attendee: {a} missing")
  if args.response and ev["response"] != enum(args.response):
    diffs.append(f"response: expected {args.response}, got {ev['response'] or 'none'}")
  if args.transparent is not None and ev["transparent"] != args.transparent:
    diffs.append(f"shown as: expected {'free' if args.transparent else 'busy'}, got {'free' if ev['transparent'] else 'busy'}")
  cal_field = str(g(events[0], "calendarId", "organizerCalendarId", default="")).lower()
  if cal_field and cal_field not in (CALS[args.calendar], "primary" if args.calendar == "W" else ""):
    diffs.append(f"calendar: expected {CALS[args.calendar]}, got {cal_field}")
  elif ev["organiser_self"] and ev["organiser"] in pa.IAN_ADDRESSES and ev["organiser"] != CALS[args.calendar]:
    diffs.append(f"calendar: expected {CALS[args.calendar]}, but the organiser is {ev['organiser']}")
  if ev["status"] == "cancelled":
    diffs.append("status: cancelled")
  if diffs:
    print("DIFFERENT\n" + "\n".join("  " + d for d in diffs))
    sys.exit(1)
  print(f"OK: {args.calendar} \"{ev['title']}\" "
        + (f"{day_label(ev['start'].date())} {hm(ev['start'])}-{hm(ev['end'])}" if ev["start"] else f"all day {ev['sdate']}"))


def cmd_access(args, now):
  _, info = load(args.work, args.personal, args.gog, None)
  bad = False
  for tag in ("W", "P"):
    if tag not in info:
      print(f"{tag}: not given")
      continue
    roles = sorted(set(info[tag]["access"]))
    errs = info[tag]["errors"]
    if errs:
      print(f"{tag}: could not read ({'; '.join(errs)})")
      bad = True
    elif not roles:
      print(f"{tag}: no accessRole in the result: check by hand")
    elif set(roles) <= {"owner", "writer"}:
      print(f"{tag}: {'/'.join(roles)}: can read and change it")
    else:
      bad = True
      print(f"{tag}: {'/'.join(roles)}: can show it but not change it.")
      if tag == "P":
        print("  " + ACCESS_FIX)
  print("Sharing only. Whether the connector's own login may write is checked with the no-op update_event "
        "(calendar skill, Setup).")
  sys.exit(1 if bad else 0)


# --- main ------------------------------------------------------------------------------------

def main():
  common = argparse.ArgumentParser(add_help=False)
  common.add_argument("--work", action="append", default=[], metavar="FILE", help="list_events result for W (- for stdin)")
  common.add_argument("--personal", action="append", default=[], metavar="FILE", help="list_events result for P")
  common.add_argument("--gog", action="append", default=[], choices=["work", "personal"],
                      help="fetch that calendar with gog for --window")
  common.add_argument("--window", help="limit to a window: today, week, next week, week-of YYYY-MM-DD, ...")
  common.add_argument("--json", action="store_true")
  common.add_argument("--now", help=argparse.SUPPRESS)
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
  sub = ap.add_subparsers(dest="cmd", required=True)
  p = sub.add_parser("window", parents=[common], help="startTime/endTime for a scope")
  p.add_argument("scope", nargs="*")
  p = sub.add_parser("agenda", parents=[common], help="one line per event, with flags")
  p.add_argument("--declined", action="store_true", help="show declined events too")
  p.add_argument("--fields", help="columns: time,cal,title,flags,att,org,meet,loc,id or minimal")
  p = sub.add_parser("free", parents=[common], help="free gaps per weekday")
  p.add_argument("--from", dest="start", default="09:00")
  p.add_argument("--to", dest="stop", default="17:30")
  p.add_argument("--min", type=int, default=90, help="minutes (90)")
  p.add_argument("--all-days", action="store_true", help="weekends too")
  p = sub.add_parser("match", parents=[common], help="calendar events nearest a recording stem")
  p.add_argument("stem")
  p.add_argument("--meetings", help="the meetings folder, to spot events already recorded")
  p = sub.add_parser("attendees", parents=[common], help="events with each person")
  p.add_argument("names", nargs="*")
  p.add_argument("--names-file")
  p = sub.add_parser("verify", parents=[common], help="check a get_event result (stdin) is as meant")
  p.add_argument("--calendar", required=True, choices=["W", "P"])
  p.add_argument("--start")
  p.add_argument("--end")
  p.add_argument("--title")
  p.add_argument("--attendee", action="append")
  p.add_argument("--response", choices=["accepted", "declined", "tentative", "needsAction"])
  p.add_argument("--free", dest="transparent", action="store_const", const=True, help="expect it shown as free")
  p.add_argument("--busy", dest="transparent", action="store_const", const=False, help="expect it shown as busy")
  sub.add_parser("access", parents=[common], help="accessRole of each calendar")
  args = ap.parse_args()
  now = now_london(args.now)
  {"window": cmd_window, "agenda": cmd_agenda, "free": cmd_free, "match": cmd_match, "attendees": cmd_attendees,
   "verify": cmd_verify, "access": cmd_access}[args.cmd](args, now)


if __name__ == "__main__":
  main()
