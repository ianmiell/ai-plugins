#!/usr/bin/env python3
"""Tests for the comms scripts (comms-gather, comms-items, mail-draft, slack-merge) and the
comms parts of people-note, mail-gather and mail-apply, against made-up data.

  python3 -m unittest discover -s personal-assistant/tests -p 'test_comms.py' -v

Nothing here touches Ian's mail, Slack or notifications: the Base class from test_scripts.py
points GTD_DIR, PA_STATE and PA_GOG into a temporary folder, PA_MACHINE=other, and
PA_NO_NOTIFY=1 keeps pa-notify.py quiet. Gmail drafts go to a small fake (FAKE_DRAFTS below)
in front of fake_gog.py, which has no drafts command.
"""

import datetime
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
from test_scripts import HERE, PERSONAL, WORK, Base, msg  # noqa: E402

# gog with `gmail drafts ...` added: records the call, answers like gog; anything else goes to fake_gog.py.
FAKE_DRAFTS = r"""#!/usr/bin/env python3
import json, os, subprocess, sys
argv = sys.argv[1:]
if "drafts" in argv:
  with open(os.environ["FAKE_GOG_LOG"], "a") as f:
    f.write(json.dumps(argv) + "\n")
  if "--gmail-no-send" not in argv:
    sys.exit(3)
  print(json.dumps({"draftId": "r-123", "message": {"id": "m-new"}}))
  sys.exit(0)
sys.exit(subprocess.run([sys.executable, os.environ["REAL_FAKE_GOG"]] + argv).returncode)
"""

ITEMS = [
  {"bucket": "act", "ch": "W✉+S", "who": "Jane Doe (Acme), Contract renewal", "what": "Wants sign-off by Fri",
   "tags": "🗂 → new task", "rec": "Draft asking for the redline; 👀 on the ping", "go": ["draft", "task", "react"],
   "mail": [1], "slack": ["https://containersolutions.slack.com/archives/D1/p1794300000000100"],
   "draft": "Jane - can you send the redline? Ian", "task": "CS: Sign off Acme renewal", "when": "2026-11-12T09:00"},
  {"bucket": "act", "ch": "WA", "who": "Sam, 1:1, 15:53", "what": "Pint on Thu?", "rec": "Draft yup",
   "draft": "yup", "whatsapp": "Sam", "when": "2026-11-11T15:53"},
  {"bucket": "fyi", "who": "GitHub", "what": "Notifications", "rec": "Archive", "mail": [2], "group": "n"},
  {"bucket": "fyi", "who": "Calendly", "what": "Notifications", "rec": "Archive", "mail": ["personal 000000000000000b"],
   "group": "n"},
  {"bucket": "Junk", "ch": "P✉", "who": "Shop", "what": "Sale", "rec": "Trash", "mail": [["personal", "000000000000000c"]]},
  {"bucket": "apps", "ch": "🔑 P", "who": "PhotoPrintr", "what": "Can see all your Drive files", "tags": "🆕",
   "rec": "Cut unless you use it", "app": "PhotoPrintr"},
  {"bucket": "schedule", "ch": "📅 W", "who": "Bob, Q4 planning Tue 14:00", "what": "Invite", "rec": "Accept",
   "go": ["accept"], "event": "Q4 planning Tue 14:00"},
  {"bucket": "Read later", "ch": "P✉", "who": "Newsletter", "what": "Weekly | issue", "rec": "Keep, star",
   "mail": [{"mailbox": "personal", "thread": "000000000000000d"}]},
]


class CommsBase(Base):
  def setUp(self):
    super().setUp()
    self.env["PA_NO_NOTIFY"] = "1"
    self.state = self.env["PA_STATE"]

  def jsonl(self, items):
    return "\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n"

  def gathered(self):
    """A saved mail-gather.py list: 1 is work thread 1a2b3c4d5e6f7a8b, 2 personal ...a."""
    os.makedirs(self.state, exist_ok=True)
    data = [{"mailbox": "work", "query": "in:inbox", "count": 1, "more": False,
             "threads": [{"n": 1, "thread": "1a2b3c4d5e6f7a8b", "from": "Jane Doe <jane@acme.example>",
                          "subject": "Contract renewal"}]},
            {"mailbox": "personal", "query": "in:inbox", "count": 1, "more": True,
             "threads": [{"n": 2, "thread": "000000000000000a", "from": "GitHub <noreply@github.com>",
                          "subject": "PR merged"}]}]
    with open(os.path.join(self.state, "mail-gather-last.json"), "w") as f:
      json.dump(data, f)


