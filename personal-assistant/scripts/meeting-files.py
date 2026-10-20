#!/usr/bin/env python3
"""The file steps of the meeting skill: find, name, move, check and tidy recordings.

  meeting-files.py pending                     # step 1: what's waiting, and which path
  meeting-files.py plan STEM "Event title"     # step 3: before -> after names (changes nothing)
  meeting-files.py apply STEM "Event title"    # step 4, after Ian's yes
  meeting-files.py mkv STEM NEW_STEM [--delete]  # step 5: the three checks, then rm the .mkv
  meeting-files.py wait NEW_STEM [--add]       # step 5: wait for Whisper's transcript
  meeting-files.py dedupe NEW_STEM             # step 4: Whisper's "<new stem> (1).txt"

The title becomes the description exactly as rename_files_with_calendar.sh does it
(`tr ' ' '_' | LC_ALL=C tr -cd '[:alnum:]_'`). Use `-` as the title for
`no_calendar_match`, or `--name DESCRIPTION` to give the description as is.

Recording path (INBOX/<stem>.mp4 exists): one move, INBOX/<stem>.mp4 -> MEETINGS/<new>.mp4.
Transcript path (MEETINGS/<stem>.txt exists): every MEETINGS/<stem>.* but the .mkv is renamed,
replacing only the leading stem; tracked files with `git mv`, untracked .txt/.aisummary with
mv + `git add`, the .mp4 with mv; then `bin/gtd push`.
Nothing is ever overwritten: if a target exists, it stops before moving anything.

INBOX is ~/Movies/meetings-inbox and MEETINGS is ~/git/gtd/meetings (MEETINGS_INBOX and
GTD_DIR override them).
"""

import argparse
import filecmp
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

INBOX = os.path.expanduser(os.environ.get("MEETINGS_INBOX", "~/Movies/meetings-inbox"))
MEETINGS = os.path.join(pa.GTD, "meetings")
STEM_RE = re.compile(r"\d{8}_\d{4}")
STABLE = 60


def describe(title):
  if title == "-":
    return "no_calendar_match"
  return "".join(c for c in title.replace(" ", "_") if c == "_" or (c.isascii() and c.isalnum()))


def age(path):
  return time.time() - os.stat(path).st_mtime


def size(path):
  try:
    return os.path.getsize(path)
  except OSError:
    return None


def human(n):
  if n is None:
    return "missing"
  for unit in ("B", "KB", "MB", "GB"):
    if n < 1024 or unit == "GB":
      return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
    n /= 1024


def ls(d):
  try:
    return sorted(os.listdir(d))
  except OSError:
    return []


def which_path(stem):
  if os.path.exists(os.path.join(INBOX, f"{stem}.mp4")):
    return "recording"
  if os.path.exists(os.path.join(MEETINGS, f"{stem}.txt")):
    return "transcript"
  return None


def cmd_pending(args):
  recs = [f[:-4] for f in ls(INBOX) if re.fullmatch(STEM_RE.pattern + r"\.mp4", f)]
  bare = [f[:-4] for f in ls(MEETINGS) if re.fullmatch(STEM_RE.pattern + r"\.txt", f)]
  names = set(ls(MEETINGS))
  orphans = [f[:-4] for f in ls(MEETINGS) if f.endswith(".mp4") and f"{f[:-4]}.txt" not in names
             and not os.path.exists(os.path.join(MEETINGS, f"{f[:-4]}.mkv"))]
  if not recs and not bare:
    print("nothing to process")
  for stem in sorted(recs):
    mp4, mkv = os.path.join(INBOX, f"{stem}.mp4"), os.path.join(INBOX, f"{stem}.mkv")
    note = "" if age(mp4) >= STABLE else f" — changed {age(mp4):.0f}s ago, OBS may still be remuxing"
    if not size(mp4):
      note = " — .mp4 is empty"
    print(f"{stem} recording: {stem}.mp4 {human(size(mp4))}, {stem}.mkv {human(size(mkv))}{note}")
  for stem in sorted(bare):
    files = [f for f in ls(MEETINGS) if f.startswith(stem + ".")]
    print(f"{stem} transcript: " + ", ".join(f"{f} {human(size(os.path.join(MEETINGS, f)))}" for f in files))
  if orphans and not recs and not bare:
    print("waiting for a transcript: " + ", ".join(sorted(orphans)[-10:]))


