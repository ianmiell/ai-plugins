#!/usr/bin/env python3
"""Send a macOS notification (Notification Centre) safely, and print the text it sent.

  pa-notify.py --title "Comms ready" "Mon 02 Nov: 3 act now. Top: reply to Jane O'Donovan"
  pa-notify.py --title "Interview prep" --sound Glass <<'EOF'
  09:30 Jane Doe (hiring), 15:00 Thomas Reilly (technical)
  EOF
  pa-notify.py --title "Comms ready" --dry-run "**3** act now"   # prints, sends nothing

The message (the arguments, or stdin when there are none) is collapsed to one line, its
markdown stripped (bold, code, headings, list markers, [links](url) become their text), double
quotes turned into single ones, and cut to 200 characters with an ellipsis. The title gets the
same treatment, cut to 60. The cleaned message is printed on stdout, so a skill can reuse the
very same text for PushNotification.

The text goes to osascript as arguments, never inside the AppleScript, so an apostrophe
(O'Donovan) or a quote can't break it. --sound NAME picks the sound (Glass by default),
--silent leaves it out. --dry-run, or PA_NO_NOTIFY=1 (the tests), prints without notifying.

Exits 0 when the notification went (or wasn't meant to), 1 if osascript failed (the message is
still printed), 2 on bad usage. Off macOS it prints and exits 0.
"""

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys

MAX_MESSAGE = 200
MAX_TITLE = 60


def clean(text, width):
  """One line of plain text, at most width characters."""
  text = text or ""
  text = re.sub(r"```.*?```", " ", text, flags=re.S)
  text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)      # [text](url) and images
  text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.M)     # headings
  text = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", text, flags=re.M)  # list markers
  text = re.sub(r"^\s*>\s?", "", text, flags=re.M)              # quotes
  text = re.sub(r"(\*\*|__|~~|`)", "", text)
  text = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])", r"\1", text)  # *italic*
  text = re.sub(r"(?<!\w)_(?=\S)([^_\n]+?)(?<=\S)_(?!\w)", r"\1", text)          # _italic_
  text = text.replace('"', "'").replace("“", "'").replace("”", "'")
  text = " ".join(text.split())
  if len(text) > width:
    text = text[:width - 1].rstrip() + "…"
  return text


APPLESCRIPT_SOUND = ["-e", "on run argv",
                     "-e", "display notification (item 1 of argv) with title (item 2 of argv) "
                           "sound name (item 3 of argv)",
                     "-e", "end run"]
APPLESCRIPT_SILENT = ["-e", "on run argv",
                      "-e", "display notification (item 1 of argv) with title (item 2 of argv)",
                      "-e", "end run"]


def osascript_cmd(message, title, sound):
  if sound:
    return ["osascript", *APPLESCRIPT_SOUND, message, title, sound]
  return ["osascript", *APPLESCRIPT_SILENT, message, title]


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("--title", required=True)
  ap.add_argument("--sound", default="Glass", help="sound name (Glass)")
  ap.add_argument("--silent", action="store_true", help="no sound")
  ap.add_argument("--dry-run", action="store_true", help="print the text, send nothing")
  ap.add_argument("message", nargs="*", help="the message (default: stdin)")
  args = ap.parse_args()

  raw = " ".join(args.message) if args.message else ("" if sys.stdin.isatty() else sys.stdin.read())
  message = clean(raw, MAX_MESSAGE)
  title = clean(args.title, MAX_TITLE)
  if not message:
    print("pa-notify: no message (give it as arguments or on stdin)", file=sys.stderr)
    return 2
  sound = None if args.silent else clean(args.sound, 40) or None
  print(message)

  if args.dry_run or os.environ.get("PA_NO_NOTIFY"):
    why = "--dry-run" if args.dry_run else "PA_NO_NOTIFY is set"
    print(f"not sent ({why}): title '{title}', sound {sound or 'none'}", file=sys.stderr)
    return 0
  if platform.system() != "Darwin" or not shutil.which("osascript"):
    print("pa-notify: not on macOS, so no notification", file=sys.stderr)
    return 0
  try:
    p = subprocess.run(osascript_cmd(message, title, sound), capture_output=True, text=True, timeout=30,
                       stdin=subprocess.DEVNULL)
  except (OSError, subprocess.TimeoutExpired) as e:
    print(f"pa-notify: osascript failed: {e}", file=sys.stderr)
    return 1
  if p.returncode != 0:
    print(f"pa-notify: osascript failed: {(p.stderr or p.stdout).strip()}", file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  sys.exit(main())