class CommsGather(CommsBase):
  def setUp(self):
    super().setUp()
    t = lambda mid, frm, labels: {"messages": [msg(mid, frm, "x@y.example", "s", labels)]}
    self.set_mail({PERSONAL: {"aaaaaaaaaaaaaaaa": t("m1", f"Ian <{PERSONAL}>", ["SENT"]),
                              "bbbbbbbbbbbbbbbb": t("m2", "Sam <sam@friends.example>", ["INBOX"])},
                   WORK: {"cccccccccccccccc": t("m3", f"Ian <{WORK}>", ["SENT"]),
                          "dddddddddddddddd": t("m4", "Jane <jane@acme.example>", ["INBOX"])}})

  def scope(self, arg, machine="other"):
    self.env["PA_MACHINE"] = machine
    return json.loads(self.run_script("comms-gather.py", "scope", arg, "--json", check=0).stdout)

  def test_scope_words(self):
    s = self.scope("")
    self.assertEqual(s["tags"], ["W✉", "P✉", "S", "📅 W", "📅 P"])
    self.assertEqual(s["off"], ["whatsapp", "linkedin", "apps-work", "apps-personal"])
    self.assertEqual(s["mail"]["work"], {"query": "in:inbox", "via": "gog"})
    self.assertEqual(s["windows"]["slack"]["source"], "no record: last 24h")
    s = self.scope("2d work")
    self.assertEqual(s["tags"], ["W✉", "S", "📅 W"])
    self.assertEqual(s["mail"]["work"]["query"], "in:inbox newer_than:2d")
    self.assertLess(abs(s["windows"]["slack"]["epoch"] - (time.time() - 2 * 86400)), 5)
    s = self.scope("personal unread", machine="macbook-pro")
    self.assertEqual(s["tags"], ["P✉", "WA", "📅 P", "🔑 P"])
    self.assertEqual(s["mail"]["personal"]["query"], "in:inbox is:unread")
    self.assertTrue(s["windows"]["whatsapp"]["unread"])
    s = self.scope("mail slack morning", machine="macbook-pro")
    self.assertEqual(s["tags"], ["W✉", "P✉", "S"])
    self.assertTrue(s["morning"])
    self.assertEqual(s["mail"]["work"]["via"], "connector")
    s = self.scope("since monday whatsapp frobnicate")
    self.assertEqual(s["tags"], [])
    self.assertEqual(s["off"], ["whatsapp"])
    self.assertEqual(s["not_understood"], ["frobnicate"])
    monday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
    self.assertIn(monday.strftime("%Y/%m/%d"), self.scope("since monday")["mail"]["work"]["query"])
    self.assertTrue(os.path.exists(os.path.join(self.state, "comms-scope.json")))

  def test_run_sections(self):
    p = self.run_script("comms-gather.py", "run", "work", "--tidy-dry-run", check=0)
    out = p.stdout
    for name in ("scope", "pa-env", "mail", "tidy"):
      self.assertIn(f"▶ {name}\n", out)
    self.assertIn("◀ mail: ok", out)
    self.assertIn("━━ WORK", out)
    self.assertNotIn("━━ PERSONAL", out)
    self.assertIn("comms-gather: ran pa-env, mail, tidy; all ok", out)
    self.assertIn("still to do with connectors: Slack", out)
    self.assertTrue(os.path.exists(os.path.join(self.state, "mail-gather-last.json")))
    for line in out.splitlines():
      self.assertFalse(line.startswith("="), line)

  def test_failed_section_doesnt_stop_others(self):
    self.env["PA_GOG"] = "/nonexistent/gog"
    p = self.run_script("comms-gather.py", "run", "personal", check=0)
    self.assertIn("◀ mail: FAILED", p.stdout)
    self.assertIn("◀ tidy: FAILED", p.stdout)
    self.assertIn("FAILED: pa-env, mail, tidy (see each section above", p.stdout)


