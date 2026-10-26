#!/usr/bin/env python3
"""Cache a full listing of the CS shared drives, so the other scripts read files, not the API.

  drive-inventory.py refresh [--drive NAME ...] [--my-drive] [--max-age HOURS]
  drive-inventory.py status
  drive-inventory.py tree --drive NAME [--depth 2]
  drive-inventory.py find TEXT [--drive NAME ...]
  drive-inventory.py export [--out FILE]

`refresh` walks each shared drive in the config with `gog drive inventory` (read-only, the
work account) and writes one cache file per drive under ~/.claude/container-solutions/drive-cache.
Drives fetched less than --max-age hours ago (default 24) are skipped; --max-age 0 forces it.
Big drives take minutes. --my-drive also lists Ian's own My Drive, for work files that belong
in a shared drive.

`status` shows each drive's item count and age. `tree` shows a drive's folders with the number
of files under each, to learn how it's organized. `find` searches names in the cache. `export`
writes everything as TSV (drive, path, kind, modified, owner, id, url).
"""

import argparse
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_drive as cs  # noqa: E402


def url(item):
  k = cs.kind(item["mime"])
  base = {"doc": "https://docs.google.com/document/d/", "slides": "https://docs.google.com/presentation/d/",
          "sheet": "https://docs.google.com/spreadsheets/d/", "folder": "https://drive.google.com/drive/folders/"}
  return base.get(k, "https://drive.google.com/file/d/") + item["id"]


def normalize(raw, drive):
  path = raw.get("path") or raw.get("name") or ""
  full = f"{drive}/{path}"
  return {
    "id": raw["id"],
    "name": raw.get("name") or os.path.basename(path),
    "drive": drive,
    "path": full,
    "folder": os.path.dirname(full),
    "mime": raw.get("mimeType", ""),
    "modified": (raw.get("modifiedTime") or "")[:10],
    "owners": raw.get("owners") or [],
    "depth": raw.get("depth") or path.count("/") + 1,
  }


def drive_ids(cfg, names):
  """Shared drive name -> ID, from the local config, asking Drive for any not yet known."""
  known = dict(cfg.get("drive_ids") or {})
  if any(n not in known for n in names):
    for d in cs.listing(cs.gog("drive", "drives", "--all"), "drives"):
      known[d["name"]] = d["id"]
    cs.save_local_config({"drive_ids": {n: known[n] for n in cfg["drives"] if n in known}})
  missing = [n for n in names if n not in known]
  if missing:
    cs.die("no shared drive called " + ", ".join(missing) + " for " + cfg["account"]
           + ". Check the names in drive.json against `gog drive drives --all`.", 2)
  return known


def refresh(args):
  cfg = cs.config()
  names = args.drive or cfg["drives"]
  ids = drive_ids(cfg, [n for n in names if n != cs.MY_DRIVE])
  if args.my_drive and cs.MY_DRIVE not in names:
    names = names + [cs.MY_DRIVE]
  os.makedirs(cs.CACHE, exist_ok=True)
  for name in names:
    old = cs.load_cache(name)
    if old and args.max_age and time.time() - old["fetched"] < args.max_age * 3600:
      print(cs.line(name, len(old["items"]), "cached " + cs.age(old["fetched"]) + " ago"))
      continue
    t = time.time()
    if name == cs.MY_DRIVE:
      res = cs.gog("drive", "inventory", "--parent", "root", "--max", "0", "--no-all-drives")
    else:
      res = cs.gog("drive", "inventory", "--parent", ids[name], "--max", "0")
    items = [normalize(r, name) for r in cs.listing(res)]
    if isinstance(res, dict) and res.get("truncated"):
      print(f"warning: gog says the {name} listing was truncated", file=sys.stderr)
    tmp = cs.cache_file(name) + ".tmp"
    with open(tmp, "w") as f:
      json.dump({"drive": name, "id": ids.get(name, "root"), "fetched": time.time(), "items": items}, f)
    os.replace(tmp, cs.cache_file(name))
    print(cs.line(name, len(items), f"fetched in {time.time() - t:.0f}s"))


def status(args):
  cfg = cs.config()
  print("catalog: " + (cfg.get("catalog_id") or "NOT SET (drive.json catalog_id)"))
  for name in cfg["drives"] + [cs.MY_DRIVE]:
    c = cs.load_cache(name)
    if c:
      files = sum(1 for i in c["items"] if i["mime"] != cs.FOLDER)
      print(cs.line(name, f"{files} files", f"{len(c['items']) - files} folders", cs.age(c["fetched"]) + " old"))
    elif name != cs.MY_DRIVE:
      print(cs.line(name, "not fetched"))


def tree(args):
  items = cs.load_inventory([args.drive])
  under = collections.Counter()
  for i in items:
    if i["mime"] == cs.FOLDER:
      continue
    parts = i["folder"].split("/")
    for n in range(1, min(len(parts), args.depth + 1) + 1):
      under["/".join(parts[:n])] += 1
  folders = {i["path"] for i in items if i["mime"] == cs.FOLDER and i["depth"] <= args.depth}
  for p in sorted(folders | {k for k in under if k.count("/") <= args.depth}):
    print(cs.line(under.get(p, 0), p))


def find(args):
  text = args.text.lower()
  for i in cs.load_inventory(args.drive or None):
    if text in i["name"].lower():
      print(cs.line(cs.kind(i["mime"]), i["modified"], i["path"], i["id"]))


def export(args):
  out = args.out or os.path.join(cs.CACHE, "inventory.tsv")
  with open(out, "w") as f:
    f.write(cs.line("drive", "path", "kind", "modified", "owner", "id", "url") + "\n")
    for i in cs.load_inventory(need=False):
      f.write(cs.line(i["drive"], i["path"], cs.kind(i["mime"]), i["modified"], ",".join(i["owners"]), i["id"], url(i)) + "\n")
  print(out)


def main():
  ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  sub = ap.add_subparsers(dest="cmd", required=True)
  p = sub.add_parser("refresh")
  p.add_argument("--drive", action="append")
  p.add_argument("--my-drive", action="store_true")
  p.add_argument("--max-age", type=float, default=24)
  p.set_defaults(fn=refresh)
  sub.add_parser("status").set_defaults(fn=status)
  p = sub.add_parser("tree")
  p.add_argument("--drive", required=True)
  p.add_argument("--depth", type=int, default=2)
  p.set_defaults(fn=tree)
  p = sub.add_parser("find")
  p.add_argument("text")
  p.add_argument("--drive", action="append")
  p.set_defaults(fn=find)
  p = sub.add_parser("export")
  p.add_argument("--out")
  p.set_defaults(fn=export)
  args = ap.parse_args()
  try:
    args.fn(args)
  except cs.GogError as e:
    cs.die(str(e))


if __name__ == "__main__":
  main()