def plan_moves(stem, desc):
  new = f"{stem}_{desc}"
  path = which_path(stem)
  if path == "recording":
    moves = [(os.path.join(INBOX, f"{stem}.mp4"), os.path.join(MEETINGS, f"{new}.mp4"))]
    clash = [p for p in (os.path.join(MEETINGS, f"{new}.mp4"), os.path.join(MEETINGS, f"{new}.txt"))
             if os.path.exists(p)]
  elif path == "transcript":
    moves = [(os.path.join(MEETINGS, f), os.path.join(MEETINGS, new + f[len(stem):]))
             for f in ls(MEETINGS) if f.startswith(stem + ".") and not f.endswith(".mkv")]
    clash = [dst for _, dst in moves if os.path.exists(dst)]
  else:
    pa.die(f"no {INBOX}/{stem}.mp4 and no {MEETINGS}/{stem}.txt: nothing to name "
           "(already named, or the server renamed it?)")
  return path, new, moves, clash


def get_desc(args):
  desc = args.name if args.name else describe(args.title or "")
  if not desc:
    pa.die("the title has no letters or digits left: give --name, or - for no_calendar_match", 2)
  return desc


def cmd_plan(args):
  path, new, moves, clash = plan_moves(args.stem, get_desc(args))
  print(f"{args.stem}: {path} path, new stem {new}")
  for src, dst in moves:
    print(f"  {os.path.relpath(src, os.path.dirname(MEETINGS)) if src.startswith(pa.GTD) else src}"
          f" -> {os.path.relpath(dst, os.path.dirname(MEETINGS))}")
  for c in clash:
    print(f"  STOP: {c} already exists")
  sys.exit(1 if clash else 0)


def git(*a):
  return subprocess.run(["git", "-C", MEETINGS, *a], capture_output=True, text=True)


def cmd_apply(args):
  path, new, moves, clash = plan_moves(args.stem, get_desc(args))
  if clash:
    pa.die("not moving anything; these exist: " + ", ".join(clash))
  for src, dst in moves:
    name = os.path.basename(src)
    if path == "recording" or name.endswith(".mp4"):
      os.rename(src, dst) if not os.path.exists(dst) else pa.die(f"{dst} appeared; stopped")
      how = "mv"
    elif git("ls-files", "--error-unmatch", "--", name).returncode == 0:
      r = git("mv", "--", name, os.path.basename(dst))
      if r.returncode:
        pa.die(f"git mv {name}: {r.stderr.strip()}")
      how = "git mv"
    else:
      os.rename(src, dst) if not os.path.exists(dst) else pa.die(f"{dst} appeared; stopped")
      git("add", "--", os.path.basename(dst))
      how = "mv + git add"
    print(f"{how}: {name} -> {os.path.relpath(dst, os.path.dirname(MEETINGS))}")
  if path == "transcript":
    code, out, err = pa.gtd_cmd("push")
    print("gtd push: " + ("ok" if code == 0 else (out + err).strip()))
    print("expect Whisper to write a duplicate '<new> (1).txt' soon: run `dedupe` before the report")
  print(f"new stem: {new}")


def duration(path):
  r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                     capture_output=True, text=True)
  try:
    return float(r.stdout.strip())
  except ValueError:
    return None


