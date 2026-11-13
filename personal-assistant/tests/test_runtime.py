#!/usr/bin/env python3
"""Tests for how the personal-assistant scripts behave when the world misbehaves: tools missing
from PATH, gog hanging or logged out, WhatsApp not running, and the launchd wrappers and
installers.

  python3 -m unittest discover -s personal-assistant/tests -p 'test_runtime.py' -v

Nothing real is touched: HOME, GTD_DIR and PA_STATE point into a temporary folder, gog is
tests/fake_gog.py, and claude, launchctl, open, pbcopy, osascript, curl and caffeinate are
stubs at the front of PATH (and passed explicitly where a script takes the binary from a
variable, so a real one can't be picked up). The names are made up.
"""

import contextlib
import importlib.util
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_scripts import Base, HERE, SCRIPTS, PERSONAL, WORK, msg  # noqa: E402

SCRIPTS = os.path.abspath(SCRIPTS)


def write_exe(path, text):
  os.makedirs(os.path.dirname(path), exist_ok=True)
  with open(path, "w") as f:
    f.write(text)
  os.chmod(path, 0o755)


class Stubs(Base):
  """Base plus a folder of stub commands that log their arguments to calls.log."""

  def setUp(self):
    super().setUp()
    self.stubs = os.path.join(self.tmp, "stubs")
    self.calls = os.path.join(self.tmp, "calls.log")
    self.home = os.path.join(self.tmp, "home")
    os.makedirs(self.home)
    self.env.update(HOME=self.home, PA_NO_NOTIFY="1", PA_RETRY_WAIT="0")

  def stub(self, name, body="exit 0"):
    write_exe(os.path.join(self.stubs, name),
              f'#!/bin/bash\necho "{name} $*" >> "{self.calls}"\n{body}\n')
    return os.path.join(self.stubs, name)

  def stub_path(self):
    # The stubs first; the tool folders the scripts add are already on it, so they stay behind.
    return os.pathsep.join([self.stubs, "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin",
                            "/usr/sbin", "/sbin"])

  def called(self):
    try:
      with open(self.calls) as f:
        return f.read().splitlines()
    except OSError:
      return []


class PaCommonTools(Stubs):
  def py(self, code, **env):
    e = dict(self.env, **env)
    p = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {SCRIPTS!r})\n" + code],
                       capture_output=True, text=True, env=e, timeout=60)
    self.assertEqual(p.returncode, 0, p.stderr)
    return p.stdout

  def test_tool_dirs_go_on_path(self):
    write_exe(os.path.join(self.home, ".local", "bin", "pa-test-tool"), "#!/bin/sh\necho hi\n")
    out = self.py("import os, pa_common as pa\n"
                  "print(pa.tool('pa-test-tool'))\nprint(pa.tool('no-such-tool-anywhere'))\n"
                  "print(os.environ['PATH'])\n",
                  PATH="/usr/bin:/bin")
    found, missing, path = out.splitlines()
    self.assertEqual(found, os.path.join(self.home, ".local", "bin", "pa-test-tool"))
    self.assertEqual(missing, "None")
    dirs = path.split(os.pathsep)
    self.assertIn(os.path.join(self.home, ".local", "bin"), dirs)
    self.assertIn(os.path.join(self.gtd, "bin"), dirs)
    self.assertEqual(dirs[-2:], ["/usr/bin", "/bin"])
    # A subprocess finds the tool too, and dirs already on PATH keep their place.
    out = self.py("import subprocess, pa_common\nprint(subprocess.run(['pa-test-tool'], capture_output=True, "
                  "text=True).stdout.strip())", PATH=f"/usr/bin:{self.gtd}/bin:/bin")
    self.assertEqual(out.strip(), "hi")

  def test_gog_missing_or_hung_is_a_gog_error(self):
    code = ("import pa_common as pa\n"
            "try:\n  pa.gog('personal', 'gmail', 'labels', 'list', timeout=1)\n"
            "except pa.GogError as e:\n  print('GogError:', e)\n")
    out = self.py(code, PA_GOG=os.path.join(self.tmp, "no-gog"))
    self.assertIn("GogError: can't run gog", out)
    self.assertIn("brew install gogcli", out)
    hung = os.path.join(self.tmp, "hung-gog")
    write_exe(hung, "#!/bin/sh\nsleep 10\n")
    t = time.time()
    out = self.py(code, PA_GOG=hung)
    self.assertIn("GogError: -a ian.miell@gmail.com --gmail-no-send --no-input --json --results-only gmail labels list:", out)
    self.assertIn("no answer from gog after 1s", out)
    self.assertLess(time.time() - t, 8)


