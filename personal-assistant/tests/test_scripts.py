#!/usr/bin/env python3
"""Tests for the personal-assistant scripts, against made-up fixtures and a fake gog.

  python3 -m unittest discover -s personal-assistant/tests -v

Nothing here touches Ian's mail, gtd repo or state files: GTD_DIR, PA_STATE, PA_GOG,
MEETINGS_INBOX and PA_LINKEDIN_STATE all point into a temporary folder. The names are made
up (the repo is public).
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
LINKEDIN = os.path.join(HERE, "..", "skills", "linkedin-sync", "linkedin-state.py")
WORK, PERSONAL = "ian.miell@container-solutions.com", "ian.miell@gmail.com"

FAKE_GTD = r"""#!/bin/bash
root="$(cd "$(dirname "$0")/.." && pwd)"
echo "$* GO_TO_TASK=${GO_TO_TASK:-} CTX=${GTD_DISPLAY_CONTEXT:-}" >> "$root/calls.log"
case "$1" in
  nt) n=$(( $(cat "$root/.metadata/lasttask") + 1 )); echo $n > "$root/.metadata/lasttask"
      mkdir -p "$root/tasks/$n"; printf '# %s\nTask Number: %s\n\n' "$2" "$n" > "$root/tasks/$n/notes.md"
      ln -s "../../tasks/$n" "$root/status/todo/$n" ;;
  defer) mv "$root"/status/*/"$2" "$root/status/waiting/"; date +%s > "$root/tasks/$2/.remindme" ;;
  ms) mv "$root"/status/*/"$3" "$root/status/$2/" ;;
  fail) exit 1 ;;
esac
echo "Processing 1/1 done"
"""


def b64(text):
  return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def msg(mid, frm, to, subject, labels, body="Hello", cc=None, date=1792500000000, extra=None, snippet=None,
        mime="text/plain"):
  headers = [{"name": "From", "value": frm}, {"name": "To", "value": to}, {"name": "Subject", "value": subject},
             {"name": "Message-ID", "value": f"<{mid}@example.com>"}, {"name": "Date", "value": "Tue, 20 Oct 2026"}]
  if cc:
    headers.append({"name": "Cc", "value": cc})
  for k, v in (extra or {}).items():
    headers.append({"name": k, "value": v})
  return {"id": mid, "labelIds": list(labels), "internalDate": str(date), "snippet": snippet or body[:80],
          "payload": {"mimeType": "multipart/alternative", "headers": headers, "body": {},
                      "parts": [{"mimeType": mime, "body": {"data": b64(body)}}]}}


SYSTEM = [{"id": x, "name": x, "type": "system"} for x in ("INBOX", "STARRED", "UNREAD", "SENT", "SPAM", "TRASH")]


class Base(unittest.TestCase):
  def setUp(self):
    self.tmp = tempfile.mkdtemp(prefix="pa-test-")
    self.gtd = os.path.join(self.tmp, "gtd")
    for d in ("status/todo", "status/waiting", "status/closed", "status/someday", "tasks", "people",
              "meetings", ".metadata", "bin"):
      os.makedirs(os.path.join(self.gtd, d))
    with open(os.path.join(self.gtd, ".metadata", "lasttask"), "w") as f:
      f.write("100\n")
    with open(os.path.join(self.gtd, "bin", "gtd"), "w") as f:
      f.write(FAKE_GTD)
    os.chmod(os.path.join(self.gtd, "bin", "gtd"), 0o755)
    self.state_file = os.path.join(self.tmp, "gog.json")
    self.log_file = os.path.join(self.tmp, "gog.log")
    self.set_mail({WORK: {}, PERSONAL: {}})
    self.env = dict(os.environ, GTD_DIR=self.gtd, PA_STATE=os.path.join(self.tmp, "state"),
                    PA_GOG=os.path.join(HERE, "fake_gog.py"), FAKE_GOG_STATE=self.state_file,
                    FAKE_GOG_LOG=self.log_file, MEETINGS_INBOX=os.path.join(self.tmp, "inbox"),
                    PA_LINKEDIN_STATE=os.path.join(self.tmp, "li"))

  def tearDown(self):
    shutil.rmtree(self.tmp)

  def set_mail(self, accounts, labels=None):
    state = {"accounts": {}}
    for addr, threads in accounts.items():
      state["accounts"][addr] = {"labels": SYSTEM + list((labels or {}).get(addr, [])), "threads": threads}
    with open(self.state_file, "w") as f:
      json.dump(state, f)

  def mail(self):
    with open(self.state_file) as f:
      return json.load(f)["accounts"]

  def labels_of(self, addr, tid):
    s = set()
    for m in self.mail()[addr]["threads"][tid]["messages"]:
      s.update(m["labelIds"])
    return s

  def gog_calls(self):
    try:
      with open(self.log_file) as f:
        return [json.loads(l) for l in f]
    except OSError:
      return []

  def task(self, n, status, text):
    os.makedirs(os.path.join(self.gtd, "tasks", str(n)))
    with open(os.path.join(self.gtd, "tasks", str(n), "notes.md"), "w") as f:
      f.write(text)
    os.symlink(f"../../tasks/{n}", os.path.join(self.gtd, "status", status, str(n)))

  def run_script(self, name, *args, stdin="", script=None, check=None):
    path = script or os.path.join(SCRIPTS, name)
    p = subprocess.run([sys.executable, path, *args], input=stdin, capture_output=True, text=True,
                       env=self.env, timeout=60)
    if check is not None:
      self.assertEqual(p.returncode, check, p.stdout + p.stderr)
    return p


class GtdFind(Base):
  def setUp(self):
    super().setUp()
    self.task(1, "todo", "# CS: Reply to Jane Doe about the renewal\nTask Number: 1\n"
              "https://mail.google.com/mail/?authuser=ian.miell%40gmail.com#all/1a2b3c4d5e6f7a8b\nShe wants it by Friday.\n")
    self.task(2, "waiting", "# HOME: Book the plumber\nTask Number: 2\nhttps://mail.google.com/mail/u/0/#inbox/FMfcgzQhWxRsfbq\n")
    self.task(3, "closed", "# CS: Old Jane Doe task\nTask Number: 3\n")
    self.task(4, "todo", "# CS: Samson review\nTask Number: 4\n")

  def test_names_ids_and_closed_left_out(self):
    out = self.run_script("gtd-find.py", "Jane Doe", check=0).stdout
    self.assertIn("1 [todo] CS: Reply to Jane Doe", out)
    self.assertNotIn("Old Jane Doe", out)
    out = self.run_script("gtd-find.py", "1a2b3c4d5e6f7a8b", check=0).stdout
    self.assertIn("1 [todo]", out)
    out = self.run_script("gtd-find.py", "FMfcgzQhWxRsfbq", check=0).stdout
    self.assertIn("2 [waiting]", out)

  def test_words_skip_links_and_need_whole_words(self):
    self.assertIn("(no open task)", self.run_script("gtd-find.py", "google", check=0).stdout)
    out = self.run_script("gtd-find.py", "Sam", check=0).stdout
    self.assertIn("(no open task)", out)

  def test_batch_and_ranking(self):
    out = self.run_script("gtd-find.py", "--batch", "--json", check=0,
                          stdin="1: renewal | Jane Doe | plumber\n2: nothing-here-at-all\n").stdout
    res = json.loads(out)
    self.assertEqual(res[0]["item"], "1")
    self.assertEqual([h["task"] for h in res[0]["hits"]], [1, 2])
    self.assertEqual(res[0]["hits"][0]["matched"], ["renewal", "Jane Doe"])
    self.assertEqual(res[1]["hits"], [])

  def test_status_option(self):
    out = self.run_script("gtd-find.py", "--status", "closed", "Jane Doe", check=0).stdout
    self.assertIn("3 [closed]", out)


PERSON = """## Jane Doe
- Email: jane@acme.example
- Company: Acme
- Level: met

