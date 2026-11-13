#!/usr/bin/env python3
"""Turn a plan written in simple markdown into the email the skills send Ian, as JSON.

  pa-mail-html.py --kind weekly --date 2026-11-16 < plan.md
  pa-mail-html.py --kind weekly --date 2026-11-16 --missing "personal calendar" --file plan.md
  pa-mail-html.py --kind interview --date 2026-11-11 --detail "Jane Doe 12:15, John Roe 15:00" < prep.md
  pa-mail-html.py --kind weekly --date 2026-11-16 --subject-only

Prints {"to": [...], "subject": ..., "htmlBody": ...}, ready for Gmail's send_message. The
recipient is always Ian's work address and can't be changed. The subject is fixed by the kind:
  weekly     Weekly plan: Mon 16 – Fri 20 Nov   (--date is any day of that week)
  interview  Interview prep: Wed 11 Nov - <--detail>
Under it goes "All times GMT" (or BST, or both across a clock change) for those days, and a
"Missing: ..." line first when --missing is given (repeatable).

The markdown: `#` headings (h2, and h3 for `##` and below), `-`, `*` or `1.` lists (indent two
spaces to nest), **bold**, `code`, [text](https://...) and bare https:// links, and blank lines
between paragraphs. Everything else is HTML-escaped, so text from calendars or tasks can't add
markup.
"""

import argparse
import datetime
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

LONDON = ZoneInfo("Europe/London")
LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)|(https?://[^\s<>()\"']*[^\s<>()\"'.,;:!?])")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")


def zone(d):
  return datetime.datetime(d.year, d.month, d.day, 12, tzinfo=LONDON).tzname()


def zones_line(first, days):
  zs = []
  for i in range(days):
    d = first + datetime.timedelta(days=i)
    if not zs or zs[-1][0] != zone(d):
      zs.append((zone(d), d))
  if len(zs) == 1:
    return f"All times {zs[0][0]}"
  bits = []
  for i, (z, d) in enumerate(zs):
    e = d if i else zs[1][1] - datetime.timedelta(days=1)
    bits.append(f"{z} {'from' if i else 'until'} {e:%a} {e.day} {e:%b}")
  return "All times " + ", ".join(bits)


def subject(kind, date, detail=""):
  if kind == "weekly":
    mon = date - datetime.timedelta(days=date.weekday())
    fri = mon + datetime.timedelta(days=4)
    left = f"Mon {mon.day}" + (f" {mon:%b}" if mon.month != fri.month else "")
    return f"Weekly plan: {left} – Fri {fri.day} {fri:%b}"
  s = f"Interview prep: {date:%a} {date.day} {date:%b}"
  return s + (f" - {' '.join(detail.split())}" if detail and detail.strip() else "")


def fmt(text):
  t = html.escape(text, quote=True)
  t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
  t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
  return t


def inline(text):
  out, pos = [], 0
  for m in LINK_RE.finditer(text):
    out.append(fmt(text[pos:m.start()]))
    if m.group(1):
      out.append(f'<a href="{html.escape(m.group(2), quote=True)}">{fmt(m.group(1))}</a>')
    else:
      u = html.escape(m.group(3), quote=True)
      out.append(f'<a href="{u}">{u}</a>')
    pos = m.end()
  out.append(fmt(text[pos:]))
  return "".join(out)


def to_html(md):
  out, para, stack = [], [], []  # stack of (indent, tag) for open lists

  def close_para():
    if para:
      out.append("<p>" + "<br>".join(inline(l) for l in para) + "</p>")
      para.clear()

  def close_lists(indent=-1):
    while stack and stack[-1][0] > indent:
      out.append(f"</li></{stack.pop()[1]}>")

  for raw in md.replace("\r\n", "\n").split("\n"):
    line = raw.rstrip()
    if not line.strip():
      close_para()
      close_lists()
      continue
    h = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
    m = LIST_RE.match(line)
    if h:
      close_para()
      close_lists()
      level = 2 if len(h.group(1)) == 1 else 3 if len(h.group(1)) <= 3 else 4
      out.append(f"<h{level}>{inline(h.group(2))}</h{level}>")
    elif m:
      close_para()
      indent, tag = len(m.group(1).expandtabs(2)), "ol" if m.group(2)[0].isdigit() else "ul"
      close_lists(indent)
      if stack and stack[-1][0] == indent:
        if stack[-1][1] != tag:
          out.append(f"</li></{stack.pop()[1]}><{tag}><li>")
          stack.append((indent, tag))
        else:
          out.append("</li><li>")
      else:
        out.append(f"<{tag}><li>")
        stack.append((indent, tag))
      out.append(inline(m.group(3)))
    elif stack:
      out.append("<br>" + inline(line.strip()))  # a continuation line of a list item
    else:
      para.append(line.strip())
  close_para()
  close_lists()
  return "\n".join(out)


def build(md, kind, date, missing=(), detail=""):
  head = []
  if missing:
    head.append('<p style="color:#b00000"><b>Missing:</b> ' + "; ".join(inline(m) for m in missing) + "</p>")
  head.append(f"<p>{zones_line(date - datetime.timedelta(days=date.weekday()), 7) if kind == 'weekly' else zones_line(date, 1)}</p>")
  return {"to": [pa.MAILBOXES["work"]], "subject": subject(kind, date, detail),
          "htmlBody": "\n".join(head) + "\n" + to_html(md)}


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("--kind", required=True, choices=["weekly", "interview"])
  ap.add_argument("--date", required=True, help="YYYY-MM-DD: a day of the week planned, or the interview day")
  ap.add_argument("--missing", action="append", default=[], help="what couldn't be read (repeatable)")
  ap.add_argument("--detail", default="", help="interview: names and times for the subject")
  ap.add_argument("--file", help="the markdown (default: stdin)")
  ap.add_argument("--subject-only", action="store_true")
  args = ap.parse_args()
  try:
    date = datetime.date.fromisoformat(args.date)
  except ValueError:
    pa.die(f"bad date {args.date!r}: use YYYY-MM-DD", 2)
  if args.subject_only:
    print(subject(args.kind, date, args.detail))
    return
  md = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
  if not md.strip():
    pa.die("no plan text (stdin or --file)", 2)
  print(json.dumps(build(md, args.kind, date, args.missing, args.detail), ensure_ascii=False, indent=1))


if __name__ == "__main__":
  main()
