#!/usr/bin/env python3
"""Make a Gmail draft reply (or forward) in Ian's voice, never sent: voice check, then gog.

  mail-draft.py personal 1a159da84468dd9d <<'EOF'
  Thanks Sam - Thursday works. I'll book the table.

  Ian
  EOF
  mail-draft.py work 1a15b0aad89c09a9 --reply-all < draft.txt
  mail-draft.py personal 1a159da84468dd9d --forward pat@acme.example <<'EOF'
  Pat - this one's yours, can you pick it up?
  EOF
  mail-draft.py work 1a15b0aad89c09a9 --dry-run < draft.txt      # checks, says what it would do

The text comes on stdin. First it runs voice-check.py --channel email on it: if anything is
flagged it prints the problems, makes no draft and exits 1 (--force makes the draft anyway,
only when Ian has said the flagged wording stays). Then, for a mailbox gog serves, it reads
the thread and makes the draft with `gog gmail drafts reply <messageId> --body ...`
(`drafts reply-all` with --reply-all, `drafts forward <messageId> --to ADDR --note ...` with
--forward), always with --gmail-no-send. It replies to the thread's latest message from
someone other than Ian (his own last message only when there is no other). It prints the
draft id, who it goes to, the subject and the text, for the report.

On the MacBook Pro the work mailbox is the Gmail connector's: there it only runs the voice
check and prints the create_draft arguments as JSON (with replyToMessageId when --message
is given: the latest message id from the connector's thread, not Ian's own), for the
connector call. Exits 0 when a draft was made (or would be), 1 when the voice check or gog
failed, 2 on bad usage.
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # no __pycache__ in the plugin from importing pa_common
import pa_common as pa  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def voice_check(text):
  """(ok, problems) from voice-check.py --channel email."""
  p = subprocess.run([sys.executable, os.path.join(HERE, "voice-check.py"), "--channel", "email"],
                     input=text, capture_output=True, text=True, timeout=60)
  if p.returncode == 2:
    pa.die(f"voice-check.py: {(p.stderr or p.stdout).strip()}", 2)
  return p.returncode == 0, (p.stdout + p.stderr).strip()


def reply_target(mailbox, thread):
  """The message to reply to (latest from someone else, else the latest), with its headers."""
  data = pa.gog(mailbox, "gmail", "thread", "get", thread)
  msgs = (data.get("thread", data) or {}).get("messages", [])
  if not msgs:
    raise pa.GogError(f"thread {thread} has no messages")
  others = [m for m in msgs if (pa.addresses(pa.headers(m).get("from")) or [""])[0] not in pa.IAN_ADDRESSES]
  m = (others or msgs)[-1]
  return m, pa.headers(m)


def draft_id(res):
  """The draft id from whatever gog printed."""
  if isinstance(res, dict):
    for k in ("draftId", "draft_id", "id"):
      if res.get(k):
        return res[k]
    for k in ("draft", "result"):
      if isinstance(res.get(k), dict):
        return draft_id(res[k])
  if isinstance(res, list) and res:
    return draft_id(res[0])
  return None


def re_subject(subject, prefix):
  s = (subject or "").strip()
  return s if s.lower().startswith(prefix.lower()) else f"{prefix} {s}".strip()


def main():
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("mailbox", choices=list(pa.MAILBOXES))
  ap.add_argument("thread")
  g = ap.add_mutually_exclusive_group()
  g.add_argument("--forward", metavar="ADDR", help="draft a forward to ADDR, the text as its note")
  g.add_argument("--reply-all", action="store_true", help="reply to everyone on the message")
  ap.add_argument("--message", help="connector only: the message id to reply to")
  ap.add_argument("--to", action="append", default=[], help="connector only: recipient (repeatable)")
  ap.add_argument("--subject", help="connector only: the thread's subject")
  ap.add_argument("--force", action="store_true", help="make the draft even when the voice check flags it")
  ap.add_argument("--dry-run", action="store_true")
  args = ap.parse_args()

  text = sys.stdin.read().strip()
  if not text:
    pa.die("no draft text on stdin", 2)
  ok, problems = voice_check(text)
  if not ok:
    print("voice check flagged the draft:")
    print(problems)
    if not args.force:
      print("no draft made: fix the text (or --force once Ian has said the wording stays)")
      sys.exit(1)
    print("--force: making it anyway")
  else:
    print("voice check: clean")

  if args.mailbox == "work" and pa.machine() == "macbook-pro":
    call = {"body": text}
    if args.forward:
      call["to"] = [args.forward]
      call["subject"] = re_subject(args.subject, "Fwd:")
    else:
      if args.to:
        call["to"] = args.to
      if args.subject:
        call["subject"] = re_subject(args.subject, "Re:")
      call["replyToMessageId"] = args.message or "<latest message id in the thread from get_thread>"
    print(f"work on the MacBook Pro goes through the Gmail connector: no gog draft made. "
          f"Call create_draft for thread {args.thread} with:")
    print(json.dumps(call, ensure_ascii=False, indent=1))
    return

  try:
    msg, h = reply_target(args.mailbox, args.thread)
    if args.forward:
      cmd = ["gmail", "drafts", "forward", msg["id"], "--to", args.forward, "--note", text]
      to, subject = args.forward, re_subject(h.get("subject"), "Fwd:")
    else:
      cmd = ["gmail", "drafts", "reply-all" if args.reply_all else "reply", msg["id"], "--body", text]
      to = h.get("reply-to") or h.get("from", "")
      if args.reply_all:
        to = ", ".join(x for x in (to, h.get("to", ""), h.get("cc", "")) if x)
      subject = re_subject(h.get("subject"), "Re:")
    res = pa.gog(args.mailbox, *cmd, dry_run=args.dry_run)
  except pa.GogError as e:
    print(f"FAILED: {e}")
    sys.exit(1)
  did = draft_id(res) if not args.dry_run else None
  what = "forward" if args.forward else ("reply-all" if args.reply_all else "reply")
  print(f"{'would make' if args.dry_run else 'draft ' + str(did or '?')} {what} in {args.mailbox} "
        f"thread {args.thread}, to message {msg['id']}")
  print(f"To: {pa.one_line(to, 200)}")
  print(f"Subject: {subject}")
  print()
  print(text)
  if not args.dry_run:
    print("\n(not sent: Ian sends it from Gmail's Drafts)")


if __name__ == "__main__":
  main()