class CommsItems(CommsBase):
  def add(self, items, *args, check=0):
    return self.run_script("comms-items.py", "add", *args, stdin=self.jsonl(items), check=check)

  def test_add_checks_everything_first(self):
    self.gathered()
    bad = ITEMS[:2] + [{"bucket": "nope", "ch": "S", "who": "x"}, {"bucket": "act", "ch": "P✉", "who": "y"},
                       {"bucket": "fyi", "mail": [99], "who": "z"}, {"bucket": "apps", "ch": "🔑 W", "who": "A", "go": ["cut"]}]
    p = self.add(bad, check=2)
    self.assertIn("line 3: bucket 'nope'", p.stdout)
    self.assertIn("line 4: P✉ item without a personal thread", p.stdout)
    self.assertIn("line 5: mail 99: not a number", p.stdout)
    self.assertIn("line 6: go can't cut", p.stdout)
    self.assertFalse(os.path.exists(os.path.join(self.state, "comms-items.json")))

  def test_render_numbers_and_tables(self):
    self.gathered()
    self.add(ITEMS, "--reset")
    out = self.run_script("comms-items.py", "render", check=0).stdout
    self.assertTrue(out.startswith("**COMMS — W✉ 1 · P✉ 4 · S 1 · WA 1 · 📅 1 invite · 🔑 1 app**"), out)
    self.assertIn("| 1 | WA | Sam, 1:1, 15:53 | Pint on Thu? |", out)   # waiting longest first
    self.assertIn("| 2 | W✉+S | Jane Doe (Acme), Contract renewal |", out)
    self.assertLess(out.index("#### Schedule"), out.index("#### Google apps"))
    self.assertIn("#### Read later / FYI / Junk", out)
    self.assertIn("| 5 | P✉ | Newsletter | Weekly \\| issue |", out)
    self.assertIn("| 6–7 | P✉ | GitHub, Calendly | Notifications |  | Archive |", out)
    self.assertIn("| 8 | P✉ | Shop |", out)
    self.assertIn("More mail after this batch in personal", out)
    with open(os.path.join(self.state, "comms-shown.tsv")) as f:
      self.assertIn("work\t1a2b3c4d5e6f7a8b\n", f.read())
    # a second batch carries on from 9
    self.add([{"bucket": "fyi", "ch": "P✉", "who": "Bank", "what": "Statement", "mail": ["personal 000000000000000e"]}])
    out = self.run_script("comms-items.py", "render", check=0).stdout
    self.assertIn("| 9 | P✉ | Bank |", out)
    self.assertIn("Nothing in Act now on any channel.", out)
    nxt = self.run_script("comms-items.py", "next", check=0).stdout
    self.assertIn("mail-gather.py list --mailbox personal --query 'in:inbox' --exclude ", nxt)

  def test_mail_layout(self):
    self.gathered()
    self.add(ITEMS[2:5] + ITEMS[:1], "--reset")
    out = self.run_script("comms-items.py", "render", "--mail", check=0).stdout
    self.assertTrue(out.startswith("**MAIL — W✉ 1 · P✉ 3**"), out)
    self.assertLess(out.index("### WORK"), out.index("### PERSONAL"))
    self.assertIn("| 1 | Jane Doe (Acme), Contract renewal |", out)
    self.assertIn("| 2–3 | GitHub, Calendly |", out)

  def expand(self, reply, check=0):
    return self.run_script("comms-items.py", "expand", reply, check=check)

  def rendered(self):
    self.gathered()
    self.add(ITEMS, "--reset")
    self.run_script("comms-items.py", "render", check=0)

  def plan(self):
    with open(os.path.join(self.state, "comms-mail-plan.txt")) as f:
      return [l.split("  #")[0] for l in f.read().splitlines()]

  def test_expand_go_except_and_overrides(self):
    self.rendered()
    out = self.expand("go except 2, archive 5, 1: say I'll call tonight, after the match").stdout
    self.assertEqual(self.plan(), ["work keep 1a2b3c4d5e6f7a8b", "personal archive 000000000000000d",
                                   "personal archive 000000000000000a", "personal archive 000000000000000b",
                                   "personal trash 000000000000000c"])
    self.assertIn("Ian says: \"say I'll call tonight, after the match\"", out)
    self.assertIn("calendar respond accept to Q4 planning", out)
    self.assertNotIn("google-apps.py cut", out)  # go never cuts an app
    self.assertIn("no action (mail stays in the inbox, starred): 2, 4", out)
    self.assertIn("mail-apply.py < ", out)

  def test_expand_verbs(self):
    self.rendered()
    out = self.expand("draft 1 and 2, trash 5, 8; 👀 2; task 2; cut 4; label Receipts 6").stdout
    self.assertEqual(self.plan(), ["work keep 1a2b3c4d5e6f7a8b", "personal trash 000000000000000d",
                                   "personal label Receipts 000000000000000a", "personal keep 000000000000000b",
                                   "personal trash 000000000000000c"])
    self.assertIn('whatsapp.py draft "Sam"', out)
    self.assertIn("mail-draft.py work 1a2b3c4d5e6f7a8b", out)
    self.assertIn('text: "Jane - can you send the redline? Ian"', out)
    self.assertIn("slack_add_reaction eyes on https://containersolutions.slack.com/archives/D1/p1794300000000100", out)
    self.assertIn('gtd-new-task.py --subject "CS: Sign off Acme renewal" --mailbox work --thread 1a2b3c4d5e6f7a8b', out)
    self.assertIn('google-apps.py cut personal "PhotoPrintr"', out)
    out = self.expand("keep the rest, trash 8").stdout
    self.assertEqual(self.plan()[-1], "personal trash 000000000000000c")
    self.assertIn("personal keep 000000000000000a", self.plan())
    self.assertIn('google-apps.py keep personal "PhotoPrintr"', out)

  def test_expand_refuses_to_guess(self):
    self.rendered()
    p = self.expand("go, frobnicate 4, archive 42", check=1)
    self.assertIn('? not understood: "frobnicate 4"', p.stdout)
    self.assertIn("no item 42", p.stdout)
    self.assertIn("Nothing saved", p.stdout)
    self.assertFalse(os.path.exists(os.path.join(self.state, "comms-mail-plan.txt")))
    p = self.expand("trash 5, archive 5", check=1)
    self.assertIn("? conflicting: 5", p.stdout)

  def test_connector_mailbox_on_macbook(self):
    self.rendered()
    self.env["PA_MACHINE"] = "macbook-pro"
    out = self.expand("archive 2").stdout
    self.assertIn("work thread 1a2b3c4d5e6f7a8b: unlabel_thread [INBOX, STARRED]", out)
    self.assertNotIn("work archive", out)

  def test_show_and_notify(self):
    self.rendered()
    out = self.run_script("comms-items.py", "show", "2", "6-7", check=0).stdout
    self.assertIn("2 [Act now] W✉+S Jane Doe (Acme), Contract renewal: Wants sign-off by Fri [mail work 1a2b3c4d5e6f7a8b;"
                  " slack https://", out)
    self.assertIn("7 [FYI / done] P✉ Calendly", out)
    out = self.run_script("comms-items.py", "notify", "--failed", "slack", check=0).stdout
    line = out.splitlines()[0]
    self.assertRegex(line, r"^Comms ready \(\w{3} \d\d \w{3}\): 2 act now, 1 to schedule, 1 Google app, "
                           r"4 FYI/junk\. Top: Sam: Pint on Thu\? Slack failed\.$")
    self.assertLessEqual(len(line), 200)
    self.assertNotIn('"', line)


