#!/usr/bin/env python3
"""Tests for meeting-files.py's status, summary, whisper and ffprobe handling.

  python3 -m unittest discover -s personal-assistant/tests -p 'test_meeting.py' -v

Made-up stems and titles in a temporary gtd repo and inbox (Base in test_scripts.py); nothing
starts Whisper or touches Ian's folders.
"""

import os
import shutil
import subprocess
import sys
import time
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_scripts import Base  # noqa: E402


class Meeting(Base):
  def setUp(self):
    super().setUp()
    self.inbox = self.env["MEETINGS_INBOX"]
    self.meetings = os.path.join(self.gtd, "meetings")
    os.makedirs(self.inbox)
    subprocess.run(["git", "init", "-q", self.gtd], check=True)
    # No real Whisper in the tests: a pattern nothing matches, unless a test starts a stand-in
    self.env["PA_WHISPER_PATTERN"] = f"pa-test-whisper-{uuid.uuid4().hex}"

  def touch(self, path, text="x", old=True):
    with open(path, "w") as f:
      f.write(text)
    if old:
      t = time.time() - 600
      os.utime(path, (t, t))

  def mf(self, *args, stdin="", check=None):
    return self.run_script("meeting-files.py", *args, stdin=stdin, check=check)

  def test_status_lists_both_folders_without_globs(self):
    m, i = (lambda f: os.path.join(self.meetings, f)), (lambda f: os.path.join(self.inbox, f))
    self.touch(i("20261015_1130.mkv"), "raw")
    self.touch(i("20261015_1130.mp4"), "video", old=False)
    self.touch(i("20261015_1200.mp4"), "other")
    out = self.mf("status", "20261015_1130", check=0).stdout
    self.assertIn("20261015_1130 (Thu 15 Oct 2026, 11:30)", out)
    self.assertIn("20261015_1130.mkv  3B", out)
    self.assertIn("OBS may still be remuxing", out)
    self.assertIn("MEETINGS", out)
    self.assertIn(": none", out)  # nothing in meetings/: no error, unlike a zsh glob
    self.assertNotIn("20261015_1200", out)
    self.assertTrue(out.rstrip().endswith("path: recording (INBOX/20261015_1130.mp4)"))

    # Named already, with Whisper's duplicate and both summaries; ls is the same command
    os.remove(i("20261015_1130.mp4"))
    for f in ("20261015_1130_Acme_kickoff.txt", "20261015_1130_Acme_kickoff (1).txt",
              "20261015_1130_Acme_kickoff.txt.gpt-5-nano.aisummary", "20261015_1130_Acme_kickoff.mp4"):
      self.touch(m(f), "words")
    out = self.mf("ls", "20261015_1130", check=0).stdout
    self.assertIn("20261015_1130_Acme_kickoff (1).txt  5B", out)
    self.assertIn("Whisper duplicate: `dedupe 20261015_1130_Acme_kickoff`", out)
    self.assertIn(".txt.gpt-5-nano.aisummary", out)
    self.assertIn("already named 20261015_1130_Acme_kickoff: skip to step 6", out)
    out = self.mf("status", "20261015_1130_Acme_kickoff", check=0).stdout
    self.assertIn("20261015_1130_Acme_kickoff.mp4", out)

    # A missing folder is "none", not a crash
    shutil.rmtree(self.inbox)
    out = self.mf("status", "20261016_0900", check=0).stdout
    self.assertIn("none (no such folder)", out)
    self.assertIn("path: none", out)
    self.mf("status", "not-a-stem", check=2)

  def test_summary_writes_adds_and_pushes(self):
    self.touch(os.path.join(self.meetings, "20261015_1130_Acme_kickoff.txt"), "Speaker 1: hello")
    p = self.mf("summary", "20261015_1130_Acme_kickoff", stdin="## Decisions\n- Ship it\n", check=0)
    path = os.path.join(self.meetings, "20261015_1130_Acme_kickoff.txt.claude.aisummary")
    with open(path) as f:
      self.assertEqual(f.read(), "## Decisions\n- Ship it\n")
    self.assertIn("ok    git add", p.stdout)
    self.assertIn("ok    gtd push", p.stdout)
    staged = subprocess.run(["git", "-C", self.gtd, "diff", "--cached", "--name-only"], capture_output=True,
                            text=True).stdout.split()
    self.assertIn("meetings/20261015_1130_Acme_kickoff.txt.claude.aisummary", staged)
    with open(os.path.join(self.gtd, "calls.log")) as f:
      self.assertIn("push", f.read())
    # Never replaced without --force
    p = self.mf("summary", "20261015_1130_Acme_kickoff", stdin="other\n", check=1)
    self.assertIn("already exists", p.stderr)
    with open(path) as f:
      self.assertIn("Ship it", f.read())
    self.mf("summary", "20261015_1130_Acme_kickoff.txt", "--force", stdin="Replaced\n", check=0)
    with open(path) as f:
      self.assertEqual(f.read(), "Replaced\n")
    # No transcript of that name, or nothing on stdin
    self.mf("summary", "20261015_1130_Other", stdin="x\n", check=1)
    self.mf("summary", "20261015_1130_Acme_kickoff", "--force", stdin="  \n", check=2)
    self.mf("summary", "../20261015_1130_Acme_kickoff", stdin="x\n", check=2)

  def test_mkv_without_ffprobe_keeps_the_mkv(self):
    mkv, mp4 = os.path.join(self.inbox, "20261015_1130.mkv"), os.path.join(self.meetings, "20261015_1130_X.mp4")
    self.touch(mkv, "raw")
    self.touch(mp4, "video")
    self.env["PA_FFPROBE"] = os.path.join(self.tmp, "no-such-ffprobe")
    p = self.mf("mkv", "20261015_1130", "20261015_1130_X", "--delete", check=1)
    self.assertIn("FAIL  durations match within 1s (ffprobe not found", p.stdout)
    self.assertIn("kept", p.stdout)
    self.assertNotIn("Traceback", p.stderr)
    self.assertTrue(os.path.exists(mkv))

  def test_mkv_with_a_fake_ffprobe(self):
    fake = os.path.join(self.tmp, "ffprobe")
    with open(fake, "w") as f:
      f.write("#!/bin/sh\necho 12.5\n")
    os.chmod(fake, 0o755)
    self.env["PA_FFPROBE"] = fake
    mkv, mp4 = os.path.join(self.inbox, "20261015_1130.mkv"), os.path.join(self.meetings, "20261015_1130_X.mp4")
    self.touch(mkv, "raw")
    self.touch(mp4, "video")
    out = self.mf("mkv", "20261015_1130", "20261015_1130_X", "--delete", check=0).stdout
    self.assertIn("pass  durations match within 1s (.mkv 12.5s, .mp4 12.5s)", out)
    self.assertFalse(os.path.exists(mkv))

  def test_whisper_check_and_wait(self):
    p = self.mf("whisper", check=1)
    self.assertIn("not running", p.stdout)
    # wait --whisper gives up at once when Whisper isn't running, rather than after 30 minutes
    start = time.time()
    p = self.mf("wait", "20261015_1130_X", "--whisper", "--interval", "1", "--timeout", "30", check=1)
    self.assertLess(time.time() - start, 10)
    self.assertIn("isn't running", p.stdout)
    stand_in = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", self.env["PA_WHISPER_PATTERN"]])
    try:
      self.assertEqual(self.mf("whisper", "--start", check=0).stdout, "running\n")
    finally:
      stand_in.kill()
      stand_in.wait()


if __name__ == "__main__":
  unittest.main()