Met at a conference.

### Email log
- 2026-10-01 (email, work): First contact.

### Meeting log
- 2026-10-02 (meeting): Intro call. [meetings/x.txt]

## LinkedIn messages

- 2025-01-01T00:00:00+00:00 (Received)
  - Content: hi
"""

MANAGED = """#
- Level: met

## managed by linkedin_tools
## Bob Smith
### Messages
- 2020-01-01T00:00:00+00:00 (Sent)
  - Content: hello
### managed by linkedin_tools
"""


class PeopleNote(Base):
  def setUp(self):
    super().setUp()
    files = {"Jane_Doe.md": PERSON, "Jane_Doe_2.md": "## Jane Doe\n- Company: Other\n",
             "Bob_Smith.md": MANAGED, "Onsel_Yilmaz.md": "## Önsel Yilmaz\n",
             "Chris_P.md": "## Chris P\n", "Plain_Person.md": "## Plain Person\n- Company: X\n",
             "Louise_Cox.md": "## Louise Cox\n- Email: louise@corp.example\n"}
    for name, text in files.items():
      with open(os.path.join(self.gtd, "people", name), "w") as f:
        f.write(text)

  def read(self, name):
    with open(os.path.join(self.gtd, "people", name)) as f:
      return f.read()

  def test_find(self):
    out = self.run_script("people-note.py", "find", "Jane Doe", check=0).stdout
    self.assertIn("Jane_Doe.md\tname\t", out)
    self.assertIn("Jane_Doe_2.md\tname (numbered duplicate)", out)
    out = self.run_script("people-note.py", "find", "Louise Corrigan", "--email", "LOUISE@corp.example", check=0).stdout
    self.assertIn("Louise_Cox.md\tcontains", out)
    self.assertIn("Onsel_Yilmaz.md", self.run_script("people-note.py", "find", "Önsel Yilmaz", check=0).stdout)
    self.assertIn("first name + surname initial",
                  self.run_script("people-note.py", "find", "Chris Peterson", check=0).stdout)
    self.run_script("people-note.py", "find", "No Body", check=1)

  def test_log_goes_at_end_of_its_section(self):
    self.run_script("people-note.py", "log", "Jane_Doe", "--kind", "email, work", "--task", "7",
                    "--date", "2026-10-20", "Sent  the\nproposal.", check=0)
    text = self.read("Jane_Doe.md")
    self.assertIn("- 2026-10-01 (email, work): First contact.\n"
                  "- 2026-10-20 (email, work): Sent the proposal. [task 7]\n\n### Meeting log", text)
    self.run_script("people-note.py", "log", "Jane_Doe.md", "--kind", "meeting", "--ref", "meetings/y.txt",
                    "--date", "2026-10-21", "Second call.", check=0)
    self.assertIn("[meetings/x.txt]\n- 2026-10-21 (meeting): Second call. [meetings/y.txt]\n\n## LinkedIn messages",
                  self.read("Jane_Doe.md"))
    self.assertTrue(self.read("Jane_Doe.md").endswith("  - Content: hi\n"))

  def test_log_is_idempotent(self):
    args = ("people-note.py", "log", "Jane_Doe", "--kind", "slack", "--date", "2026-10-20", "Pinged.")
    self.run_script(*args, check=0)
    out = self.run_script(*args, check=0).stdout
    self.assertIn("already has that line", out)
    self.assertEqual(self.read("Jane_Doe.md").count("Pinged."), 1)

  def test_new_section_skips_managed_block(self):
    self.run_script("people-note.py", "log", "Bob_Smith", "--kind", "whatsapp", "--date", "2026-10-20", "Intro.",
                    check=0)
    text = self.read("Bob_Smith.md")
    self.assertTrue(text.endswith("### managed by linkedin_tools\n\n### Email log\n- 2026-10-20 (whatsapp): Intro.\n"))

  def test_new_section_before_linkedin_messages(self):
    with open(os.path.join(self.gtd, "people", "Plain_Person.md"), "a") as f:
      f.write("\n## LinkedIn messages\n\n- 2025-01-01T00:00:00+00:00 (Sent)\n  - Content: yo\n")
    self.run_script("people-note.py", "log", "Plain_Person", "--kind", "linkedin", "--date", "2026-10-20", "Hi.",
                    check=0)
    self.assertEqual(self.read("Plain_Person.md"),
                     "## Plain Person\n- Company: X\n\n### Email log\n- 2026-10-20 (linkedin): Hi.\n\n"
                     "## LinkedIn messages\n\n- 2025-01-01T00:00:00+00:00 (Sent)\n  - Content: yo\n")

  def test_dry_run_and_missing_file(self):
    before = self.read("Plain_Person.md")
    out = self.run_script("people-note.py", "log", "Plain_Person", "--kind", "slack", "--dry-run", "x", check=0).stdout
    self.assertIn("would add", out)
    self.assertEqual(self.read("Plain_Person.md"), before)
    self.run_script("people-note.py", "log", "Nobody_Here", "--kind", "slack", "x", check=1)

  def test_check_finds_misplaced_lines(self):
    with open(os.path.join(self.gtd, "people", "Jane_Doe.md"), "a") as f:
      f.write("- 2026-10-16 (email, work): stray line\n")
    out = self.run_script("people-note.py", "check", check=0).stdout
    self.assertIn("Jane_Doe.md: 1 line(s)", out)
    self.assertIn("1 file(s)", out)


class LabelTidy(Base):
  def setUp(self):
    super().setUp()
    self.task(10, "todo", "# CS: open\nTask Number: 10\n")
    self.task(11, "closed", "# CS: closed one\nTask Number: 11\n"
              "https://mail.google.com/mail/?authuser=ian.miell%40gmail.com#all/cccccccccccccccc\n"
              "https://mail.google.com/mail/?authuser=ian.miell@container-solutions.com#all/dddddddddddddddd\n")
    p = lambda mid, labels: {"messages": [msg(mid, "a@x.example", PERSONAL, "s", labels)]}
    self.set_mail({PERSONAL: {"aaaaaaaaaaaaaaaa": p("m1", ["INBOX", "STARRED", "L10"]),
                              "bbbbbbbbbbbbbbbb": p("m2", ["INBOX", "STARRED", "L11"]),
                              "cccccccccccccccc": p("m3", ["INBOX", "STARRED"]),
                              "eeeeeeeeeeeeeeee": p("m4", ["INBOX", "L99"])},
                   WORK: {}},
                  labels={PERSONAL: [{"id": "L10", "name": "GTD-10"}, {"id": "L11", "name": "GTD-11"},
                                     {"id": "L99", "name": "GTD-99"}]})

  def test_dry_run_changes_nothing(self):
    before = self.mail()
    out = self.run_script("gtd-label-tidy.py", "--mailbox", "personal", "--dry-run", check=0).stdout
    self.assertIn("personal: task 11 closed: would archive 2 thread(s), would remove GTD-11", out)
    self.assertEqual(self.mail(), before)

  def test_closed_task_tidied(self):
    out = self.run_script("gtd-label-tidy.py", "--mailbox", "personal", check=0).stdout
    self.assertIn("personal: task 11 closed: archived 2 thread(s), removed GTD-11", out)
    self.assertIn("GTD-99 has no task 99 in gtd; left alone", out)
    self.assertIn("GTD labels: personal 3 label(s), 1 open", out)
    self.assertEqual(self.labels_of(PERSONAL, "bbbbbbbbbbbbbbbb"), set())
    self.assertEqual(self.labels_of(PERSONAL, "cccccccccccccccc"), set())  # linked in notes, no label
    self.assertEqual(self.labels_of(PERSONAL, "aaaaaaaaaaaaaaaa"), {"INBOX", "STARRED", "L10"})
    names = [l["name"] for l in self.mail()[PERSONAL]["labels"]]
    self.assertNotIn("GTD-11", names)
    self.assertIn("GTD-10", names)

  def test_one_task_and_unreachable_mailbox(self):
    out = self.run_script("gtd-label-tidy.py", "--mailbox", "personal", "--task", "10", check=0).stdout
    self.assertIn("task 10 is todo, not closed", out)
    self.env["PA_GOG"] = "/nonexistent/gog"
    p = self.run_script("gtd-label-tidy.py", "--mailbox", "personal")
    self.assertNotEqual(p.returncode, 0)


class MailGather(Base):
  def setUp(self):
    super().setUp()
    self.set_mail({
      PERSONAL: {
        "0000000000000001": {"messages": [msg("p1", "The Week <info@newsletter.theweek.co.uk>", PERSONAL,
                                              "Evening Review", ["INBOX", "UNREAD"], date=1792500001000)]},
        "0000000000000002": {"messages": [msg("p2", "OWID <newsletter@ourworldindata.org>", PERSONAL, "Data Insight",
                                              ["INBOX"], date=1792500002000)]},
        "0000000000000003": {"messages": [
          msg("p3", "Sam Friend <sam@friends.example>", PERSONAL, "Dinner?", ["INBOX"],
              body="Fancy dinner on the 24th?\n\nOn Mon, 19 Oct 2026 Ian wrote:\n> earlier text", date=1792500003000),
          msg("p4", f"Ian Miell <{PERSONAL}>", "sam@friends.example", "Re: Dinner?", ["SENT"], date=1792500004000)]},
        "0000000000000004": {"messages": [msg("shared", "Pat <pat@acme.example>", f"{PERSONAL}, {WORK}",
                                              "Both of you", ["INBOX"], date=1792500005000)]},
        "0000000000000005": {"messages": [msg("p6", "Shop <news@shop.example>", PERSONAL, "Sale!", ["INBOX"],
                                              extra={"List-Unsubscribe": "<https://shop.example/u>"},
                                              date=1792500006000)]},
      },
      WORK: {
        "1000000000000001": {"messages": [msg("w1", "Bob <bob@client.example>", WORK,
                                              "Invitation: Q4 planning @ Tue", ["INBOX", "UNREAD"], date=1792500007000)]},
        "1000000000000002": {"messages": [msg("w2", "Jane <jane@client.example>", "boss@cs.example", "Contract",
                                              ["INBOX", "STARRED", "L7"], cc=WORK, date=1792500008000)]},
        "1000000000000003": {"messages": [msg("shared", "Pat <pat@acme.example>", f"{PERSONAL}, {WORK}",
                                              "Both of you", ["INBOX"], date=1792500005000)]},
        "1000000000000004": {"messages": [msg("w4", "GitHub <notifications@github.com>", WORK, "PR merged",
                                              ["INBOX"], date=1792500009000)]},
        "1000000000000005": {"messages": [msg("w5", "Alerts <no-reply@tool.example>", WORK, "Weekly digest",
                                              ["INBOX"], date=1792500000500)]},
        "1000000000000006": {"messages": [msg("w6", "Out <x@y.example>", WORK, "Archived", ["STARRED"])]},
      }}, labels={WORK: [{"id": "L7", "name": "GTD-7"}]})

  def test_list_hints_numbering_and_dedupe(self):
    out = json.loads(self.run_script("mail-gather.py", "list", "--json", check=0).stdout)
    self.assertEqual([b["mailbox"] for b in out], ["work", "personal"])
    hints = {t["thread"]: (t["n"], t["hint"]) for b in out for t in b["threads"]}
    self.assertEqual(len(hints), 10)  # the archived thread isn't in:inbox
    self.assertEqual(hints["1000000000000004"], (1, "fyi"))
    self.assertEqual(hints["1000000000000002"][1], "task 7")
    self.assertEqual(hints["1000000000000001"][1], "invite")
    self.assertEqual(hints["1000000000000005"][1], "automated?")
    self.assertEqual(hints["0000000000000001"][1], "trash")
    self.assertEqual(hints["0000000000000002"][1], "read-later")
    self.assertEqual(hints["0000000000000003"][1], "you replied last")
    self.assertEqual(hints["0000000000000005"][1], "newsletter?")
    self.assertEqual(hints["0000000000000004"][1], "person")
    self.assertEqual(sorted(n for n, _ in hints.values()), list(range(1, 11)))
    by = {t["thread"]: t for b in out for t in b["threads"]}
    self.assertEqual(by["0000000000000004"]["also_in"], "work")
    self.assertEqual(by["1000000000000003"]["also_in"], "personal")
    self.assertEqual(by["1000000000000002"]["ian_in"], "cc")
    self.assertEqual(by["0000000000000005"]["unsubscribe"], "https://shop.example/u")
    self.assertEqual(by["0000000000000003"]["last_message"], "p4")

  def test_list_text_and_query(self):
    out = self.run_script("mail-gather.py", "list", "--mailbox", "personal", "--max", "2", check=0).stdout
    self.assertIn("━━ PERSONAL (ian.miell@gmail.com) — 2 threads for `in:inbox` (first 2; there are more)", out)
    self.assertNotIn("WORK", out)
    self.assertIn("thread ", out)

  def test_read_strips_quotes(self):
    out = self.run_script("mail-gather.py", "read", "personal", "0000000000000003", check=0).stdout
    self.assertIn("Fancy dinner on the 24th?", out)
    self.assertNotIn("earlier text", out)
    self.assertIn("msg p4", out)
    self.assertIn("--full", self.gog_calls()[-1])

  def test_unreachable_mailbox_is_reported(self):
    state = json.load(open(self.state_file))
    del state["accounts"][WORK]
    json.dump(state, open(self.state_file, "w"))
    out = self.run_script("mail-gather.py", "list", check=0).stdout
    self.assertIn("WORK — UNREACHABLE", out)
    self.assertIn("PERSONAL", out)


class MailApply(Base):
  def setUp(self):
    super().setUp()
    p = lambda mid, labels: {"messages": [msg(mid, "a@x.example", PERSONAL, "s", labels)]}
    self.set_mail({PERSONAL: {"aaaaaaaaaaaaaaaa": p("m1", ["INBOX", "STARRED", "UNREAD"]),
                              "bbbbbbbbbbbbbbbb": p("m2", ["INBOX"]),
                              "cccccccccccccccc": p("m3", ["INBOX", "STARRED"]),
                              "dddddddddddddddd": p("m4", ["INBOX"]),
                              "eeeeeeeeeeeeeeee": p("m5", ["INBOX"]),
                              "ffffffffffffffff": p("m6", ["INBOX"]),
                              "1111111111111111": p("m7", ["STARRED"])},
                   WORK: {}}, labels={PERSONAL: [{"id": "L1", "name": "Receipts"}]})

  def test_actions_and_star_rules(self):
    plan = """