class MailDraft(CommsBase):
  def setUp(self):
    super().setUp()
    fake = os.path.join(self.tmp, "gog-drafts.py")
    with open(fake, "w") as f:
      f.write(FAKE_DRAFTS)
    os.chmod(fake, 0o755)
    self.env["REAL_FAKE_GOG"] = self.env["PA_GOG"]
    self.env["PA_GOG"] = fake
    self.set_mail({PERSONAL: {"1a159da84468dd9d": {"messages": [
      msg("m1", "Sam Friend <sam@friends.example>", PERSONAL, "Dinner?", ["INBOX"]),
      msg("m2", f"Ian <{PERSONAL}>", "sam@friends.example", "Re: Dinner?", ["SENT"])]}}, WORK: {}})

  def drafts(self):
    return [c for c in self.gog_calls() if "drafts" in c]

  def test_reply_to_last_other_message(self):
    p = self.run_script("mail-draft.py", "personal", "1a159da84468dd9d",
                        stdin="Thursday works - I'll book the table.\n\nIan\n", check=0)
    self.assertIn("voice check: clean", p.stdout)
    self.assertIn("draft r-123 reply in personal thread 1a159da84468dd9d, to message m1", p.stdout)
    self.assertIn("To: Sam Friend <sam@friends.example>", p.stdout)
    self.assertIn("Subject: Re: Dinner?", p.stdout)
    call = self.drafts()[-1]
    self.assertEqual(call[call.index("drafts"):call.index("drafts") + 3], ["drafts", "reply", "m1"])
    self.assertIn("--gmail-no-send", call)
    self.assertEqual(call[call.index("--body") + 1], "Thursday works - I'll book the table.\n\nIan")

  def test_voice_check_refuses(self):
    p = self.run_script("mail-draft.py", "personal", "1a159da84468dd9d",
                        stdin="I hope this email finds you well — best regards\n")
    self.assertEqual(p.returncode, 1)
    self.assertIn("no draft made", p.stdout)
    self.assertEqual(self.drafts(), [])
    self.run_script("mail-draft.py", "personal", "1a159da84468dd9d", "--force",
                    stdin="I hope this email finds you well\n", check=0)
    self.assertEqual(len(self.drafts()), 1)

  def test_forward_dry_run_and_connector(self):
    p = self.run_script("mail-draft.py", "personal", "1a159da84468dd9d", "--forward", "pat@acme.example",
                        "--dry-run", stdin="Pat - yours, can you pick it up?\n", check=0)
    self.assertIn("would run: -a ian.miell@gmail.com --gmail-no-send", p.stdout)
    self.assertIn("gmail drafts forward m1 --to pat@acme.example --note", p.stdout)
    self.assertEqual(self.drafts(), [])
    self.env["PA_MACHINE"] = "macbook-pro"
    p = self.run_script("mail-draft.py", "work", "1a15b0aad89c09a9", "--message", "w9", "--subject", "Contract",
                        "--to", "jane@acme.example", stdin="Thanks Jane - signed.\n", check=0)
    call = json.loads(p.stdout[p.stdout.index("{"):])
    self.assertEqual(call, {"body": "Thanks Jane - signed.", "to": ["jane@acme.example"], "subject": "Re: Contract",
                            "replyToMessageId": "w9"})
    self.assertEqual(self.drafts(), [])


