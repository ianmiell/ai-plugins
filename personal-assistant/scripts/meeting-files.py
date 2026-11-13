#!/usr/bin/env python3
"""The file steps of the meeting skill: find, name, move, check and tidy recordings.

  meeting-files.py pending                     # step 1: what's waiting, and which path
  meeting-files.py status STEM                 # step 1: one stem's files in INBOX and MEETINGS (alias ls)
  meeting-files.py plan STEM "Event title"     # step 3: before -> after names (changes nothing)
  meeting-files.py apply STEM "Event title"    # step 4, after Ian's yes
  meeting-files.py mkv STEM NEW_STEM [--delete]  # step 5: the three checks, then rm the .mkv
  meeting-files.py wait NEW_STEM [--add]       # step 5: wait for Whisper's transcript
  meeting-files.py dedupe NEW_STEM             # step 4: Whisper's "<new stem> (1).txt"
  meeting-files.py whisper [--start]           # step 4: is Whisper Transcription running? start it
  meeting-files.py summary NEW_STEM [--force] < summary.md  # step 6: save, git add, gtd push

`status` takes a bare stem or a named one (20261016_1530_Some_Title) and lists every file in
INBOX and MEETINGS whose name starts with it (.mkv, .mp4, .txt, .aisummary, Whisper's
"(1)" duplicates), with sizes and ages, then which path applies. It never globs, so a
missing folder or file is just "none" (zsh aborts a whole `ls` when one glob matches nothing).

`summary` writes stdin to MEETINGS/<new stem>.txt.claude.aisummary, next to the transcript,
then `git add` and `bin/gtd push`. It refuses to replace an existing summary without --force.

`whisper` exits 0 and prints `running` if Whisper Transcription is running; with --start it
starts it (`open -a`) and waits up to 20 seconds for it. `wait --whisper` gives up at once if
Whisper isn't running, instead of waiting 30 minutes for a transcript that never comes.

ffprobe (for `mkv`) is found with pa_common's tool() (or on PATH, /opt/homebrew/bin,
/usr/local/bin); PA_FFPROBE overrides it. Without it the duration check fails and the
.mkv is kept.

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
import shutil
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
WHISPER = os.environ.get("PA_WHISPER_PATTERN", "Whisper Transcription.app/Contents/MacOS")
WHISPER_APP = os.environ.get("PA_WHISPER_APP", "Whisper Transcription")


def find_tool(name):
  """The path of a command line tool, wherever Homebrew put it, or None. PA_<NAME> overrides it."""
  env = os.environ.get(f"PA_{name.upper()}")
  if env:
    return env if os.access(env, os.X_OK) else None
  if hasattr(pa, "tool"):
    try:
      found = pa.tool(name)
      if found:
        return found
    except (Exception, SystemExit):
      pass
  return shutil.which(name) or next((p for p in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}")
                                     if os.access(p, os.X_OK)), None)


def pretty(path):
  home = os.path.expanduser("~")
  return "~" + path[len(home):] if path == home or path.startswith(home + os.sep) else path


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


def cmd_status(args):
  stem = args.stem
  base = STEM_RE.match(stem).group(0)
  when = time.strptime(base, "%Y%m%d_%H%M")
  print(f"{stem} ({time.strftime('%a %d %b %Y, %H:%M', when)})")
  found = {}
  for label, d in (("INBOX", INBOX), ("MEETINGS", MEETINGS)):
    files = [f for f in ls(d) if f.startswith(stem)]
    found[label] = files
    print(f"{label} {pretty(d)}:" + ("" if files else " none" + ("" if os.path.isdir(d) else " (no such folder)")))
    for f in files:
      p = os.path.join(d, f)
      note = ""
      if re.search(r" \(\d+\)\.txt$", f):
        note = f"  <- Whisper duplicate: `dedupe {f.rsplit(' (', 1)[0]}`"
      elif f.endswith(".mp4") and not size(p):
        note = "  <- empty"
      elif f.endswith(".mp4") and age(p) < STABLE:
        note = "  <- changed in the last 60s: OBS may still be remuxing"
      print(f"  {f}  {human(size(p))}  changed {ago(age(p))}{note}")
  path = which_path(stem) if stem == base else None
  named = sorted({m.group(1) for f in found["MEETINGS"]
                  for m in [re.match(rf"({re.escape(base)}_[^. ]+)\.(txt|mp4)$", f)] if m})
  if path == "recording":
    print(f"path: recording (INBOX/{stem}.mp4)")
  elif path == "transcript":
    print(f"path: transcript (MEETINGS/{stem}.txt)")
  elif named:
    for new in named:
      has_txt = f"{new}.txt" in found["MEETINGS"]
      print(f"already named {new}: " + ("skip to step 6" if has_txt else "no transcript yet: `wait` (step 5)"))
  else:
    print("path: none (nothing to name: no INBOX .mp4 and no bare MEETINGS .txt)")


def ago(secs):
  if secs < 120:
    return f"{secs:.0f}s ago"
  if secs < 7200:
    return f"{secs / 60:.0f}m ago"
  if secs < 172800:
    return f"{secs / 3600:.0f}h ago"
  return f"{secs / 86400:.0f}d ago"


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


def duration(ffprobe, path):
  try:
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True, timeout=60)
    return float(r.stdout.strip())
  except (OSError, ValueError, subprocess.TimeoutExpired):
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
  ffprobe = find_tool("ffprobe")
  if not ffprobe:
    checks.append(("durations match within 1s", False,
                   "ffprobe not found on PATH, in /opt/homebrew/bin or /usr/local/bin: it comes with ffmpeg; "
                   "ask Ian, the .mkv stays until it can be checked"))
  else:
    dm, d4 = duration(ffprobe, mkv), (duration(ffprobe, mp4) if size(mp4) else None)
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
      print(f"no .mp4: remux with `{find_tool('ffmpeg') or 'ffmpeg'} -i {mkv} -c copy {mp4}`, then rerun")
    sys.exit(1)


def whisper_running():
  """True or False, or None when it can't tell (no pgrep)."""
  pgrep = find_tool("pgrep") or "/usr/bin/pgrep"
  try:
    code = subprocess.run([pgrep, "-f", WHISPER], capture_output=True, timeout=30).returncode
  except (OSError, subprocess.TimeoutExpired):
    return None
  return {0: True, 1: False}.get(code)