class PaEnvIsolation(Stubs):
  EXPIRED = 'oauth2: cannot fetch token: 400 Bad Request\nResponse: {"error": "invalid_grant"}'

  def setUp(self):
    super().setUp()
    t = lambda mid, frm, labels: {"messages": [msg(mid, frm, "x@y.example", "s", labels)]}
    self.threads = {PERSONAL: {"aaaaaaaaaaaaaaaa": t("m1", f"Ian <{PERSONAL}>", ["SENT"]),
                               "bbbbbbbbbbbbbbbb": t("m2", "a@x.example", ["INBOX"])},
                    WORK: {"cccccccccccccccc": t("m3", f"Ian <{WORK}>", ["SENT"]),
                           "dddddddddddddddd": t("m4", "b@x.example", ["INBOX"])}}
    self.set_mail(self.threads)
    self.env.update(PA_CHECK_TIMEOUT="1")

  def set_box(self, addr, **extra):
    with open(self.state_file) as f:
      state = json.load(f)
    state["accounts"][addr].update(extra)
    with open(self.state_file, "w") as f:
      json.dump(state, f)

  def test_hung_whatsapp_is_an_error_and_the_rest_still_run(self):
    tries = os.path.join(self.tmp, "wa-tries")
    hung = os.path.join(self.tmp, "whatsapp-hung.py")
    write_exe(hung, f"import time\nopen({tries!r}, 'a').write('x')\ntime.sleep(10)\n")
    self.env.update(PA_MACHINE="macbook-pro", PA_WHATSAPP=hung)
    t = time.time()
    p = self.run_script("pa-env.py", "check")
    self.assertEqual(p.returncode, 1, p.stderr)
    self.assertNotIn("Traceback", p.stderr)
    self.assertIn("whatsapp: error: no answer after 1s", p.stdout)
    self.assertIn("mail personal (ian.miell@gmail.com) via gog: account ok, write ok", p.stdout)
    self.assertIn("slack window: since", p.stdout)
    with open(tries) as f:
      self.assertEqual(f.read(), "xx")  # tried once more
    self.assertLess(time.time() - t, 20)

  def test_hung_gog_on_one_mailbox(self):
    self.set_box(WORK, sleep=10)
    p = self.run_script("pa-env.py", "check", "--only", "mail", "--only", "windows")
    self.assertEqual(p.returncode, 1)
    self.assertIn("mail work (ian.miell@container-solutions.com) via gog: account error: ", p.stdout)
    self.assertIn("no answer from gog after 1s", p.stdout)
    self.assertIn("mail personal (ian.miell@gmail.com) via gog: account ok, write ok", p.stdout)
    self.assertIn("whatsapp window:", p.stdout)

  def test_mailbox_narrows_the_check(self):
    self.set_box(WORK, sleep=10)  # would fail if it were checked
    p = self.run_script("pa-env.py", "check", "--only", "mail", "--mailbox", "personal", check=0)
    self.assertIn("mail personal (ian.miell@gmail.com) via gog: account ok, write ok", p.stdout)
    self.assertNotIn("mail work", p.stdout)

  def test_gog_missing(self):
    self.env["PA_GOG"] = os.path.join(self.tmp, "no-gog")
    p = self.run_script("pa-env.py", "check")
    self.assertEqual(p.returncode, 1)
    self.assertNotIn("Traceback", p.stderr)
    self.assertRegex(p.stdout, r"mail personal \(ian.miell@gmail.com\) via gog: account error: can't run gog")
    self.assertIn("whatsapp: off on this machine", p.stdout)

  def test_expired_login(self):
    self.set_box(PERSONAL, error=self.EXPIRED)
    fix = (f"auth expired: run gog auth add {PERSONAL} "
           "--services gmail,calendar,drive,sheets,docs,slides,contacts,people --force-consent")
    p = self.run_script("pa-env.py", "check", "--only", "mail")
    self.assertEqual(p.returncode, 1)
    self.assertIn(f"mail personal ({PERSONAL}) via gog: account {fix}, write -\n", p.stdout)
    self.assertIn(f"mail work ({WORK}) via gog: account ok, write ok", p.stdout)
    p = self.run_script("pa-env.py", "auth")
    self.assertEqual(p.returncode, 1)
    self.assertEqual(p.stdout, f"auth work ({WORK}): ok\nauth personal ({PERSONAL}): {fix}\n")
    p = self.run_script("pa-env.py", "auth", "--notify")
    self.assertIn(f"notified: gog login expired: Run gog auth add for {PERSONAL}", p.stdout)
    # Not a login problem: an error, with no notification about logins.
    self.set_box(PERSONAL, error="dial tcp: lookup gmail.googleapis.com: no such host")
    p = self.run_script("pa-env.py", "auth", "--notify")
    self.assertIn(f"auth personal ({PERSONAL}): error: dial tcp", p.stdout)
    self.assertIn("notified: gog check failed: personal: error: dial tcp", p.stdout)

  def test_auth_ok(self):
    p = self.run_script("pa-env.py", "auth", "--notify", check=0)
    self.assertNotIn("notified", p.stdout)
    out = json.loads(self.run_script("pa-env.py", "check", "--only", "auth", "--json", check=0).stdout)
    self.assertEqual([a["status"] for a in out["auth"]], ["ok", "ok"])


