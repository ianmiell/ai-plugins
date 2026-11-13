#!/usr/bin/env python3
"""Tests for ian-voice/scripts/voice-check.py, against made-up drafts.

  python3 -m unittest discover -s ian-voice/tests -v
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "voice-check.py")
spec = importlib.util.spec_from_file_location("voice_check", SCRIPT)
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)

CLEAN = """# Ten Things I Wish I'd Known About make

Recently a colleague asked me why our build took forty minutes.

I didn't know (and I'm not proud of that), so I went and looked.

```
$ make -j8 all  # the organization of this Makefile is a mess, e.g. this line
```

It turned out the `organize` target ran twice. In other words, we'd been paying for the same
work twice a day, eg on every merge to main, for about a year.

The fix took me a fortnight - mostly faff with the CI config. See the `color` flag at
https://example.com/organization/docs for more.

Keen to hear from you if you've hit the same thing.
"""


def found(text, register="blog"):
  return [(line, matched) for line, matched, _ in vc.check(text, register)]


class VoiceCheck(unittest.TestCase):

  def test_clean_draft_passes(self):
    self.assertEqual(vc.check(CLEAN), [])

  def test_dashes_and_abbreviations(self):
    text = "One thing\u2014the main one.\nFrom 2011\u20132026 it ran \u2013 badly.\nSee e.g. this, i.e. that.\nThis -- that.\nOr eg, this.\n"
    got = found(text)
    self.assertIn((1, "\u2014"), got)
    self.assertIn((2, "\u2013"), got)
    self.assertEqual(sum(1 for l, m in got if l == 2), 2)  # the range and the spaced dash
    self.assertIn((3, "e.g."), got)
    self.assertIn((3, "i.e."), got)
    self.assertIn((4, "--"), got)
    self.assertIn((5, "eg,"), got)

  def test_american_spellings_in_the_blog(self):
    text = ("The organization's behavior was\nfavorite of the center.\n\n"
            "We analyzed the catalog and canceled the license, then focused.\n")
    got = found(text)
    for want in [(1, "organization"), (1, "behavior"), (2, "favorite"), (2, "center"), (4, "analyzed"),
                 (4, "catalog"), (4, "canceled"), (4, "license"), (4, "focused")]:
      self.assertIn(want, got)
    msgs = {m: msg for _, m, msg in vc.check(text)}
    self.assertIn("use 'organisation'", msgs["organization"])
    self.assertIn("use 'focussed'", msgs["focused"])

  def test_spelling_skips_names_quotes_code_and_shared_words(self):
    text = ("We moved off Jira Data Center last year, and Active Directory too.\n\n"
            "> The organization was very large, as Meadows put it.\n\n"
            "Use `--color` here. The size, the prize and the program were fine.\n\n"
            "Organization matters. Initialize and containerize are left alone.\n")
    self.assertEqual(found(text), [(7, "Organization")])

  def test_book_register_wants_american_spelling(self):
    text = "The organisation's behaviour was the centre of it, and we were focussed\u2014mostly.\n"
    got = found(text, "book")
    self.assertEqual([m for _, m in got], ["organisation", "behaviour", "centre", "focussed"])
    msgs = [msg for _, _, msg in vc.check(text, "book")]
    self.assertIn("use 'organization'", msgs[0])
    self.assertEqual(found("The organization's behavior.\n", "book"), [])

  def test_avoid_list(self):
    text = ("Let's dive in. We can leverage this to unlock a seamless,\nrobust platform. "
            "Furthermore, it's worth noting that synergy matters.\n\n"
            "For instance, our journey (or our 'journey') went fine.\n\n"
            "Whilst the directory was full, I hope this helps.\n")
    got = [m for _, m in found(text)]
    for want in ["Let's dive", "can leverage", "unlock", "seamless", "robust", "Furthermore",
                 "it's worth noting", "synergy", "For instance", "journey", "Whilst", "directory",
                 "I hope this helps"]:
      self.assertIn(want, got)
    self.assertEqual(got.count("journey"), 1)

  def test_whilst_is_fine_in_cs_house_copy(self):
    self.assertEqual(found("Whilst we often work with large enterprises, this is fine.\n", "cs"), [])

  def test_structural_tells(self):
    text = ("# 5 Ways to Undo a Commit\n\nHave you ever wondered about git?\n\n"
            "It's not the technology. It's the funding.\n\n"
            "That's **really** it. **This whole sentence is the takeaway.** **Note:** fine.\n\n"
            "Wow!! #devops \U0001F680\n\nUltimately, the choice is yours.\n")
    got = found(text)
    for want in [(1, "# 5 Ways"), (3, "Have you ever wondered"), (5, "It's not the technology. It's"),
                 (7, "**really**"), (9, "!!"), (9, "#devops"), (9, "\U0001F680"), (11, "Ultimately")]:
      self.assertIn(want, got)
    self.assertNotIn("**Note:**", [m for _, m in got])
    self.assertEqual(found("# The 2026 Review\n\n## 3) Exit Codes\n\nA fine C# program.\n"), [])

  def test_a_phrase_wrapped_over_two_lines_reports_its_first_line(self):
    self.assertEqual(found("Some text and then in\nconclusion we stop.\n"), [(1, "in conclusion")])


class Cli(unittest.TestCase):

  def run_cli(self, *args, stdin=""):
    return subprocess.run([sys.executable, SCRIPT] + list(args), input=stdin, capture_output=True, text=True)

  def test_exit_codes_and_output(self):
    p = self.run_cli(stdin=CLEAN)
    self.assertEqual((p.returncode, p.stdout), (0, ""))
    p = self.run_cli("-", stdin="Fine.\n\nWe should utilize it.\n")
    self.assertEqual(p.returncode, 1)
    self.assertIn('line 3: "utilize": American spelling: use \'utilise\'', p.stdout)
    self.assertIn('line 3: "utilize": on the avoid list', p.stdout)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
      f.write("The colour of it.\n")
    try:
      self.assertEqual(self.run_cli(f.name).returncode, 0)
      p = self.run_cli("--register", "book", f.name)
      self.assertEqual(p.returncode, 1)
      self.assertIn('"colour"', p.stdout)
    finally:
      os.unlink(f.name)

  def test_usage_errors_exit_2(self):
    self.assertEqual(self.run_cli(stdin="  \n").returncode, 2)
    self.assertEqual(self.run_cli("/no/such/draft.md").returncode, 2)
    self.assertEqual(self.run_cli("--register", "tabloid", stdin="x").returncode, 2)


if __name__ == "__main__":
  unittest.main()