DETAILED = """# Search Results for: \n\n## Messages (6 results)
### Result 1 of 6
Channel: DM (ID: D03KEGXQNTE)
Participants: Ian Miell (ID: URFKQUBEW), Ivy Scott (ID: U02CNPM55DF)
From: Ivy Scott <ivy@example.com> (ID: U02CNPM55DF) \nTime: 2026-11-12 14:14:04 GMT
Message_ts: {t1}
Permalink: [link](https://containersolutions.slack.com/archives/D03KEGXQNTE/p{p1})
Text: \nCan we just ignore this?\nIt's SUP-915.

---

### Result 2 of 6
Channel: DM (ID: D0BOB)
Participants: Ian Miell (ID: URFKQUBEW), Bob Jones (ID: U0BOB)
From: Ian Miell <ian@example.com> (ID: URFKQUBEW) \nTime: 2026-11-12 15:00:00 GMT
Message_ts: {t2}
Permalink: [link](https://containersolutions.slack.com/archives/D0BOB/p{p2})
Text: \nDone, thanks

---

### Result 3 of 6
Channel: DM (ID: D0SELF)
Participants: Ian Miell (ID: URFKQUBEW)
From: Ian Miell <ian@example.com> (ID: URFKQUBEW) \nTime: 2026-11-12 15:01:00 GMT
Message_ts: {t2}
Permalink: [link](https://containersolutions.slack.com/archives/D0SELF/p{p2})
Text: \nnote to self

---

### Result 4 of 6
Channel: #ccf-ci-failures (ID: C0CI)
From: ccf-release-bot (ID: U0BOT)  [BOT]
Time: 2026-11-12 14:55:03 GMT
Message_ts: {t1}
Permalink: [link](https://containersolutions.slack.com/archives/C0CI/p{p1}?thread_ts={t1}&cid=C0CI)
Text: \nBuild failed

---

### Result 5 of 6
Channel: #beach (ID: C03BEACH)
From: Gus Carr <gus@example.com> (ID: U02GUS) \nTime: 2026-11-12 16:00:16 GMT
Message_ts: {t3}
Permalink: [link](https://containersolutions.slack.com/archives/C03BEACH/p{p3}?thread_ts={t1}&cid=C03BEACH)
Text: \n<@URFKQUBEW|Ian Miell> what do you think?

---

### Result 6 of 6
Channel: #beach (ID: C03BEACH)
From: Gus Carr <gus@example.com> (ID: U02GUS) \nTime: 2026-11-01 16:00:16 GMT
Message_ts: {t0}
Permalink: [link](https://containersolutions.slack.com/archives/C03BEACH/p{p0})
Text: \ntoo old

---
"""