personal archive aaaaaaaaaaaaaaaa
personal keep bbbbbbbbbbbbbbbb
personal trash cccccccccccccccc
personal spam dddddddddddddddd
personal label Receipts eeeeeeeeeeeeeeee
personal gtd 42 ffffffffffffffff
personal gtd 43 1111111111111111
"""
    out = self.run_script("mail-apply.py", stdin=plan, check=0).stdout
    L = lambda t: self.labels_of(PERSONAL, t)
    self.assertEqual(L("aaaaaaaaaaaaaaaa"), {"UNREAD"})
    self.assertEqual(L("bbbbbbbbbbbbbbbb"), {"INBOX", "STARRED"})
    self.assertEqual(L("cccccccccccccccc"), {"TRASH"})
    self.assertEqual(L("dddddddddddddddd"), {"SPAM"})
    self.assertEqual(L("eeeeeeeeeeeeeeee"), {"L1"})
    gtd42 = next(l["id"] for l in self.mail()[PERSONAL]["labels"] if l["name"] == "GTD-42")
    self.assertEqual(L("ffffffffffffffff"), {"INBOX", "STARRED", gtd42})  # still in inbox: starred
    gtd43 = next(l["id"] for l in self.mail()[PERSONAL]["labels"] if l["name"] == "GTD-43")
    self.assertEqual(L("1111111111111111"), {"STARRED", gtd43})  # not in inbox: star left as it was
    self.assertIn("personal: archive 1, keep 1, trash 1, spam 1, label 1, gtd 2", out)

  def test_gtd_and_archive_on_one_thread(self):
    self.run_script("mail-apply.py", stdin="personal gtd 9 aaaaaaaaaaaaaaaa\npersonal archive aaaaaaaaaaaaaaaa\n",
                    check=0)
    gtd9 = next(l["id"] for l in self.mail()[PERSONAL]["labels"] if l["name"] == "GTD-9")
    self.assertEqual(self.labels_of(PERSONAL, "aaaaaaaaaaaaaaaa"), {"UNREAD", gtd9})

  def test_refusals(self):
    before = self.mail()
    p = self.run_script("mail-apply.py", stdin="personal trash aaaaaaaaaaaaaaaa\npersonal spam aaaaaaaaaaaaaaaa\n")
    self.assertEqual(p.returncode, 2)
    self.assertIn("both trash and spam", p.stdout)
    p = self.run_script("mail-apply.py", stdin="nowhere archive aaaaaaaaaaaaaaaa\n")
    self.assertEqual(p.returncode, 2)
    p = self.run_script("mail-apply.py", stdin="personal label NewOne aaaaaaaaaaaaaaaa\n")
    self.assertEqual(p.returncode, 1)
    self.assertIn("--create-labels", p.stdout)
    self.assertEqual(self.mail(), before)
    self.run_script("mail-apply.py", "--create-labels", stdin="personal label NewOne aaaaaaaaaaaaaaaa\n", check=0)

  def test_dry_run(self):
    before = self.mail()
    out = self.run_script("mail-apply.py", "--dry-run", stdin="personal archive aaaaaaaaaaaaaaaa\n", check=0).stdout
    self.assertIn("thread modify aaaaaaaaaaaaaaaa --remove INBOX,STARRED", out)
    self.assertEqual(self.mail(), before)


class NewTask(Base):
  def setUp(self):
    super().setUp()
    self.set_mail({PERSONAL: {"aaaaaaaaaaaaaaaa": {"messages": [msg("m1", "a@x.example", PERSONAL, "s",
                                                                    ["INBOX", "STARRED"])]}}, WORK: {}})

  def notes(self, n):
    with open(os.path.join(self.gtd, "tasks", str(n), "notes.md")) as f:
      return f.read()

  def calls(self):
    with open(os.path.join(self.gtd, "calls.log")) as f:
      return f.read()

  def test_from_mail_with_defer_and_archive(self):
    out = self.run_script("gtd-new-task.py", "--subject", "HOME: Fill in the form", "--mailbox", "personal",
                          "--thread", "aaaaaaaaaaaaaaaa", "--archive", "--defer", "2",
                          stdin="Clinic wants the forms.\nBy Thursday.\n", check=0).stdout
    self.assertIn("task 101", out)
    self.assertEqual(self.notes(101),
                     "# HOME: Fill in the form\nTask Number: 101\n"
                     "https://mail.google.com/mail/?authuser=ian.miell%40gmail.com#all/aaaaaaaaaaaaaaaa\n\n"
                     "Clinic wants the forms.\nBy Thursday.\n")
    self.assertTrue(os.path.lexists(os.path.join(self.gtd, "status", "waiting", "101")))
    calls = self.calls()
    self.assertIn("nt HOME: Fill in the form GO_TO_TASK=N CTX=web", calls)
    self.assertIn("push", calls)
    self.assertIn("defer 101 2", calls)
    gtd = next(l["id"] for l in self.mail()[PERSONAL]["labels"] if l["name"] == "GTD-101")
    self.assertEqual(self.labels_of(PERSONAL, "aaaaaaaaaaaaaaaa"), {gtd})

  def test_with_link_only(self):
    self.run_script("gtd-new-task.py", "--subject", "CS: Reply to Bob", "--link", "https://slack.example/p1",
                    "--status", "someday", "--priority", "high", stdin="Bob asked.\n", check=0)
    self.assertIn("Task Number: 101\nhttps://slack.example/p1\n\nBob asked.\n", self.notes(101))
    self.assertIn("ms someday 101", self.calls())
    self.assertIn("mp high 101", self.calls())
    self.assertEqual(self.gog_calls(), [])

  def test_bad_arguments(self):
    self.run_script("gtd-new-task.py", "--subject", "CS: x", check=2)
    self.run_script("gtd-new-task.py", "--subject", "CS: x", "--mailbox", "work", check=2)
    self.run_script("gtd-new-task.py", "--subject", "CS: x", "--link", "l", "--defer", "1", "--status", "todo", check=2)


class PaEnv(Base):
  def setUp(self):
    super().setUp()
    t = lambda mid, frm, labels: {"messages": [msg(mid, frm, "x@y.example", "s", labels)]}
    self.set_mail({PERSONAL: {"aaaaaaaaaaaaaaaa": t("m1", f"Ian <{PERSONAL}>", ["SENT"]),
                              "bbbbbbbbbbbbbbbb": t("m2", "a@x.example", ["INBOX"])},
                   WORK: {"cccccccccccccccc": t("m3", "someone@else.example", ["SENT"])}})

  def test_mail_checks(self):
    p = self.run_script("pa-env.py", "check", "--only", "mail")
    self.assertEqual(p.returncode, 1)
    self.assertIn("mail personal (ian.miell@gmail.com) via gog: account ok, write ok", p.stdout)
    self.assertIn("mail work (ian.miell@container-solutions.com) via gog: account thread cccccccccccccccc has no SENT "
                  "message from ian.miell@container-solutions.com", p.stdout)
    self.assertEqual(self.labels_of(PERSONAL, "bbbbbbbbbbbbbbbb"), {"INBOX"})

  def test_windows_and_mark(self):
    out = self.run_script("pa-env.py", "check", "--only", "windows", "--json", check=0).stdout
    w = {x["channel"]: x for x in json.loads(out)["windows"]}
    self.assertEqual(w["slack"]["source"], "no record: last 24h")
    self.assertEqual(w["whatsapp"]["whatsapp_since"], "1440m")
    os.makedirs(self.env["PA_STATE"])
    with open(os.path.join(self.env["PA_STATE"], "slack-last-run"), "w") as f:
      f.write(f"{int(time.time()) - 30 * 86400}\n")
    with open(os.path.join(self.env["PA_STATE"], "whatsapp-last-run"), "w") as f:
      f.write(f"{int(time.time()) - 3600}\n")
    w = {x["channel"]: x for x in json.loads(self.run_script("pa-env.py", "check", "--only", "windows", "--json",
                                                              check=0).stdout)["windows"]}
    self.assertEqual(w["slack"]["source"], "capped at 7 days")
    self.assertEqual(w["whatsapp"]["source"], "last run")
    self.assertIn(w["whatsapp"]["whatsapp_since"], ("60m", "61m"))
    self.run_script("pa-env.py", "mark", "slack", check=0)
    with open(os.path.join(self.env["PA_STATE"], "slack-last-run")) as f:
      self.assertLess(abs(int(f.read()) - time.time()), 5)


class MeetingFiles(Base):
  def setUp(self):
    super().setUp()
    self.inbox = self.env["MEETINGS_INBOX"]
    self.meetings = os.path.join(self.gtd, "meetings")
    os.makedirs(self.inbox)
    subprocess.run(["git", "init", "-q", self.gtd], check=True)

  def touch(self, path, text="x", old=True):
    with open(path, "w") as f:
      f.write(text)
    if old:
      t = time.time() - 600
      os.utime(path, (t, t))

  def test_slug_matches_tr(self):
    sys.path.insert(0, SCRIPTS)
    import importlib.util
    spec = importlib.util.spec_from_file_location("meeting_files", os.path.join(SCRIPTS, "meeting-files.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for title in ("DNB/Container Solutions - Follow up call", "Önsel's café: Q4 · plan", "a\tb  c", "Mr. X (1:1)"):
      tr = subprocess.run("tr ' ' '_' | LC_ALL=C tr -cd '[:alnum:]_'", shell=True, input=title.encode(),
                          capture_output=True).stdout.decode()
      self.assertEqual(mod.describe(title), tr, title)
    self.assertEqual(mod.describe("DNB/Container Solutions - Follow up call"), "DNBContainer_Solutions__Follow_up_call")
    self.assertEqual(mod.describe("-"), "no_calendar_match")

  def test_recording_path(self):
    self.touch(os.path.join(self.inbox, "20261015_1130.mp4"), "video")
    self.touch(os.path.join(self.inbox, "20261015_1130.mkv"), "raw")
    out = self.run_script("meeting-files.py", "pending", check=0).stdout
    self.assertIn("20261015_1130 recording: 20261015_1130.mp4 5B, 20261015_1130.mkv 3B", out)
    out = self.run_script("meeting-files.py", "plan", "20261015_1130", "Acme / CS: kickoff", check=0).stdout
    self.assertIn("recording path, new stem 20261015_1130_Acme__CS_kickoff", out)
    self.run_script("meeting-files.py", "apply", "20261015_1130", "Acme / CS: kickoff", check=0)
    self.assertTrue(os.path.exists(os.path.join(self.meetings, "20261015_1130_Acme__CS_kickoff.mp4")))
    self.assertFalse(os.path.exists(os.path.join(self.inbox, "20261015_1130.mp4")))

  def test_never_overwrites(self):
    self.touch(os.path.join(self.inbox, "20261015_1130.mp4"), "video")
    self.touch(os.path.join(self.meetings, "20261015_1130_X.txt"), "already")
    self.run_script("meeting-files.py", "plan", "20261015_1130", "X", check=1)
    self.run_script("meeting-files.py", "apply", "20261015_1130", "X", check=1)
    self.assertTrue(os.path.exists(os.path.join(self.inbox, "20261015_1130.mp4")))

  def test_transcript_path(self):
    m = lambda f: os.path.join(self.meetings, f)
    self.touch(m("20261015_1130.txt"), "transcript")
    self.touch(m("20261015_1130.txt.gpt-5-nano.aisummary"), "summary")
    self.touch(m("20261015_1130.mp4"), "video")
    self.touch(m("20261015_1130.mkv"), "raw")
    subprocess.run(["git", "-C", self.gtd, "add", "meetings/20261015_1130.txt"], check=True)
    out = self.run_script("meeting-files.py", "apply", "20261015_1130", "--name", "Weekly_sync", check=0).stdout
    self.assertIn("git mv: 20261015_1130.txt -> meetings/20261015_1130_Weekly_sync.txt", out)
    self.assertIn("mv + git add: 20261015_1130.txt.gpt-5-nano.aisummary", out)
    self.assertIn("mv: 20261015_1130.mp4", out)
    self.assertIn("gtd push: ok", out)
    self.assertTrue(os.path.exists(m("20261015_1130.mkv")))  # the .mkv isn't renamed
    staged = subprocess.run(["git", "-C", self.gtd, "diff", "--cached", "--name-only"], capture_output=True,
                            text=True).stdout.split()
    self.assertIn("meetings/20261015_1130_Weekly_sync.txt", staged)
    self.assertIn("meetings/20261015_1130_Weekly_sync.txt.gpt-5-nano.aisummary", staged)

  def test_dedupe_and_wait(self):
    m = lambda f: os.path.join(self.meetings, f)
    self.touch(m("20261015_1130_X.txt"), "same")
    self.touch(m("20261015_1130_X (1).txt"), "same")
    self.assertIn("deleted", self.run_script("meeting-files.py", "dedupe", "20261015_1130_X", check=0).stdout)
    self.touch(m("20261015_1130_X (1).txt"), "different")
    self.run_script("meeting-files.py", "dedupe", "20261015_1130_X", check=1)
    out = self.run_script("meeting-files.py", "wait", "20261015_1130_X", "--interval", "1", "--add", check=0).stdout
    self.assertIn("ready:", out)
    self.run_script("meeting-files.py", "wait", "20261015_1130_Y", "--interval", "1", "--timeout", "2", check=1)

  @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
  def test_mkv_checks(self):
    mkv, mp4 = os.path.join(self.inbox, "20261015_1130.mkv"), os.path.join(self.meetings, "20261015_1130_X.mp4")
    for path, secs in ((mkv, "3"), (mp4, "3")):
      subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=duration={secs}", "-y", path],
                     check=True)
    out = self.run_script("meeting-files.py", "mkv", "20261015_1130", "20261015_1130_X", check=1).stdout
    self.assertIn("FAIL  neither changed in the last 60s", out)
    for p in (mkv, mp4):
      os.utime(p, (time.time() - 600, time.time() - 600))
    out = self.run_script("meeting-files.py", "mkv", "20261015_1130", "20261015_1130_X", check=0).stdout
    self.assertIn("all checks pass", out)
    self.assertTrue(os.path.exists(mkv))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=6", "-y", mp4], check=True)
    os.utime(mp4, (time.time() - 600, time.time() - 600))
    out = self.run_script("meeting-files.py", "mkv", "20261015_1130", "20261015_1130_X", "--delete", check=1).stdout
    self.assertIn("FAIL  durations match", out)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=3", "-y", mp4], check=True)
    os.utime(mp4, (time.time() - 600, time.time() - 600))
    out = self.run_script("meeting-files.py", "mkv", "20261015_1130", "20261015_1130_X", "--delete", check=0).stdout
    self.assertIn("deleted", out)
    self.assertFalse(os.path.exists(mkv))


class LinkedInState(Base):
  def li(self, *args, stdin="", check=None):
    return self.run_script(None, *args, stdin=stdin, script=LINKEDIN, check=check)

  def test_window_done(self):
    out = self.li("window", check=0).stdout
    self.assertIn("# no linkedin-sync-last", out)
    self.li("done", "2026-10-20T08:00:00Z", check=0)
    self.assertIn("LAST 2026-10-20T08:00:00Z\n", self.li("window", check=0).stdout)

  def test_queue_log_defer(self):
    self.li("log", "sent", "https://www.linkedin.com/in/a", "A Person", check=0)
    self.li("log", "deferred", "https://www.linkedin.com/in/d", "D Person", check=0)
    self.li("log", "no-connect", "https://www.linkedin.com/in/n", "N Person", check=0)
    page = ("junk\nVIEWERS-BEGIN\n" +
            "\n".join(json.dumps({"url": f"https://www.linkedin.com/in/{x}", "name": f"{x.upper()} Person"})
                      for x in ("a", "b", "c", "d", "n")) + "\nVIEWERS-END 5\nmore junk\n")
    out = self.li("queue", "--max", "2", stdin=page, check=0).stdout
    lines = [l for l in out.splitlines() if not l.startswith("#")]
    self.assertEqual([l.split("\t")[0][-1] for l in lines], ["d", "b", "c", "n"])
    self.assertEqual(out.splitlines()[3], "# over the cap: pass the lines below to `defer`")
    self.li("defer", stdin="\n".join(lines[2:]) + "\n", check=0)
    with open(os.path.join(self.env["PA_LINKEDIN_STATE"], "linkedin-invites.log")) as f:
      self.assertEqual(f.read().count("\tdeferred\t"), 3)
    p = self.li("queue", stdin=page.replace("VIEWERS-END 5", "VIEWERS-END 6"))
    self.assertNotEqual(p.returncode, 0)

  def test_evidence(self):
    with open(os.path.join(self.gtd, "meetings", "20261016_1508_Acme.txt"), "w") as f:
      f.write("Speaker 1: thanks Dana Lee for joining\n")
    for name, text in (("Dana_Lee.md", "## Dana Lee\n"), ("Eli_Moss.md", "## Eli Moss\n"),
                       ("Fay_Ng.md", "## Fay Ng\n"), ("Other.md", "Introduced by Eli Moss.\n")):
      with open(os.path.join(self.gtd, "people", name), "w") as f:
        f.write(text)
    imp = ("Read 3 cards\n  Created Dana_Lee.md | Dana Lee | CTO at Acme | connected 01 Oct 2026 | https://x\n"
           "  Created Eli_Moss.md | Eli Moss | Eng | connected 01 Oct 2026 | https://y\n"
           "  Pending Fay Ng | PM | connected 01 Oct 2026 | https://z | same name as Fay_Ng.md\n"
           "Created 2 people files; added LinkedIn links to 0 existing files.\n")
    out = self.li("evidence", stdin=imp, check=0).stdout.splitlines()
    self.assertEqual(out, ["Dana Lee\tmet\tmeetings/20261016_1508_Acme.txt",
                           "Eli Moss\tin-touch\tpeople/Other.md",
                           "Fay Ng\tforgotten?\t-"])


class RulesMatchSenders(unittest.TestCase):
  """The addresses the newsletter rules list are the ones senders.tsv gives the scripts."""

  def test_rules_and_tsv_agree(self):
    import re
    rules = os.path.join(HERE, "..", "rules")
    tsv = {}
    with open(os.path.join(rules, "senders.tsv")) as f:
      for line in f:
        if line.strip() and not line.startswith("#"):
          addr, bucket = line.split("\t")[:2]
          tsv[addr] = bucket
    for name, bucket in (("newsletters-to-trash.md", "trash"), ("read-later-stays-in-inbox.md", "read-later")):
      with open(os.path.join(rules, name)) as f:
        listed = set(re.findall(r"^- .*?\(`([^`]+@[^`]+)`\)", f.read(), re.M))
      self.assertTrue(listed, name)
      self.assertEqual(listed, {a for a, b in tsv.items() if b == bucket}, name)


class VoiceCheckStillRuns(Base):
  def test_voice_check(self):
    p = self.run_script("voice-check.py", "--channel", "slack", stdin="sounds good - thanks\n")
    self.assertEqual(p.returncode, 0, p.stdout)


if __name__ == "__main__":
  unittest.main()
