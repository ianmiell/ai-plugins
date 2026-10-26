#!/usr/bin/env python3
"""A stand-in for gog in the tests: the read-only drive and sheets calls the scripts make.

FAKE_GOG_STATE is a JSON file:
  {"drives": [{"id", "name"}],
   "inventories": {parentId: [gog inventory items]},
   "files": {fileId: file metadata},          for `drive get`
   "sheets": {sheetId: {tab: {"values": [[...]], "links": [{row, col, value, link}]}}}}
FAKE_GOG_LOG gets one JSON line per call.
"""

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
  if "--readonly" not in argv:
    fail("fake gog: called without --readonly", 3)
  rest = [a for i, a in enumerate(argv) if a not in ("--readonly", "--no-input", "--json", "-a")
          and not (i > 0 and argv[i - 1] == "-a")]
  with open(STATE) as f:
    state = json.load(f)
  cmd = rest[:2]
  out = None
  if cmd == ["drive", "drives"]:
    out = {"count": len(state["drives"]), "drives": state["drives"], "has_more": False}
  elif cmd == ["drive", "inventory"]:
    parent = rest[rest.index("--parent") + 1]
    out = {"items": state["inventories"].get(parent, [])}
  elif cmd == ["drive", "get"]:
    f = state.get("files", {}).get(rest[2])
    if f is None:
      fail("Error 404: File not found: " + rest[2])
    out = {"file": f}
  elif cmd == ["sheets", "metadata"]:
    tabs = state["sheets"][rest[2]]
    out = {"sheets": [{"properties": {"title": t}} for t in tabs]}
  elif cmd == ["sheets", "get"]:
    tab = rest[3].strip("'")
    out = {"range": tab, "values": state["sheets"][rest[2]][tab]["values"]}
  elif rest[:3] == ["sheets", "links", "get"]:
    tab = rest[4].strip("'")
    out = {"links": [dict(l, sheet=tab) for l in state["sheets"][rest[3]][tab].get("links", [])]}
  else:
    fail(f"fake gog: no command {rest}")
  print(json.dumps(out))


if __name__ == "__main__":
  main()
