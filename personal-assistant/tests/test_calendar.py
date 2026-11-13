#!/usr/bin/env python3
"""Tests for calendar-events.py, weekly-plan-gather.py, pa-mail-html.py, interview-gather.py and
the timesheet skill's timesheet.py, against made-up calendar and grid fixtures.

  python3 -m unittest discover -s personal-assistant/tests -p 'test_calendar.py' -v

The names are made up (the repo is public). Nothing here reaches a real calendar, gog or Chrome.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_scripts import Base, HERE, WORK, PERSONAL  # noqa: E402

TIMESHEET = os.path.join(HERE, "..", "skills", "timesheet", "timesheet.py")
IVANA = "ivana@container-solutions.com"


def ev(eid, title, start, end, **kw):
  """A Google Calendar API event; start/end are dateTime strings, or YYYY-MM-DD for all-day."""
  def when(v):
    return {"date": v} if len(v) == 10 else {"dateTime": v}
  e = {"id": eid, "summary": title, "start": when(start), "end": when(end), "status": "confirmed"}
  e.update(kw)
  return e


def me(addr=WORK, status="accepted"):
  return {"email": addr, "self": True, "responseStatus": status}


class Cal(Base):
  def write(self, name, obj, raw=False):
    path = os.path.join(self.tmp, name)
    with open(path, "w") as f:
      f.write(obj if raw else json.dumps(obj))
    return path

  def cal(self, *args, stdin="", check=0):
    return self.run_script("calendar-events.py", *args, stdin=stdin, check=check).stdout


# --- calendar-events.py ----------------------------------------------------------------------

class Window(Cal):
  def test_clock_change_week(self):
    out = self.cal("window", "week", "--now", "2026-10-22T10:00")
    self.assertIn("Mon 19 Oct 2026 to Sun 25 Oct 2026", out)
    self.assertIn("BST until Sat 24 Oct, GMT from Sun 25 Oct", out)
    self.assertIn("startTime 2026-10-19T00:00:00 endTime 2026-10-26T00:00:00", out)
    self.assertIn("2026-10-19T00:00:00+01:00 to 2026-10-26T00:00:00+00:00", out)

  def test_scopes(self):
    def win(*a):
      return json.loads(self.cal("window", *a, "--json", "--now", "2026-10-22T10:00"))
    self.assertEqual(win("today")["first"], "2026-10-22")
    self.assertEqual(win("tomorrow")["first"], "2026-10-23")
    nw = win("next", "week")
    self.assertEqual((nw["first"], nw["last"], nw["zones"]), ("2026-10-26", "2026-11-01", "GMT"))
    self.assertEqual(win("invites")["last"], "2026-11-18")
    self.assertEqual(win("thu")["first"], "2026-10-22")
    self.assertEqual(win("wednesday")["first"], "2026-10-28")
    wo = win("week-of", "2026-10-28")
    self.assertEqual((wo["first"], wo["last"]), ("2026-10-26", "2026-11-01"))
    d = win("2026-10-25")
    self.assertEqual((d["start"], d["end"]), ("2026-10-25T00:00:00+01:00", "2026-10-26T00:00:00+00:00"))
    self.assertEqual(win("2026-10-23..2026-10-27")["last"], "2026-10-27")
    self.run_script("calendar-events.py", "window", "someday", check=2)


class Agenda(Cal):
  def setUp(self):
    super().setUp()
    work = {"accessRole": "owner", "events": [
      ev("w1", "Daily standup", "2026-10-19T09:30:00Z", "2026-10-19T10:00:00Z", attendees=[me(), {"email": "a@container-solutions.com"}]),
      ev("w2", "Client call", "2026-10-19T11:00:00Z", "2026-10-19T12:00:00Z", hangoutLink="https://meet.google.com/abc-defg-hij",
         organizer={"email": "jane.doe@acme.example", "displayName": "Jane Doe"},
         attendees=[me(status="NEEDS_ACTION"), {"email": "jane.doe@acme.example", "organizer": True}]),
      ev("w3", "Office day", "2026-10-19T08:00:00Z", "2026-10-19T19:30:00Z", transparency="transparent"),
      ev("w4", "Holiday", "2026-10-23", "2026-10-24"),
      ev("w5", "Old sync", "2026-10-20T09:00:00Z", "2026-10-20T10:00:00Z", attendees=[me(status="declined")]),
      ev("w6", "Dinner", "2026-10-20T18:00:00Z", "2026-10-20T20:00:00Z", iCalUID="shared-1@example"),
      ev("w7", "Park Run", "2026-10-24T08:00:00Z", "2026-10-24T09:00:00Z"),
      ev("w8", "After the change", "2026-10-26T10:00:00Z", "2026-10-26T11:00:00Z"),
      ev("w9", "Gone", "2026-10-21T10:00:00Z", "2026-10-21T11:00:00Z", status="cancelled"),
      ev("w10", "Site visit", "2026-10-21T13:00:00Z", "2026-10-21T14:00:00Z", location="1 Example Street, London"),
      ev("w11", "Lunch", "2026-10-21T14:10:00Z", "2026-10-21T15:00:00Z", location="Cafe Nowhere, Leeds"),
    ]}
    # The connector's MCP wrapper: a text block holding the JSON.
    self.work = self.write("w.json", [{"type": "text", "text": json.dumps(work)}])
    personal = {"accessRole": "reader", "items": [
      ev("p1", "Dentist", "2026-10-19T12:30:00+01:00", "2026-10-19T13:30:00+01:00", location="1 High St"),
      ev("p2", "Dinner", "2026-10-20T19:00:00+01:00", "2026-10-20T21:00:00+01:00", iCalUID="shared-1@example"),
      ev("p3", "park run", "2026-10-24T09:00:00+01:00", "2026-10-24T10:00:00+01:00"),
    ]}
    # The harness's saved oversized result: some words, then the JSON.
    self.personal = self.write("p.txt", "Output saved. Result:\n" + json.dumps(personal), raw=True)

  def agenda(self, *a):
    return self.cal("agenda", "--work", self.work, "--personal", self.personal, "--window", "week-of 2026-10-19", *a)

  def test_flags_merge_and_filters(self):
    out = self.agenda()
    self.assertIn("W 9 events (owner); P 3 events (reader); 2 on both (W+P); 1 declined hidden", out)
    self.assertNotIn("Old sync", out)
    self.assertNotIn("Gone", out)
    self.assertNotIn("After the change", out)
    self.assertIn("CLASHES (1)", out)
    self.assertIn('Mon 19 Oct 12:00-13:00 W "Client call" overlaps 12:30-13:30 P "Dentist"', out)
    lines = out.splitlines()
    call = next(l for l in lines if "Client call [" in l)
    self.assertTrue(call.startswith("⚠ 12:00-13:00 W"))
    self.assertIn("PENDING", call)
    self.assertIn("org Jane Doe", call)
    self.assertIn("Meet", call)
    self.assertIn("2 att", call)
    self.assertIn("09:00-20:30 W   Office day [FREE]", out)   # transparent: no clash with it
    self.assertIn("19:00-21:00 W+P Dinner", out)               # same iCalUID
    self.assertIn("09:00-10:00 W+P Park Run", out)             # same title and start
    self.assertIn("all day     W   Holiday", out)
    self.assertIn("SUN 25 OCT (GMT)", out)
    self.assertIn("SAT 24 OCT (BST)", out)
    tight = next(l for l in lines if "Lunch" in l)
    self.assertIn("TIGHT after \"Site visit\"", tight)
    self.assertIn("NEEDS A DECISION\n  1. Client call (W, Mon 19 Oct 12:00, org Jane Doe)", out)

  def test_declined_and_minimal_fields(self):
    out = self.agenda("--declined", "--fields", "minimal")
    self.assertIn("Old sync [declined]", out)
    self.assertIn("Client call [CLASH with P \"Dentist\" 12:30-13:30; PENDING]\n", out)

  def test_json(self):
    res = json.loads(self.agenda("--json"))
    call = next(e for e in res["events"] if e["title"] == "Client call")
    self.assertEqual(call["flags"][:2], ["CLASH", "PENDING"])
    self.assertEqual(call["clash_with"], ["P Dentist"])

  def test_free(self):
    out = self.cal("free", "--work", self.work, "--personal", self.personal, "--window", "week-of 2026-10-19")
    self.assertIn("Mon 19 Oct (BST): 09:00-10:30 (1h30), 13:30-17:30 (4h00)", out)
    self.assertIn("Fri 23 Oct (BST): 09:00-17:30 (8h30)  (all day: Holiday)", out)
    self.assertNotIn("Sat", out)

  def test_access(self):
    p = self.run_script("calendar-events.py", "access", "--work", self.work, "--personal", self.personal, check=1)
    self.assertIn("W: owner: can read and change it", p.stdout)
    self.assertIn("P: reader: can show it but not change it.", p.stdout)
    self.assertIn("Make changes and manage sharing", p.stdout)

  def test_gog(self):
    fake = os.path.join(self.tmp, "gog")
    data = self.write("gog-out.json", [ev("g1", "From gog", "2026-10-22T09:00:00+01:00", "2026-10-22T10:00:00+01:00")])
    with open(fake, "w") as f:
      f.write(f"#!/bin/sh\necho \"$@\" >> {self.tmp}/gog-args\ncat {data}\n")
    os.chmod(fake, 0o755)
    self.env["PA_GOG"] = fake
    out = self.cal("agenda", "--gog", "work", "--window", "week-of 2026-10-19")
    self.assertIn("09:00-10:00 W   From gog", out)
    with open(os.path.join(self.tmp, "gog-args")) as f:
      called = f.read()
    self.assertIn("--gmail-no-send", called)
    self.assertIn("calendar events ian.miell@container-solutions.com --from 2026-10-19T00:00:00+01:00", called)


class Match(Cal):
  def setUp(self):
    super().setUp()
    self.work = self.write("w.json", {"events": [
      ev("a", "Weekly sync", "2026-10-15T09:30:00Z", "2026-10-15T10:30:00Z", attendees=[me(), {"email": "x@container-solutions.com"}]),
      ev("b", "Acme / CS - Follow up", "2026-10-15T10:30:00Z", "2026-10-15T11:00:00Z"),
      ev("c", "Lunch", "2026-10-15T12:00:00Z", "2026-10-15T13:00:00Z"),
      ev("d", "Busy marker", "2026-10-15T10:00:00Z", "2026-10-15T12:00:00Z", transparency="transparent"),
      ev("e", "Declined", "2026-10-15T10:30:00Z", "2026-10-15T11:30:00Z", attendees=[me(status="declined"), {"email": "q@x.example"}]),
      ev("f", "Conference", "2026-10-15", "2026-10-16"),
    ]})

  def test_boundary_prefers_the_one_starting(self):
    out = self.cal("match", "20261015_1130", "--work", self.work)
    self.assertIn("recording 20261015_1130 = Thu 15 Oct 2026 11:30 BST", out)
    lines = out.splitlines()
    self.assertTrue(lines[1].startswith("* 1. W   11:30-12:00  Acme / CS - Follow up"), out)
    self.assertIn("starts at the recording", lines[1])
    self.assertTrue(lines[2].startswith("  2. W   10:30-11:30  Weekly sync  (2 att; ends at the recording)"), out)
    self.assertIn("3. W   13:00-14:00  Lunch", lines[3])
    for dropped in ("Busy marker", "Declined", "Conference"):
      self.assertNotIn(dropped, out)

  def test_minutes_to_the_nearer_edge_and_recorded(self):
    with open(os.path.join(self.gtd, "meetings", "20261015_1030_Weekly_sync.txt"), "w") as f:
      f.write("x")
    out = self.cal("match", "20261015_1125", "--work", self.work, "--meetings", os.path.join(self.gtd, "meetings"))
    self.assertIn("* 1. W   10:30-11:30  Weekly sync", out)
    self.assertIn("already recorded: 20261015_1030_Weekly_sync.txt", out)
    self.assertIn("5 min before it starts", out)
    res = json.loads(self.cal("match", "20261015_1125", "--work", self.work, "--json"))
    self.assertEqual([c["score"] for c in res["candidates"]], [0, 5, 95])
    self.assertEqual(res["candidates"][1]["description"], "Acme__CS__Follow_up")


class Attendees(Cal):
  def test_accent_folding_and_email_forms(self):
    work = self.write("w.json", [
      ev("1", "Intro", "2026-09-01T10:00:00Z", "2026-09-01T11:00:00Z",
         attendees=[me(), {"email": "o.yilmaz@acme.example"}]),
      ev("2", "Review", "2026-10-01T10:00:00Z", "2026-10-01T11:00:00Z",
         attendees=[me(), {"email": "someone@corp.example", "displayName": "Önsel Yılmaz"}]),
      ev("3", "Next", "2026-12-01T10:00:00Z", "2026-12-01T11:00:00Z",
         attendees=[me(), {"email": "onsel.yilmaz@corp.example"}]),
      ev("4", "Other", "2026-10-02T10:00:00Z", "2026-10-02T11:00:00Z",
         attendees=[me(), {"email": "jdoe@acme.example"}]),
    ])
    out = self.cal("attendees", "Onsel Yilmaz", "Jane Doe", "Nobody Here", "--work", work, "--now", "2026-11-01T10:00")
    lines = out.splitlines()
    self.assertTrue(lines[0].startswith('Onsel Yilmaz: 3 event(s), last Thu 1 Oct 2026 "Review" (W), next Tue 1 Dec 2026'), out)
    self.assertIn("o.yilmaz@acme.example", lines[0])
    self.assertTrue(lines[1].startswith("Jane Doe: 1 event(s)"), out)
    self.assertEqual(lines[2], "Nobody Here: none")
    names = self.write("names.txt", "# people\nJane Doe\n", raw=True)
    self.assertIn("Jane Doe: 1 event(s)", self.cal("attendees", "--names-file", names, "--work", work))


class Verify(Cal):
  EVENT = {"id": "x1", "summary": "Catch up", "start": {"dateTime": "2026-11-16T10:00:00Z"},
           "end": {"dateTime": "2026-11-16T10:30:00Z"},
           "organizer": {"email": WORK, "self": True},
           "attendees": [{"email": WORK, "self": True, "responseStatus": "accepted"}, {"email": "jane@acme.example"}]}

  def test_ok(self):
    out = self.cal("verify", "--calendar", "W", "--start", "2026-11-16T10:00", "--end", "2026-11-16T10:30",
                   "--title", "Catch up", "--attendee", "jane@acme.example", "--response", "accepted",
                   stdin=json.dumps([{"type": "text", "text": json.dumps(self.EVENT)}]))
    self.assertIn('OK: W "Catch up" Mon 16 Nov 10:00-10:30', out)

  def test_differences(self):
    p = self.run_script("calendar-events.py", "verify", "--calendar", "P", "--start", "2026-11-16T11:00",
                        "--title", "Catch-up", "--attendee", "bob@acme.example", stdin=json.dumps(self.EVENT), check=1)
    self.assertIn("start: expected Mon 16 Nov 11:00 GMT, got Mon 16 Nov 10:00 GMT", p.stdout)
    self.assertIn("title: expected 'Catch-up'", p.stdout)
    self.assertIn("attendee: bob@acme.example missing", p.stdout)
    self.assertIn("calendar: expected ian.miell@gmail.com", p.stdout)


# --- pa-mail-html.py -------------------------------------------------------------------------

class MailHtml(Cal):
  def test_weekly(self):
    md = "# Shape\n- **Mon**: <b>x</b> & [doc](https://x.example/a?b=1&c=2)\n  - nested\n- two\n\nPara https://meet.google.com/abc.\n"
    res = json.loads(self.run_script("pa-mail-html.py", "--kind", "weekly", "--date", "2026-10-21",
                                     "--missing", "personal calendar", stdin=md, check=0).stdout)
    self.assertEqual(res["to"], [WORK])
    self.assertEqual(res["subject"], "Weekly plan: Mon 19 – Fri 23 Oct")
    body = res["htmlBody"]
    self.assertTrue(body.startswith('<p style="color:#b00000"><b>Missing:</b> personal calendar</p>'))
    self.assertIn("All times BST until Sat 24 Oct, GMT from Sun 25 Oct", body)
    self.assertIn("<h2>Shape</h2>", body)
    self.assertIn("<b>Mon</b>: &lt;b&gt;x&lt;/b&gt; &amp; <a href=\"https://x.example/a?b=1&amp;c=2\">doc</a>", body)
    self.assertIn("<ul><li>\nnested", body)
    self.assertIn('<a href="https://meet.google.com/abc">https://meet.google.com/abc</a>.', body)

  def test_subjects(self):
    def subj(*a):
      return self.run_script("pa-mail-html.py", "--subject-only", *a, check=0).stdout.strip()
    self.assertEqual(subj("--kind", "weekly", "--date", "2026-11-30"), "Weekly plan: Mon 30 Nov – Fri 4 Dec")
    self.assertEqual(subj("--kind", "interview", "--date", "2026-11-11", "--detail", "Jane Doe 12:15, John Roe 15:00"),
                     "Interview prep: Wed 11 Nov - Jane Doe 12:15, John Roe 15:00")
    res = json.loads(self.run_script("pa-mail-html.py", "--kind", "interview", "--date", "2026-11-11",
                                     stdin="hi", check=0).stdout)
    self.assertIn("<p>All times GMT</p>", res["htmlBody"])


# --- weekly-plan-gather.py -------------------------------------------------------------------

class WeeklyGather(Cal):
  def test_week(self):
    self.task(5, "todo", "# CS: Write the proposal (oct 30th)\nTask Number: 5\n\n" + "".join(f"note {i}\n" for i in range(20)))
    os.makedirs(os.path.join(self.gtd, "priority", "high"))
    os.symlink("../../tasks/5", os.path.join(self.gtd, "priority", "high", "5"))
    self.task(6, "todo", "# HOME: Low thing\nTask Number: 6\n")
    work = self.write("w.json", {"events": [
      ev("1", "Planning", "2026-10-26T10:00:00Z", "2026-10-26T11:00:00Z"),
      ev("2", "Overlap", "2026-10-26T10:30:00Z", "2026-10-26T11:30:00Z"),
      ev("3", "Saturday", "2026-10-24T10:00:00+01:00", "2026-10-24T11:00:00+01:00"),
    ]})
    out = self.run_script("weekly-plan-gather.py", "--work", work, "--now", "2026-10-25T18:00", check=0).stdout
    self.assertIn("WEEK Mon 26 Oct to Fri 30 Oct 2026", out)
    self.assertIn("times London: GMT", out)
    self.assertIn("subject: Weekly plan: Mon 26 – Fri 30 Oct", out)
    self.assertIn("missing: personal calendar (not given)", out)
    self.assertIn("CLASHES (1)", out)
    self.assertIn("MON 26 OCT (GMT): 2 meeting(s), 1.5h busy", out)
    self.assertIn("free 09:00-17:30 >= 90m: 11:30-17:30 (6h00)", out)  # 09:00-10:00 is under 90 minutes
    self.assertNotIn("Saturday", out)
    self.assertIn("CS: Write the proposal", out)
    self.assertIn("#5 CS: Write the proposal (oct 30th) (high)", out)
    self.assertIn("    note 19", out)
    self.assertNotIn("    note 7\n", out)
    self.assertNotIn("#6", out)

  def test_monday_and_bst_week(self):
    out = self.run_script("weekly-plan-gather.py", "--monday", "2026-10-19", "--window-only", check=0).stdout
    self.assertIn("BST until Sat 24 Oct, GMT from Sun 25 Oct", out)
    self.assertIn("startTime 2026-10-19T00:00:00 endTime 2026-10-26T00:00:00", out)
    self.run_script("weekly-plan-gather.py", "--monday", "2026-10-20", check=2)


# --- interview-gather.py ---------------------------------------------------------------------

class InterviewGather(Cal):
  def test_interviews(self):
    with open(os.path.join(self.gtd, "people", "Jane_Doe.md"), "w") as f:
      f.write("## Jane Doe\n- Email: jane@candidate.example\n- Level: met\n")
    work = self.write("w.json", {"events": [
      ev("1", "Technical interview: Jane Doe", "2026-11-11T12:15:00Z", "2026-11-11T13:15:00Z",
         organizer={"email": IVANA}, hangoutLink="https://meet.google.com/aaa-bbbb-ccc",
         description='CV: <a href="https://drive.google.com/file/d/abc">CV</a> Ticket CE-42, notes https://docs.google.com/document/d/xyz',
         attachments=[{"title": "Jane Doe CV.pdf", "fileUrl": "https://drive.google.com/file/d/abc"}],
         attendees=[me(status="needsAction"), {"email": IVANA, "organizer": True},
                    {"email": "bob.roe@container-solutions.com", "displayName": "Bob Roe", "responseStatus": "accepted"},
                    {"email": "jane@candidate.example", "displayName": "Jane Doe"}]),
      ev("2", "Pairing Interview - John Roe", "2026-11-11T15:00:00Z", "2026-11-11T16:00:00Z",
         organizer={"email": "someone@container-solutions.com"}, attendees=[me()]),
      ev("3", "Team lunch", "2026-11-11T13:30:00Z", "2026-11-11T14:00:00Z"),
      ev("4", "Interview tomorrow", "2026-11-12T10:00:00Z", "2026-11-12T11:00:00Z", organizer={"email": IVANA}),
    ]})
    mail = self.write("thread.txt", "Hi, her GitHub handle: janedoe-dev and see https://github.com/ContainerSolutions/API-Exercise\n"
                      "Jira CE-43\n", raw=True)
    out = self.run_script("interview-gather.py", "--work", work, "--date", "2026-11-11", "--mail-file", mail, check=0).stdout
    self.assertIn("INTERVIEWS Wed 11 Nov 2026 (all times GMT): 2 found, 1 from Ivana", out)
    self.assertIn("subject: Interview prep: Wed 11 Nov - Jane Doe 12:15", out)
    self.assertIn("1. 12:15-13:15 Technical interview: Jane Doe", out)
    self.assertIn("from Ivana: yes", out)
    self.assertIn("stage: technical; Ian: NOT RESPONDED", out)
    self.assertIn("co-interviewers: Bob Roe (accepted)", out)
    self.assertIn("candidate: Jane Doe <jane@candidate.example> (attendee)", out)
    self.assertIn("meet: https://meet.google.com/aaa-bbbb-ccc", out)
    self.assertIn("link (Jane Doe CV.pdf): https://drive.google.com/file/d/abc", out)
    self.assertIn("link (doc): https://docs.google.com/document/d/xyz", out)
    self.assertIn("ticket: CE-42 https://container-solutions.atlassian.net/browse/CE-42", out)
    self.assertIn("people/ Jane Doe: Jane_Doe.md", out)
    self.assertIn("2. 15:00-16:00 Pairing Interview - John Roe", out)
    self.assertIn("from Ivana: no (organiser someone@container-solutions.com): ask Ian", out)
    self.assertIn("stage: pairing", out)
    self.assertIn("candidate: John Roe (from the title)", out)
    self.assertNotIn("Team lunch", out)
    self.assertNotIn("Interview tomorrow", out)
    self.assertIn("github: janedoe-dev", out)
    self.assertNotIn("github: ContainerSolutions", out)
    self.assertIn("ticket: CE-43", out)

  def test_none(self):
    work = self.write("w.json", [])
    out = self.run_script("interview-gather.py", "--work", work, "--date", "2026-11-11", check=0).stdout
    self.assertIn("no interviews", out)


# --- timesheet.py ----------------------------------------------------------------------------

def grid(status, rows, week="W44", total=""):
  return {"week": week, "weekNumber": 44, "status": status, "editable": status == "NOT SUBMITTED",
          "rows": [{"project": p, "client": "CS Internal", "cells": dict(c)} for p, c in rows.items()],
          "totals": {"week": total}, "warnings": []}


EMPTY = {d: "" for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")}


class Timesheet(Cal):
  def ts(self, *a, check=0, stdin=""):
    return self.run_script(None, *a, script=TIMESHEET, check=check, stdin=stdin).stdout

  def test_propose(self):
    prev = grid("BEING REVIEWED", {"CCF": dict(EMPTY, Mon="8:00", Tue="8:00"),
                                   "Pre sales work": dict(EMPTY, Wed="8:00", Thu="8:00", Fri="8:00")})
    # This week (w/c Mon 21 Dec 2026): Ian has already put Tue down as pre-sales; Fri is Christmas
    # Day; Thu is annual leave on the personal calendar.
    now = grid("NOT SUBMITTED", {"Pre sales work": dict(EMPTY, Tue="8:00")})
    personal = self.write("p.json", [ev("l", "Annual leave", "2026-12-24", "2026-12-25")])
    work = self.write("w.json", [ev("m", "Acme discovery", "2026-12-23T10:00:00Z", "2026-12-23T11:00:00Z",
                                    attendees=[me(), {"email": "jane@acme.example"}])])
    out = self.ts("propose", "--monday", "2026-12-21", "--grid", json.dumps(now), "--prev", self.write("prev.json", prev),
                  "--work", work, "--personal", personal)
    self.assertIn("W44 (21 Dec - 27 Dec): NOT SUBMITTED, needs 4 cell(s) changed", out)
    self.assertIn("| CCF | 8:00 |  |  |  |  | 8 h |", out)
    self.assertIn("| Pre sales work |  | 8:00 | 8:00 |  |  | 16 h |", out)
    self.assertIn("| Holiday (vacation) |  |  |  | 8:00 | 8:00 | 16 h |", out)
    self.assertIn("Tue: already in the grid", out)
    self.assertIn("Thu: off: P \"Annual leave\" (all day)", out)
    self.assertIn("Fri: bank holiday: Christmas Day", out)
    self.assertIn("Holiday (vacation) Thu: empty -> 8:00  (no row yet: + Add row)", out)
    self.assertIn("Wed: 1 client/prospect meeting(s) (Acme discovery) -> pre-sales?", out)
    plan = json.loads(out.split("plan: ", 1)[1])
    self.assertEqual(plan["CCF"]["Mon"], "8:00")
    self.assertEqual(plan["Pre sales work"]["Mon"], "")
    self.assertIn("total 40:00", out)

  def test_locked(self):
    out = self.ts("propose", "--monday", "2026-10-26", "--grid", json.dumps(grid("APPROVED", {})), check=3)
    self.assertIn("LOCKED", out)

  def test_check(self):
    plan = {"CCF": {"Mon": "8:00", "Tue": "8:00", "Wed": ""}, "Pre sales work": {"Wed": "8:00"}}
    good = grid("NOT SUBMITTED", {"CCF": dict(EMPTY, Mon="8:00", Tue="8", Thu="8:00"),
                                  "Pre sales work": dict(EMPTY, Wed="8:00")}, total="32:00")
    out = self.ts("check", "--plan", json.dumps(plan), "--grid", "-", stdin=json.dumps(json.dumps(good)))
    self.assertIn("OK: every planned cell matches; week total 32:00", out)
    bad = grid("NOT SUBMITTED", {"CCF": dict(EMPTY, Mon="8:00", Wed="8:00")})
    out = self.ts("check", "--plan", json.dumps(plan), "--grid", json.dumps(bad), check=1)
    self.assertIn("CCF Tue: expected 8:00, grid has empty", out)
    self.assertIn("CCF Wed: expected empty, grid has 8:00", out)
    self.assertIn("Pre sales work: no row in the grid", out)

  def test_submitted_and_week(self):
    self.assertIn("BEING REVIEWED: submitted", self.ts("submitted", "--grid", json.dumps(grid("Being reviewed", {}))))
    self.assertIn("not submitted", self.ts("submitted", "--grid", json.dumps(grid("NOT SUBMITTED", {})), check=1))
    out = self.ts("week", "--today", "2026-11-03", "--last-grid", json.dumps(grid("NOT SUBMITTED", {})))
    self.assertIn("do last week first: W44 (26 Oct - 1 Nov)", out)
    out = self.ts("week", "--today", "2026-11-03", "--last-grid", json.dumps(grid("APPROVED", {})))
    self.assertIn("this week: W45 (2 Nov - 8 Nov); monday 2026-11-02", out)
    self.assertIn("read last week first", self.ts("week", "--today", "2026-11-02", check=2))
    self.assertIn("this week: W45", self.ts("week", "--today", "2026-11-04"))


if __name__ == "__main__":
  unittest.main()
