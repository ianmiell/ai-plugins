#!/usr/bin/env python3
"""Tests for linkedin-state.py's download hand-off, STOP/RERUN signals, saved-JSON readers,
mail queries, export lookup and gog failures.

  python3 -m unittest discover -s personal-assistant/tests -p 'test_linkedin.py' -v

Made-up people in temporary folders (Base in test_scripts.py): PA_DOWNLOADS is a fake Downloads
folder, PA_LINKEDIN_STATE a fake state folder, and PA_GOG a fake gog.
"""

import json
import os
import stat
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_scripts import Base, LINKEDIN, PERSONAL, WORK, msg  # noqa: E402


def profile(slug):
  return f"https://www.linkedin.com/in/{slug}"


class LinkedIn(Base):
  def setUp(self):
    super().setUp()
    self.dl = self.env["PA_DOWNLOADS"]
    os.makedirs(self.dl)
    self.state = self.env["PA_LINKEDIN_STATE"]

  def li(self, *args, stdin="", check=None):
    return self.run_script(None, *args, stdin=stdin, script=LINKEDIN, check=check)

  def download(self, kind, rows, stamp="20261113T080000Z", count=None, age=0, name=None):
    path = os.path.join(self.dl, name or f"pa-linkedin-{kind}-{stamp}.json")
    with open(path, "w") as f:
      json.dump({"kind": kind, "count": len(rows) if count is None else count, "rows": rows}, f)
    t = time.time() - age
    os.utime(path, (t, t))
    return path

  def log_text(self, name="linkedin-invites.log"):
    with open(os.path.join(self.state, name)) as f:
      return f.read()

  # --- the download hand-off

  def test_queue_from_download(self):
    old = self.download("viewers", [{"url": profile("old-one"), "name": "Old One"}], "20261113T070000Z", age=60)
    new = self.download("viewers", [{"url": profile(x), "name": f"{x.title()} Person"} for x in ("ann", "bob", "cy")])
    self.download("feed", [{"url": profile("zed")}])
    p = self.li("queue", "--max", "2", "--from-download", "--wait", "0", check=0)
    lines = p.stdout.splitlines()
    self.assertEqual(lines[0], "# 3 viewer(s) on the page, 3 to try (0 deferred from before)")
    self.assertEqual(lines[1:], [f"{profile('ann')}\tAnn Person", f"{profile('bob')}\tBob Person",
                                 "# over the cap: pass the lines below to `defer`", f"{profile('cy')}\tCy Person"])
    self.assertIn("3 row(s) from pa-linkedin-viewers-20261113T080000Z.json", p.stderr)
    # Consumed: moved to the state folder, never read twice; the older one and the feed stay
    self.assertFalse(os.path.exists(new))
    self.assertTrue(os.path.exists(os.path.join(self.state, "downloads", os.path.basename(new))))
    self.assertTrue(os.path.exists(old))
    self.assertTrue(os.path.exists(os.path.join(self.dl, "pa-linkedin-feed-20261113T080000Z.json")))

  def test_download_checks(self):
    # Nothing there: a clear message pointing at the get_page_text fallback
    p = self.li("suggestions", "--from-download", "--wait", "0", check=1)
    self.assertIn("no pa-linkedin-suggestions-*.json", p.stderr)
    self.assertIn("get_page_text", p.stderr)
    # A count that doesn't match is refused and left where it is
    bad = self.download("suggestions", [{"url": profile("a"), "name": "A A", "mutual": 3}], count=2)
    p = self.li("suggestions", "--from-download", "--wait", "0", check=1)
    self.assertIn("says 2 but has 1 rows", p.stderr)
    self.assertTrue(os.path.exists(bad))
    os.remove(bad)
    # From an earlier run: refused
    self.download("suggestions", [], age=5 * 3600)
    self.assertIn("hours old", self.li("suggestions", "--from-download", "--wait", "0", check=1).stderr)
    # The wrong kind for the command
    self.li("queue", "--from-download", "feed", "--wait", "0", check=2)
    # Chrome's " (1)" for a name taken is fine; stdin still works without --from-download
    for f in os.listdir(self.dl):
      os.remove(os.path.join(self.dl, f))
    self.download("followers", [{"url": profile("fi"), "name": "Fi Fo"}], name="pa-linkedin-followers-20261113T080000Z (1).json")
    out = self.li("follows", "--from-download", "--wait", "0", check=0).stdout
    self.assertIn(f"{profile('fi')}\tFi Fo", out)
    page = "FOLLOWERS-BEGIN\n" + json.dumps({"url": profile("gu"), "name": "Gu Ha"}) + "\nFOLLOWERS-END 1\n"
    self.assertIn(f"{profile('gu')}\tGu Ha", self.li("follows", stdin=page, check=0).stdout)

  def test_connections_and_feed_from_download(self):
    rows = [{"url": profile("dee-ell"), "name": "Dee Ell", "headline": "CTO at Ácme", "connected": "November 10, 2026"}]
    self.download("connections", rows)
    out = os.path.join(self.tmp, "c.json")
    self.assertIn(f"1 connection(s) -> {out}", self.li("connections", out, "--from-download", "--wait", "0",
                                                         check=0).stdout)
    with open(out, encoding="utf-8") as f:
      self.assertEqual([json.loads(l) for l in f], rows)
    post = dict(url=profile("eve-ng"), postUrl="", name="Eve Ng", openToWork=False, degree="1st", context="",
                age="2h", reactions=0, comments=0, reposts=0, text="I'm starting a new position at Initech")
    self.download("feed", [post])
    out = self.li("feed", "--from-download", "--wait", "0", check=0).stdout.splitlines()
    self.assertEqual(out[0], "# 1 post(s) read, 1 scoring 3.5 or more, showing 1")

  def test_unreadable_downloads_folder(self):
    if os.geteuid() == 0:
      self.skipTest("root reads anything")
    os.chmod(self.dl, 0)
    try:
      p = self.li("export", check=1)
    finally:
      os.chmod(self.dl, stat.S_IRWXU)
    self.assertIn("can't read", p.stderr)
    self.assertNotIn("Traceback", p.stderr)

  # --- STOP, BUDGET and RERUN from `log`, and defer --rest

  def test_log_stop_and_defer_rest(self):
    self.download("viewers", [{"url": profile(x), "name": f"{x.title()} Person"} for x in ("ann", "bob", "cy", "di")])
    self.li("queue", "--from-download", "--wait", "0", check=0)
    self.assertNotIn("STOP", self.li("log", "sent", profile("ann"), "Ann Person", check=0).stdout)
    self.assertNotIn("STOP", self.li("log", "needs-email", profile("bob"), "Bob Person", check=0).stdout)
    out = self.li("log", "limit", profile("cy"), "Cy Person", check=0).stdout.splitlines()
    self.assertTrue(out[1].startswith("STOP limit"), out)
    self.assertEqual(out[2:], ["# not yet tried (1): `defer --rest` logs them as deferred for the next run",
                               f"{profile('di')}\tDi Person"])
    self.assertEqual(self.li("defer", "--rest", check=0).stdout, "deferred 1\n")
    self.assertIn(f"\tdeferred\t{profile('di')}\tDi Person\n", self.log_text())
    # The queue is gone once deferred: a second --rest does nothing
    self.assertEqual(self.li("defer", "--rest", check=0).stdout, "deferred 0\n")

  def test_three_not_profile_in_a_row_stop(self):
    self.download("viewers", [{"url": profile(x), "name": x.title()} for x in ("aa", "bb", "cc", "dd", "ee")])
    self.li("queue", "--from-download", "--wait", "0", check=0)
    self.li("log", "not-profile", profile("aa"), "Aa", check=0)
    self.li("log", "no-connect", profile("bb"), "Bb", check=0)
    self.assertNotIn("STOP", self.li("log", "not-profile", profile("cc"), "Cc", check=0).stdout)
    self.assertNotIn("STOP", self.li("log", "not-profile", profile("dd"), "Dd", check=0).stdout)
    out = self.li("log", "not-profile", profile("ee"), "Ee", check=0).stdout
    self.assertIn("STOP not-profile: three profiles in a row", out)
    self.assertIn("# nobody left in the queue to defer", out)
    self.assertIn("STOP error", self.li("log", "error", profile("ff"), "Ff", check=0).stdout)

  def test_budget_signal(self):
    self.download("viewers", [{"url": profile(x), "name": x.title()} for x in ("aa", "bb", "cc")])
    self.li("queue", "--max", "1", "--from-download", "--wait", "0", check=0)
    out = self.li("log", "sent", profile("aa"), "Aa", check=0).stdout
    self.assertIn("BUDGET: 1 sent since the queue was made, its --max 1", out)
    self.assertIn("# not yet tried (2)", out)

  def test_correspondents_stop_defers_the_rest(self):
    stdin = "Ann One <ann@a.example>\nBen Two <ben@b.example>\nCat Three <cat@c.example>\n"
    self.li("correspondents", stdin=stdin, check=0)
    self.li("log", "--email", "ann@a.example", "no-match", "", "Ann One", check=0)
    out = self.li("log", "--email", "ben@b.example", "unexpected", profile("ben-two"), "Ben Two", check=0).stdout
    self.assertIn("STOP unexpected", out)
    self.assertIn("`defer --email --rest`", out)
    self.assertIn("cat@c.example\tCat Three", out)
    self.assertEqual(self.li("defer", "--email", "--rest", check=0).stdout, "deferred 1\n")
    self.assertIn("\tdeferred\tcat@c.example\tCat Three\t", self.log_text("linkedin-correspondents.log"))

  def test_follows_rerun_and_stop(self):
    for x in ("aa", "bb"):
      self.assertNotIn("RERUN", self.li("log", "--follows", "missing", profile(x), x, check=0).stdout)
    out = self.li("log", "--follows", "missing", profile("cc"), "Cc", check=0).stdout
    self.assertIn("RERUN: three missing in a row", out)
    self.assertNotIn("RERUN", self.li("log", "--follows", "followed", profile("dd"), "Dd", check=0).stdout)
    self.assertIn("STOP limit", self.li("log", "--follows", "limit", profile("ee"), "Ee", check=0).stdout)

  # --- correspondents: the Gmail connector's JSON, and gog failures

  def test_threads_json(self):
    threads = {"threads": [
      {"id": "t1", "messages": [
        {"id": "m1", "from": "Jo Park <jo@parkco.example>", "to": [{"email": PERSONAL, "name": "Ian"}]},
        {"id": "m2", "from": f"Ian Miell <{WORK}>", "to": [{"email": "jo@parkco.example", "name": "Jo Park"}],
         "cc": "Lu Wei <lu.wei@parkco.example>, info@parkco.example"},
      ]},
      # A Gmail API style message labelled SENT, inside a tool result's text
      {"content": [{"type": "text", "text": json.dumps({"messages": [
        msg("m3", WORK, "Max Ray <max.ray@raysoft.example>", "Re: plan", ["SENT"])]})}]},
      # The same message again (search and get_thread both saved): counted once
      {"id": "m2", "from": WORK, "to": "Jo Park <jo@parkco.example>"},
    ]}
    path = os.path.join(self.tmp, "sent.json")
    with open(path, "w") as f:
      json.dump(threads, f)
    out = self.li("correspondents", "--threads-json", path, check=0).stdout
    rows = [l.split("\t")[:4] for l in out.splitlines() if not l.startswith("#")]
    self.assertEqual(rows, [["jo@parkco.example", "Jo Park", "parkco", "work"],
                            ["lu.wei@parkco.example", "Lu Wei", "parkco", "work"],
                            ["max.ray@raysoft.example", "Max Ray", "raysoft", "work"]])
    # Nobody from Ian in it: says so rather than listing nothing quietly
    with open(path, "w") as f:
      json.dump({"messages": [{"id": "x", "from": "a@b.example", "to": PERSONAL}]}, f)
    self.assertIn("no messages from Ian", self.li("correspondents", "--threads-json", path, check=0).stderr)

  def test_correspondents_gog_failure(self):
    fake = os.path.join(self.tmp, "failing-gog")
    with open(fake, "w") as f:
      f.write("#!/bin/sh\necho 'oauth2: token expired and refresh token is not set' >&2\nexit 1\n")
    os.chmod(fake, 0o755)
    self.env["PA_GOG"] = fake
    p = self.li("correspondents", "--gog", "personal", check=1)
    self.assertIn("gog couldn't read the personal mailbox's sent mail (oauth2: token expired", p.stderr)
    self.assertIn("rerun without `--gog personal`", p.stderr)
    self.assertNotIn("Traceback", p.stderr)
    self.env["PA_GOG"] = os.path.join(self.tmp, "no-such-gog")
    p = self.li("correspondents", "--gog", "work", check=1)
    self.assertIn("gog couldn't read the work mailbox", p.stderr)
    self.assertNotIn("Traceback", p.stderr)
    # Output that isn't JSON
    with open(fake, "w") as f:
      f.write("#!/bin/sh\necho 'not json'\n")
    self.env["PA_GOG"] = fake
    p = self.li("correspondents", "--gog", "personal", check=1)
    self.assertRegex(p.stderr, r"gog couldn't read the personal mailbox's sent mail \((output not understood|.*isn't JSON)")
    self.assertNotIn("Traceback", p.stderr)

  def test_correspondents_from_fake_gog_still_works(self):
    self.set_mail({PERSONAL: {"t1": {"messages": [msg("m1", PERSONAL, "Ola Berg <ola@berg.example>", "Hi", ["SENT"])]}},
                   WORK: {}})
    out = self.li("correspondents", "--gog", "personal", check=0).stdout
    self.assertIn("ola@berg.example\tOla Berg\tberg\tpersonal", out)

  # --- step 7: evidence from the calendar, and the mail queries

  def test_evidence_with_events_and_attendees(self):
    events = {"events": [
      {"summary": "Acme intro", "start": {"dateTime": "2026-10-20T10:00:00+01:00"},
       "attendees": [{"email": WORK, "self": True}, {"email": "dana.lee@acme.example"}]},
      {"summary": "Pairing", "start": {"date": "2026-10-22"},
       "attendees": [{"email": "x@y.example", "displayName": "Eli Moss", "responseStatus": "declined"}]},
      {"summary": "Old", "start": {"dateTime": "2026-10-01T09:00:00Z"},
       "attendees": [{"email": "dlee@acme.example"}]},
    ]}
    path = os.path.join(self.tmp, "cal-work.json")
    with open(path, "w") as f:
      json.dump(events, f)
    att = os.path.join(self.tmp, "attendees.txt")
    with open(att, "w") as f:
      f.write('Fay Ng: 2 event(s), last Fri 30 Oct 2026 "Roadmap" (P), via fay@ng.example\nGus Hale: none\n')
    imp = ("  Created Dana_Lee.md | Dana Lee | CTO at Acme | connected 01 Nov 2026 | https://x\n"
           "  Created Eli_Moss.md | Eli Moss | Eng | connected 01 Nov 2026 | https://y\n"
           "  Created Fay_Ng.md | Fay Ng | PM | connected 01 Nov 2026 | https://z\n"
           "  Created Gus_Hale.md | Gus Hale | PM | connected 01 Nov 2026 | https://w\n")
    out = self.li("evidence", "--events", path, "--attendees", att, stdin=imp, check=0).stdout.splitlines()
    self.assertEqual(out, ["Dana Lee\tmet\tcalendar: Acme intro 2026-10-20; calendar: Old 2026-10-01",
                           "Eli Moss\tforgotten?\t-",   # declined: not met
                           "Fay Ng\tmet\tcalendar: 2 event(s), last Fri 30 Oct 2026 \"Roadmap\" (P)",
                           "Gus Hale\tforgotten?\t-"])
    # calendar-events.py attendees --json works too
    with open(att, "w") as f:
      json.dump([{"name": "Fay Ng", "count": 1, "emails": [], "last": {"date": "2026-10-30", "title": "Roadmap",
                                                                        "cal": "P"}, "next": None}], f)
    out = self.li("evidence", "--attendees", att, stdin="Fay Ng\n", check=0).stdout
    self.assertEqual(out, 'Fay Ng\tmet\tcalendar: 1 event(s), last 2026-10-30 "Roadmap"\n')

  def test_mail_query(self):
    names = "\n".join(f"Person{chr(65 + i)} Test" for i in range(12)) + '\nPersonA Test\nQuo "Te" Mark\n'
    out = self.li("mail-query", stdin=names, check=0).stdout.splitlines()
    self.assertEqual(len(out), 2)
    self.assertTrue(out[0].startswith('newer_than:30d ("PersonA Test" OR "PersonB Test" OR '))
    self.assertEqual(out[0].count(" OR "), 9)
    self.assertEqual(out[1], 'newer_than:30d ("PersonK Test" OR "PersonL Test" OR "Quo Te Mark")')
    imp = "  Created Dana_Lee.md | Dana Lee | CTO | connected 01 Nov 2026 | https://x\n  Pending Fay Ng | PM | x | y\n"
    self.assertEqual(self.li("mail-query", "--days", "7", "--size", "1", stdin=imp, check=0).stdout,
                     'newer_than:7d ("Dana Lee")\nnewer_than:7d ("Fay Ng")\n')

  # --- step 6: the data export

  def test_export_lookup_and_import(self):
    self.assertEqual(self.li("export", check=0).stdout, "EXPORT none\nACTION request\n")
    os.makedirs(os.path.join(self.dl, "Basic_LinkedInDataExport_folder.zip"))  # a folder, not a zip
    zip_path = os.path.join(self.dl, "complete_linkedindataexport_11-13-2026.ZIP")
    open(zip_path, "w").close()
    open(os.path.join(self.dl, "LinkedInDataExport notes.txt"), "w").close()
    out = self.li("export", "--import", check=0).stdout.splitlines()
    self.assertEqual(out[:2], [f"EXPORT {zip_path} 0d", "ACTION import"])
    with open(os.path.join(self.gtd, "calls.log")) as f:
      self.assertIn(f"import-connections --auto {zip_path}", f.read())
    # Without --import, or when it isn't fresh, nothing is run
    os.remove(os.path.join(self.gtd, "calls.log"))
    self.li("export", check=0)
    t = time.time() - 10 * 86400
    os.utime(zip_path, (t, t))
    self.assertEqual(self.li("export", "--import", check=0).stdout, f"EXPORT {zip_path} 10d\nACTION none\n")
    self.assertFalse(os.path.exists(os.path.join(self.gtd, "calls.log")))


if __name__ == "__main__":
  unittest.main()