class PaNotify(Stubs):
  def test_cleaning(self):
    text = ("## Comms ready\n- **3** act now. Top: reply to [Jane O'Donovan](https://x.example) "
            "about the \"renewal\"\n- `code` and *more*")
    p = self.run_script("pa-notify.py", "--title", "Comms ready", text, check=0)
    self.assertEqual(p.stdout, "Comms ready 3 act now. Top: reply to Jane O'Donovan about the 'renewal' "
                               "code and more\n")
    p = self.run_script("pa-notify.py", "--title", "x", "--dry-run", stdin="word " * 100, check=0)
    line = p.stdout.rstrip("\n")
    self.assertEqual(len(line), 200)
    self.assertTrue(line.endswith("…"))
    self.run_script("pa-notify.py", "--title", "x", stdin="  \n", check=2)

  @unittest.skipUnless(platform.system() == "Darwin", "osascript is macOS only")
  def test_text_goes_to_osascript_as_arguments(self):
    self.stub("osascript", 'for a in "$@"; do echo "ARG:$a" >> "' + self.calls + '"; done')
    del self.env["PA_NO_NOTIFY"]
    self.env["PATH"] = self.stub_path()
    self.run_script("pa-notify.py", "--title", "Interview prep", "09:30 Siobhan O'Donovan (hiring)", check=0)
    args = [l[4:] for l in self.called() if l.startswith("ARG:")]
    self.assertEqual(args[-3:], ["09:30 Siobhan O'Donovan (hiring)", "Interview prep", "Glass"])
    self.assertIn("on run argv", args)
    self.assertFalse(any("O'Donovan" in a for a in args[:-3]))  # never inside the script


class WhatsAppDraft(Stubs):
  CHAT = {"id": 7, "name": "Jane Doe", "kind": "dm", "phone": "447700900123"}

  def setUp(self):
    super().setUp()
    spec = importlib.util.spec_from_file_location("whatsapp_under_test", os.path.join(SCRIPTS, "whatsapp.py"))
    self.wa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(self.wa)
    self.wa.DRAFT_RETRY_WAIT = 0
    self.clip = os.path.join(self.tmp, "clipboard")
    self.stub("pbcopy", f'cat > "{self.clip}"')
    self.old_path = os.environ["PATH"]
    os.environ["PATH"] = self.stub_path()

  def tearDown(self):
    os.environ["PATH"] = self.old_path
    super().tearDown()

  def draft(self, chat, text="see you at 6"):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
      self.wa.draft(None, chat, text, False)
    return out.getvalue()

  def test_whatsapp_not_running_falls_back_to_clipboard(self):
    self.stub("open", 'case "$1" in whatsapp:*) echo "LSOpenURLsWithRole() failed with error -600 '
                      '(procNotFound)" >&2; exit 1 ;; esac')
    out = self.draft(self.CHAT)
    self.assertIn("copied the draft to the clipboard (WhatsApp wouldn't open the chat:", out)
    self.assertIn("procNotFound", out)
    self.assertIn("open 'Jane Doe' in WhatsApp, paste and send", out)
    with open(self.clip) as f:
      self.assertEqual(f.read(), "see you at 6")
    opens = [c for c in self.called() if c.startswith("open")]
    self.assertEqual([c.split()[1] for c in opens], ["whatsapp://send?phone=447700900123&text=see%20you%20at%206",
                                                    "-a", "whatsapp://send?phone=447700900123&text=see%20you%20at%206",
                                                    "-a"])

  def test_second_try_after_starting_whatsapp(self):
    flag = os.path.join(self.tmp, "started")
    self.stub("open", f'case "$1" in -a) touch "{flag}" ;; whatsapp:*) [ -e "{flag}" ] || exit 1 ;; esac')
    out = self.draft(self.CHAT)
    self.assertIn("opened the chat with Jane Doe with the draft typed in", out)
    self.assertFalse(os.path.exists(self.clip))

  def test_group_and_app_missing(self):
    self.stub("open", "exit 1")
    out = self.draft(dict(self.CHAT, kind="group", phone=None, name="Book club"))
    self.assertIn("copied the draft to the clipboard (no direct link for a group): start WhatsApp, then open "
                  "'Book club'", out)


