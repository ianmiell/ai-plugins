#!/usr/bin/env python3
"""A stand-in for gog in the tests: a few gmail commands over a JSON state file.

FAKE_GOG_STATE is the state ({"accounts": {address: {"labels": [...], "threads": {...}}}}),
rewritten after every change; FAKE_GOG_LOG gets one JSON line per call. Threads are Gmail API
threads ({"messages": [{"id", "labelIds", "internalDate", "snippet", "payload"}]}).
"""

import fcntl
import json
import os
import sys

STATE = os.environ["FAKE_GOG_STATE"]
LOG = os.environ.get("FAKE_GOG_LOG")


def fail(msg, code=1):
  print(msg, file=sys.stderr)
  sys.exit(code)


def main():
  argv = sys.argv[1:]
  if LOG:
    with open(LOG, "a") as f:
      f.write(json.dumps(argv) + "\n")
  if "--gmail-no-send" not in argv:
    fail("fake gog: called without --gmail-no-send", 3)
  account = argv[argv.index("-a") + 1]
  rest = [a for i, a in enumerate(argv) if a not in ("--gmail-no-send", "--no-input", "--json", "--results-only")
          and not (i > 0 and argv[i - 1] == "-a") and a != "-a"]
  # mail-gather reads several threads at once: one call at a time over the state file.
  lock = open(STATE + ".lock", "w")
  fcntl.flock(lock, fcntl.LOCK_EX)
  with open(STATE) as f:
    state = json.load(f)
  box = state["accounts"].get(account)
  if box is None:
    fail(f"fake gog: no account {account}")
  assert rest[0] == "gmail", rest
  cmd, args = rest[1], rest[2:]
  out = None
  by_name = {l["name"]: l["id"] for l in box["labels"]}

  def lid(x):
    if x in by_name:
      return by_name[x]
    if any(l["id"] == x for l in box["labels"]):
      return x
    fail(f"fake gog: no label {x}")

  def thread_labels(t):
    s = set()
    for m in t["messages"]:
      s.update(m["labelIds"])
    return s

  if cmd == "search":
    max_n = int(args[args.index("--max") + 1]) if "--max" in args else 10
    query = args[args.index("--") + 1] if "--" in args else args[0]
    res = []
    for tid, t in box["threads"].items():
      labs, ok = thread_labels(t), True
      for term in query.split():
        neg = term.startswith("-")
        term = term.lstrip("-")
        if term == "in:inbox":
          hit = "INBOX" in labs
        elif term == "in:sent":
          hit = "SENT" in labs
        elif term == "is:starred":
          hit = "STARRED" in labs
        elif term.startswith("label:"):
          hit = by_name.get(term[6:]) in labs
        else:
          hit = True
        ok &= hit != neg
      if ok:
        h = {x.get("name"): x.get("value", "") for x in t["messages"][0]["payload"]["headers"]}
        res.append({"id": tid, "from": h.get("From"), "subject": h.get("Subject"), "labels": sorted(labs)})
    out = res[:max_n]
  elif cmd == "thread" and args[0] == "get":
    t = box["threads"].get(args[1]) or fail(f"fake gog: no thread {args[1]}")
    out = {"thread": dict(t, id=args[1]), "downloaded": None}
  elif cmd == "thread" and args[0] == "modify":
    t = box["threads"].get(args[1]) or fail(f"fake gog: no thread {args[1]}")
    add = args[args.index("--add") + 1].split(",") if "--add" in args else []
    rem = args[args.index("--remove") + 1].split(",") if "--remove" in args else []
    add, rem = [lid(x) for x in add], [lid(x) for x in rem]
    for m in t["messages"]:
      m["labelIds"] = [x for x in m["labelIds"] if x not in rem] + [x for x in add if x not in m["labelIds"]]
    out = {"id": args[1]}
  elif cmd == "labels" and args[0] == "list":
    out = box["labels"]
  elif cmd == "labels" and args[0] == "create":
    if args[1] in by_name:
      fail("fake gog: label exists")
    new = {"id": f"Label_{len(box['labels']) + 100}", "name": args[1], "type": "user"}
    box["labels"].append(new)
    out = new
  elif cmd == "labels" and args[0] == "delete":
    target = lid(args[1])
    box["labels"] = [l for l in box["labels"] if l["id"] != target]
    for t in box["threads"].values():
      for m in t["messages"]:
        m["labelIds"] = [x for x in m["labelIds"] if x != target]
    out = {"deleted": target}
  elif cmd == "url":
    out = [{"id": a, "url": f"https://mail.google.com/mail/?authuser={account.replace('@', '%40')}#all/{a}"}
           for a in args]
  elif cmd == "trash":
    for t in box["threads"].values():
      for m in t["messages"]:
        if m["id"] in args:
          m["labelIds"] = [x for x in m["labelIds"] if x != "INBOX"] + ["TRASH"]
    out = {"trashed": args}
  else:
    fail(f"fake gog: unsupported {rest}", 2)
  with open(STATE, "w") as f:
    json.dump(state, f)
  print(json.dumps(out))


if __name__ == "__main__":
  main()