def cmd_whisper(args):
  now = whisper_running()
  if now is not False:
    print("running" if now else "can't tell (pgrep failed): check Whisper Transcription by hand")
    return
  if not args.start:
    print("not running: start it with `meeting-files.py whisper --start` before moving anything in")
    sys.exit(1)
  try:
    subprocess.run(["open", "-a", WHISPER_APP], capture_output=True, timeout=60)
  except (OSError, subprocess.TimeoutExpired) as e:
    print(f"not running, and `open -a {WHISPER_APP!r}` failed: {e}")
    sys.exit(1)
  for _ in range(20):
    if whisper_running():
      print("started: tell Ian")
      return
    time.sleep(1)
  print(f"not running, even after `open -a {WHISPER_APP!r}`: stop and ask Ian before moving anything")
  sys.exit(1)


def cmd_wait(args):
  f = os.path.join(MEETINGS, f"{args.new_stem}.txt")
  deadline = time.time() + args.timeout
  checked = 0
  while time.time() < deadline:
    if args.whisper and not size(f) and time.time() - checked >= 60:
      checked = time.time()
      if whisper_running() is False:
        print(f"Whisper Transcription isn't running, so no transcript will come: start it "
              f"(`meeting-files.py whisper --start`), then `open -a {WHISPER_APP!r} {os.path.join(MEETINGS, args.new_stem)}.mp4` "
              "and run `wait` again")
        sys.exit(1)
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


def cmd_summary(args):
  new = args.new_stem[:-4] if args.new_stem.endswith(".txt") else args.new_stem
  if "/" in new or not STEM_RE.match(new):
    pa.die(f"{args.new_stem!r} isn't a meeting stem (YYYYMMDD_HHMM_Title)", 2)
  text = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
  if not text:
    pa.die("the summary goes on stdin", 2)
  if not os.path.exists(os.path.join(MEETINGS, f"{new}.txt")):
    pa.die(f"no {pretty(MEETINGS)}/{new}.txt: give the transcript's stem (`status` lists the files)")
  name = f"{new}.txt.claude.aisummary"
  path = os.path.join(MEETINGS, name)
  if os.path.exists(path) and not args.force:
    pa.die(f"{pretty(path)} already exists: read it, and rerun with --force only if Ian wants it replaced")
  with open(path, "w", encoding="utf-8") as f:
    f.write(text + "\n")
  print(f"ok    wrote meetings/{name} ({human(size(path))})")
  r = git("add", "--", name)
  if r.returncode:
    print(f"FAIL  git add: {(r.stderr or r.stdout).strip()}")
    sys.exit(1)
  print("ok    git add")
  code, out, err = pa.gtd_cmd("push")
  print("ok    gtd push" if code == 0 else f"FAIL  gtd push: {(out + err).strip()}")
  sys.exit(0 if code == 0 else 1)


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="cmd", required=True)
  sub.add_parser("pending")
  p = sub.add_parser("status", aliases=["ls"], help="one stem's files in INBOX and MEETINGS")
  p.add_argument("stem", help="YYYYMMDD_HHMM, or a named stem")
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
  p.add_argument("--whisper", action="store_true", help="give up at once if Whisper Transcription isn't running")
  p = sub.add_parser("dedupe")
  p.add_argument("new_stem")
  p = sub.add_parser("whisper")
  p.add_argument("--start", action="store_true", help="start it if it isn't running")
  p = sub.add_parser("summary")
  p.add_argument("new_stem")
  p.add_argument("--force", action="store_true", help="replace an existing .claude.aisummary")
  args = ap.parse_args()
  if args.cmd in ("status", "ls"):
    if not STEM_RE.match(args.stem) or "/" in args.stem:
      pa.die(f"{args.stem!r} doesn't start with a YYYYMMDD_HHMM stem", 2)
  elif getattr(args, "stem", None) and not STEM_RE.fullmatch(args.stem):
    pa.die(f"{args.stem!r} isn't a bare YYYYMMDD_HHMM stem", 2)
  {"pending": cmd_pending, "status": cmd_status, "ls": cmd_status, "plan": cmd_plan, "apply": cmd_apply,
   "mkv": cmd_mkv, "wait": cmd_wait, "dedupe": cmd_dedupe, "whisper": cmd_whisper,
   "summary": cmd_summary}[args.cmd](args)


if __name__ == "__main__":
  main()