class SlackMerge(CommsBase):
  def setUp(self):
    super().setUp()
    now = int(time.time())
    self.since = now - 3600
    ts = {"t0": f"{now - 30 * 86400}.000100", "t1": f"{now - 1800}.000200", "t2": f"{now - 1200}.000300",
          "t3": f"{now - 600}.000400"}
    ts.update({k.replace("t", "p"): v.replace(".", "") for k, v in ts.items()})
    self.ts = ts
    text = DETAILED.format(**ts)
    self.wrapped = os.path.join(self.tmp, "dms.json")
    with open(self.wrapped, "w") as f:
      json.dump([{"type": "text", "text": json.dumps({"results": text, "pagination_info": "End"})}], f)
    self.plain = os.path.join(self.tmp, "mentions.txt")
    with open(self.plain, "w") as f:
      f.write(text)

  def read(self, path):
    with open(path) as f:
      return f.read()

  def test_grouping_and_drops(self):
    out = json.loads(self.run_script("slack-merge.py", "--since", str(self.since), "--json", self.wrapped, self.plain,
                                     check=0).stdout)
    convs = {c["where"]: c for c in out["conversations"]}
    self.assertEqual(sorted(convs), ["#beach thread", "DM Ivy Scott"])
    self.assertEqual(convs["DM Ivy Scott"]["link"],
                     f"https://containersolutions.slack.com/archives/D03KEGXQNTE/p{self.ts['p1']}")
    self.assertEqual(convs["#beach thread"]["link"],
                     f"https://containersolutions.slack.com/archives/C03BEACH/p{self.ts['p3']}"
                     f"?thread_ts={self.ts['t1']}&cid=C03BEACH")
    self.assertTrue(convs["#beach thread"]["mentions_ian"])
    self.assertEqual(convs["DM Ivy Scott"]["messages"], 1)  # the repeat across the two files is dropped
    self.assertEqual(out["dropped"]["you spoke last"], ["DM Bob Jones"])
    self.assertEqual(out["dropped"]["self-DM"], ["DM"])
    self.assertEqual(len(out["dropped"]["bots"]), 1)

  def test_text_allow_bot_and_gtd_batch(self):
    out = self.run_script("slack-merge.py", "--since", str(self.since), "--allow-bot", "ccf-release-bot",
                          "--keep-last", "--gtd-batch", stdin=self.read(self.plain), check=0).stdout
    self.assertIn("— 4 conversation(s) from 6 result(s); dropped: 1 self-DM", out)
    self.assertIn("#ccf-ci-failures thread", out)
    self.assertIn("DM Bob Jones", out)
    self.assertIn("gtd-find.py --batch input:", out)
    self.assertIn(f"Gus Carr | #beach | p{self.ts['t1'].replace('.', '')}", out)

  def test_concise_and_last_run(self):
    os.makedirs(self.state, exist_ok=True)
    with open(os.path.join(self.state, "slack-last-run"), "w") as f:
      f.write(f"{int(time.time()) - 7200}\n")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    concise = json.dumps({"results": "# Search Results\n\n## Messages (3 results)\n"
                                     f"1. DM with Ian Miell, Ivy Scott - Ivy Scott: Lunch?\nTomorrow? {stamp}\n"
                                     f"2. DM with Ian Miell - Ian Miell: self note {stamp}\n"
                                     f"3. #beach - Gus Carr: hello all {stamp}\n"})
    out = self.run_script("slack-merge.py", stdin=concise, check=0).stdout
    self.assertIn("2 conversation(s) from 3 result(s); dropped: 1 self-DM", out)
    self.assertIn("S1. DM Ivy Scott", out)
    self.assertIn("(no link: concise results)", out)