class VoiceCheckStdin(Base):
  def test_dash_is_stdin(self):
    p = self.run_script("voice-check.py", "--channel", "slack", "-", stdin="sounds good - thanks\n")
    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
    p = self.run_script("voice-check.py", "--channel", "email", "-", stdin="I will circle back\n")
    self.assertEqual(p.returncode, 1)
    self.assertIn("circle back", p.stdout)
    p = self.run_script("voice-check.py", "--channel", "email", os.path.join(self.tmp, "nope.txt"))
    self.assertEqual(p.returncode, 2)
    self.assertIn("can't read", p.stderr)


class Launchd(Stubs):
  """The wrappers and installers, with every outside command stubbed."""

  def setUp(self):
    super().setUp()
    self.claude = self.stub("claude", 'echo "cwd $PWD" >> "' + self.calls + '"')
    for name in ("caffeinate", "curl", "open"):
      self.stub(name)
    self.launchctl = self.stub("launchctl")
    if not shutil.which("plutil"):
      self.stub("plutil")
    self.env.update(PATH=self.stub_path(), CLAUDE_BIN=self.claude, LAUNCHCTL=self.launchctl,
                    AWAKE_FOR="0", NETWORK_WAIT="0", XDG_STATE_HOME=os.path.join(self.tmp, "xdg"),
                    MEETINGS_DIR=os.path.join(self.gtd, "meetings"), INBOX_DIR=os.path.join(self.tmp, "inbox"))
    self.dest = os.path.join(self.home, ".local", "share", "personal-assistant", "launchd")

  def sh(self, path, *args, **env):
    e = dict(self.env, **env)
    return subprocess.run(["/bin/bash", path, *args], capture_output=True, text=True, env=e, timeout=60)

  def test_all_scripts_parse(self):
    for name in sorted(os.listdir(SCRIPTS)):
      if name.endswith(".sh"):
        p = subprocess.run(["/bin/bash", "-n", os.path.join(SCRIPTS, name)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, name + p.stderr)

  def test_comms_morning_logs_and_starts(self):
    p = self.sh(os.path.join(SCRIPTS, "comms-morning.sh"))
    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
    first = p.stdout.splitlines()[0]
    self.assertRegex(first, r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d morning comms session started \(pid \d+")
    calls = self.called()
    self.assertIn("open -g -a Google Chrome", calls)
    start = next(c for c in calls if c.startswith("claude "))
    self.assertRegex(start, r"^claude --bg --chrome --name comms-\w{3}-\d\d-\w{3} /personal-assistant:comms morning$")
    self.assertIn(f"cwd {self.gtd}", calls)

  def test_preflight_says_what_is_missing(self):
    p = self.sh(os.path.join(SCRIPTS, "weekly-plan.sh"), CLAUDE_BIN=os.path.join(self.tmp, "no-claude"),
                GTD_DIR=os.path.join(self.tmp, "no-gtd"))
    self.assertEqual(p.returncode, 1)
    self.assertIn("weekly plan session started", p.stdout)
    self.assertIn("preflight: claude not found", p.stderr)
    self.assertIn(f"preflight: no gtd folder at {self.tmp}/no-gtd", p.stderr)
    self.assertNotIn("failed to start", p.stderr)
    self.assertFalse(any(c.startswith("claude") for c in self.called()))

  def test_claude_failure_is_logged(self):
    self.stub("claude", "exit 3")
    p = self.sh(os.path.join(SCRIPTS, "linkedin-sync.sh"), CLAUDE_BIN=os.path.join(self.stubs, "claude"))
    self.assertIn("linkedin-sync session started", p.stdout)
    self.assertIn("claude exited with 3: failed to start a background claude session", p.stderr)
    self.assertRegex("\n".join(self.called()), r"claude --bg --chrome --name linkedin-sync-\d\d-\w{3} ")

  def test_interview_morning(self):
    gog = self.stub("gog", r'printf "ID\tSTART\tEND\tSUMMARY\nx1\t09:30\t10:30\tInterview: Jane Doe\n"')
    p = self.sh(os.path.join(SCRIPTS, "interview-morning.sh"), DRY_RUN="1")
    self.assertEqual(p.returncode, 0, p.stderr)
    self.assertIn("interview check started", p.stdout)
    self.assertIn("09:30\tInterview: Jane Doe", p.stdout)
    self.assertIn("DRY_RUN: would start", p.stdout)
    self.assertTrue(any(c.startswith("gog --readonly") for c in self.called()))
    write_exe(gog, '#!/bin/bash\nprintf "ID\\tSTART\\tEND\\tSUMMARY\\nx1\\t09:30\\t10:30\\tStandup\\n"\n')
    p = self.sh(os.path.join(SCRIPTS, "interview-morning.sh"))
    self.assertIn("no interviews today", p.stdout)
    self.assertFalse(any(c.startswith("claude") for c in self.called()))

  def test_installers_copy_and_point_the_plist_there(self):
    p = self.sh(os.path.join(SCRIPTS, "install-comms-morning.sh"), "06:30")
    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
    plist_path = os.path.join(self.home, "Library", "LaunchAgents", "com.ianmiell.comms-morning.plist")
    with open(plist_path) as f:
      plist = f.read()
    self.assertIn(f"<string>{self.dest}/comms-morning.sh</string>", plist)
    self.assertIn("<key>Hour</key><integer>6</integer><key>Minute</key><integer>30</integer>", plist)
    self.assertIn(f"<string>{self.gtd}</string>", plist)
    self.assertNotRegex(plist.replace("__PLACEHOLDERS__", ""), r"__[A-Z_]+__")
    for name in ("comms-morning.sh", "launchd-common.sh"):
      self.assertTrue(os.access(os.path.join(self.dest, name), os.X_OK), name)
    self.assertEqual([c.split()[1] for c in self.called() if c.startswith("launchctl")], ["bootout", "bootstrap"])
    # The copy runs on its own, finding launchd-common.sh next to it.
    p = self.sh(os.path.join(self.dest, "comms-morning.sh"))
    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
    self.assertIn("morning comms session started", p.stdout)

    open(self.calls, "w").close()
    p = self.sh(os.path.join(SCRIPTS, "install-comms-morning.sh"), "25:00")
    self.assertEqual(p.returncode, 1)
    self.assertEqual(self.called(), [])  # a bad time leaves the agent alone
    p = self.sh(os.path.join(SCRIPTS, "install-comms-morning.sh"), "--uninstall")
    self.assertEqual(p.returncode, 0, p.stderr)
    self.assertFalse(os.path.exists(plist_path))

  def test_every_installer(self):
    os.makedirs(self.env["INBOX_DIR"])
    with open(os.path.join(self.env["INBOX_DIR"], "20261020_1000.mp4"), "w") as f:
      f.write("x")
    for script, label, copied in (
        ("install-interview-morning.sh", "interview-morning", ["interview-morning.sh", "launchd-common.sh"]),
        ("install-weekly-plan.sh", "weekly-plan", ["weekly-plan.sh", "launchd-common.sh"]),
        ("install-linkedin-sync.sh", "linkedin-sync", ["linkedin-sync.sh", "launchd-common.sh"]),
        ("install-meeting-watch.sh", "meeting-watch", ["meeting-watch.sh", "launchd-common.sh"]),
        ("install-obs-auto-record.sh", "obs-auto-record", ["obs-auto-record.py"])):
      p = self.sh(os.path.join(SCRIPTS, script))
      self.assertEqual(p.returncode, 0, script + p.stdout + p.stderr)
      with open(os.path.join(self.home, "Library", "LaunchAgents", f"com.ianmiell.{label}.plist")) as f:
        plist = f.read()
      self.assertIn(f"<string>{self.dest}/{copied[0]}</string>", plist, script)
      self.assertNotRegex(plist.replace("__PLACEHOLDERS__", ""), r"__[A-Z_]+__", script)
      for name in copied:
        self.assertTrue(os.path.exists(os.path.join(self.dest, name)), name)
    with open(os.path.join(self.env["XDG_STATE_HOME"], "personal-assistant", "meeting-seen")) as f:
      self.assertEqual(f.read(), "20261020_1000\n")


if __name__ == "__main__":
  unittest.main()