def cmd_mkv(args):
  rec = os.path.exists(os.path.join(INBOX, f"{args.stem}.mkv"))
  mkv = os.path.join(INBOX if rec else MEETINGS, f"{args.stem}.mkv")
  mp4 = os.path.join(MEETINGS, f"{args.new_stem}.mp4")
  if not os.path.exists(mkv):
    print(f"no {args.stem}.mkv to delete")
    return
  checks = []
  checks.append(("renamed .mp4 exists and isn't empty", bool(size(mp4)), human(size(mp4))))
  dm, d4 = duration(mkv), (duration(mp4) if size(mp4) else None)
  ok = dm is not None and d4 is not None and abs(dm - d4) <= 1
  checks.append(("durations match within 1s", ok, f".mkv {dm}s, .mp4 {d4}s"))
  ages = [age(p) for p in (mkv, mp4) if os.path.exists(p)]
  checks.append(("neither changed in the last 60s", bool(ages) and min(ages) >= STABLE,
                 ", ".join(f"{a:.0f}s ago" for a in ages)))
  for what, good, detail in checks:
    print(f"{'pass' if good else 'FAIL'}  {what} ({detail})")
  if all(g for _, g, _ in checks):
    if args.delete:
      os.remove(mkv)
      print(f"deleted {mkv}")
    else:
      print("all checks pass: rerun with --delete to remove it")
  else:
    print(f"kept {mkv}")
    if not size(mp4):
      print(f"no .mp4: remux with `ffmpeg -i {mkv} -c copy {mp4}`, then rerun")
    sys.exit(1)


def cmd_wait(args):
  f = os.path.join(MEETINGS, f"{args.new_stem}.txt")
  deadline = time.time() + args.timeout
  while time.time() < deadline:
    if size(f):
      a = size(f)
      time.sleep(args.interval)
      if size(f) == a:
        print(f"ready: {f} ({human(a)})")
        if args.add:
          git("add", "--", os.path.basename(f))
          code, out, err = pa.gtd_cmd("push")
          print("git add + gtd push: " + ("ok" if code == 0 else (out + err).strip()))
        return
    else:
      time.sleep(args.interval)
  print(f"no transcript after {args.timeout // 60} minutes: is Whisper Transcription running, "
        f"with its Watch Folder on {MEETINGS}?")
  sys.exit(1)


def cmd_dedupe(args):
  orig = os.path.join(MEETINGS, f"{args.new_stem}.txt")
  dup = os.path.join(MEETINGS, f"{args.new_stem} (1).txt")
  if not os.path.exists(dup):
    print("no duplicate transcript")
    return
  if os.path.exists(orig) and filecmp.cmp(orig, dup, shallow=False):
    os.remove(dup)
    print(f"deleted {os.path.basename(dup)} (identical to {os.path.basename(orig)})")
  else:
    print(f"{os.path.basename(dup)} differs from {os.path.basename(orig)}: "
          f"{human(size(dup))} vs {human(size(orig))}; ask Ian")
    sys.exit(1)


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  sub.add_parser("pending")
  for name in ("plan", "apply"):
    p = sub.add_parser(name)
    p.add_argument("stem")
    p.add_argument("title", nargs="?")
    p.add_argument("--name", help="the description as is, in place of a title")
  p = sub.add_parser("mkv")
  p.add_argument("stem")
  p.add_argument("new_stem")
  p.add_argument("--delete", action="store_true")
  p = sub.add_parser("wait")
  p.add_argument("new_stem")
  p.add_argument("--add", action="store_true", help="git add the transcript and gtd push when ready")
  p.add_argument("--timeout", type=int, default=1800)
  p.add_argument("--interval", type=int, default=10)
  p = sub.add_parser("dedupe")
  p.add_argument("new_stem")
  args = ap.parse_args()
  if getattr(args, "stem", None) and not STEM_RE.fullmatch(args.stem):
    pa.die(f"{args.stem!r} isn't a bare YYYYMMDD_HHMM stem", 2)
  {"pending": cmd_pending, "plan": cmd_plan, "apply": cmd_apply, "mkv": cmd_mkv,
   "wait": cmd_wait, "dedupe": cmd_dedupe}[args.cmd](args)


if __name__ == "__main__":
  main()