class PeopleBatch(CommsBase):
  def test_find_batch(self):
    for name, text in {"Jane_Doe.md": "## Jane Doe\n- Company: Acme\n", "Louise_Cox.md": "## Louise Cox\n- Email: louise@corp.example\n"}.items():
      with open(os.path.join(self.gtd, "people", name), "w") as f:
        f.write(text)
    out = self.run_script("people-note.py", "find", "--batch", check=0,
                          stdin="3: Jane Doe | jane@acme.example\nS2: Louise Corrigan | louise@corp.example\n7: Nobody Here\n").stdout
    self.assertIn("3: Jane Doe <jane@acme.example>\n  Jane_Doe.md\tname\tCompany: Acme", out)
    self.assertIn("S2: Louise Corrigan <louise@corp.example>\n  Louise_Cox.md\tcontains louise@corp.example", out)
    self.assertIn("7: Nobody Here\n  (no file)", out)
    p = self.run_script("people-note.py", "find")
    self.assertEqual(p.returncode, 2)


class StarredOutside(CommsBase):
  def setUp(self):
    super().setUp()
    p = lambda mid, labels: {"messages": [msg(mid, "a@x.example", PERSONAL, f"subject {mid}", labels)]}
    self.set_mail({PERSONAL: {"aaaaaaaaaaaaaaaa": p("m1", ["INBOX"]), "bbbbbbbbbbbbbbbb": p("m2", ["INBOX"]),
                              "cccccccccccccccc": p("m3", ["STARRED"])}, WORK: {}})

  def test_stars_recorded_and_told_apart(self):
    self.run_script("mail-apply.py", stdin="personal keep aaaaaaaaaaaaaaaa\npersonal archive bbbbbbbbbbbbbbbb\n", check=0)
    with open(os.path.join(self.state, "starred-by-pa.tsv")) as f:
      rows = [l.split("\t")[:2] for l in f.read().splitlines()]
    self.assertEqual(rows, [["personal", "aaaaaaaaaaaaaaaa"]])
    self.run_script("mail-apply.py", "--dry-run", stdin="personal keep bbbbbbbbbbbbbbbb  # a comment\n", check=0)
    with open(os.path.join(self.state, "starred-by-pa.tsv")) as f:
      self.assertEqual(len(f.read().splitlines()), 1)  # a dry run records nothing
    # Ian archives a's thread by hand, star and all left on: it's ours to unstar; c's star is older
    with open(self.state_file) as f:
      state = json.load(f)
    state["accounts"][PERSONAL]["threads"]["aaaaaaaaaaaaaaaa"]["messages"][0]["labelIds"] = ["STARRED"]
    with open(self.state_file, "w") as f:
      json.dump(state, f)
    out = self.run_script("mail-gather.py", "starred-outside", "--mailbox", "personal", check=0).stdout
    self.assertIn("2 starred outside the inbox: 1 starred by this plugin, 1 older", out)
    self.assertIn("personal unstar aaaaaaaaaaaaaaaa", out)
    self.assertNotIn("unstar cccccccccccccccc", out)
    self.assertIn("[older]", out)


class GatherExclude(CommsBase):
  def test_next_batch_skips_shown(self):
    p = lambda mid, d: {"messages": [msg(mid, "a@x.example", PERSONAL, f"s {mid}", ["INBOX"], date=d)]}
    self.set_mail({PERSONAL: {"000000000000000%d" % i: p(f"m{i}", 1792500000000 + i * 1000) for i in range(1, 6)},
                   WORK: {}})
    first = json.loads(self.run_script("mail-gather.py", "list", "--mailbox", "personal", "--max", "2", "--json",
                                       check=0).stdout)
    shown = [t["thread"] for t in first[0]["threads"]]
    self.assertTrue(first[0]["more"])
    with open(os.path.join(self.state, "mail-gather-last.json")) as f:
      self.assertEqual(json.load(f)[0]["threads"][0]["thread"], shown[0])
    ex = os.path.join(self.tmp, "shown.tsv")
    with open(ex, "w") as f:
      f.write("".join(f"personal\t{t}\n" for t in shown))
    second = json.loads(self.run_script("mail-gather.py", "list", "--mailbox", "personal", "--max", "2", "--exclude",
                                        ex, "--json", check=0).stdout)
    got = [t["thread"] for t in second[0]["threads"]]
    self.assertEqual(len(got), 2)
    self.assertFalse(set(got) & set(shown))


if __name__ == "__main__":
  unittest.main()
