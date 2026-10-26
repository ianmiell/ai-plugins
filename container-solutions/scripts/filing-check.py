#!/usr/bin/env python3
"""Flag files in the CS shared drives that look like they're in the wrong place.

  filing-check.py check [--signal NAME ...] [--drive NAME ...] [--limit 20] [--all]
  filing-check.py customers

Reads the cached inventory (drive-inventory.py refresh). Each flag is a lead for the skill to
judge, not a verdict. Signals:
  root        a file loose at the top of a shared drive, in no folder
  customer    a file named after a customer (a top-level folder of the customers drive) that
              sits outside the drives allowed for customer files, or in another customer's folder
  allhands    an all-hands recording outside the All Hands drive, or something in that drive
              that isn't an all-hands recording
  rule        a file whose name matches a rule in the config (contracts, invoices, proposals,
              webinars, runbooks...) in a drive the rule doesn't expect
  mydrive     a work file in Ian's My Drive that a rule or customer name puts in a shared drive
              (only if My Drive was fetched with refresh --my-drive)
  stray       "Copy of ..." and "Untitled ..." files
Files Ian has decided on (drive-decide.py, check "filing") are left out. Everything also goes
to drive-cache/filing-check.tsv.

`customers` prints the customer names the customer signal uses, so wrong ones can go in the
config's customers.not_customers.
"""

import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_drive as cs  # noqa: E402

SIGNALS = ("root", "customer", "allhands", "rule", "mydrive", "stray")
SUFFIX = re.compile(r"\s*(\(.*?\)|\b(ltd|limited|bv|b\.v\.|gmbh|ag|inc|plc|llc|sa|nv|group)\.?)\s*$", re.I)


def customers(cfg, inv):
  """{normalized name: folder path} for each customer folder in the customers drive."""
  c = cfg["customers"]
  skip = {n.lower() for n in c["not_customers"]}
  out = {}
  for i in inv:
    if i["drive"] != c["drive"] or i["mime"] != cs.FOLDER or i["depth"] != c["depth"]:
      continue
    name = SUFFIX.sub("", i["name"]).strip()
    n = cs.norm_title(name)
    if len(n) >= 4 and n not in skip:
      out[n] = i["path"]
  return out


def name_re(names):
  if not names:
    return None
  alts = sorted((re.escape(n).replace(r"\ ", r"[\s_.-]*") for n in names), key=len, reverse=True)
  return re.compile(r"(?<![a-z0-9])(" + "|".join(alts) + r")(?![a-z0-9])", re.I)


def check(args):
  cfg = cs.config()
  inv = cs.load_inventory(args.drive or None)
  decided = cs.load_decisions("filing")
  signals = args.signal or SIGNALS
  custs = customers(cfg, cs.load_inventory([cfg["customers"]["drive"]]))
  cust_re = name_re(custs)
  ok_drives = set(cfg["customers"]["ok_drives"])
  ah = cfg["all_hands"]
  ah_re, rec_re = re.compile(ah["pattern"]), re.compile(cfg["recording_pattern"])
  rules = [(r["label"], re.compile(r["pattern"]), set(r["expect"])) for r in cfg["rules"]]
  rows = []

  def emit(sig, i, why):
    rows.append((sig, i["path"], why, cs.kind(i["mime"]), i["modified"], i["id"]))

  def rule_hits(i):
    hits = [(label, expect) for label, r, expect in rules if r.search(i["name"])]
    if not hits:
      return None
    expect = set().union(*(e for _, e in hits))
    return " + ".join(l for l, _ in hits), expect

  for i in inv:
    if i["id"] in decided or i["mime"] in (cs.SHORTCUT,):
      continue
    folder = i["mime"] == cs.FOLDER
    mine = i["drive"] == cs.MY_DRIVE
    if "root" in signals and not folder and not mine and i["depth"] == 1:
      emit("root", i, "loose at the top of the drive")
    if "stray" in signals and not folder and re.match(r"(?i)(copy of |untitled)", i["name"]):
      emit("stray", i, "copy or untitled")
    if folder:
      continue
    cust = cust_re.findall(i["name"]) if cust_re else []
    cust = list(dict.fromkeys(cs.norm_title(SUFFIX.sub("", c)) for c in cust))
    cust = [c for c in cust if c in custs]
    if "customer" in signals and cust and not mine:
      if i["drive"] not in ok_drives:
        emit("customer", i, f"names {', '.join(cust)}; customer files go in {' or '.join(sorted(ok_drives))}")
      elif i["drive"] == cfg["customers"]["drive"]:
        home = next((c for c in cust if i["path"].startswith(custs[c] + "/")), None)
        inside = next((n for n, p in custs.items() if i["path"].startswith(p + "/")), None)
        if inside and not home:
          emit("customer", i, f"names {', '.join(cust)} but is in {custs[inside].split('/')[-1]}'s folder")
    is_rec = cs.kind(i["mime"]) == "video" or bool(rec_re.search(i["name"]))
    inner = i["path"].split("/", 1)[-1]  # the drive's own name would match the all-hands pattern
    if "allhands" in signals:
      if i["drive"] != ah["drive"] and is_rec and ah_re.search(inner):
        emit("allhands", i, f"all-hands recording outside {ah['drive']}")
      elif i["drive"] == ah["drive"] and not ah_re.search(inner) and not is_rec:
        emit("allhands", i, "in the all-hands drive but doesn't look like an all-hands recording")
    hit = rule_hits(i)
    if "rule" in signals and hit and not mine and i["drive"] not in hit[1]:
      emit("rule", i, f"{hit[0]}: expected in {' or '.join(sorted(hit[1]))}")
    if "mydrive" in signals and mine and (hit or cust):
      where = sorted(hit[1]) if hit else [cfg["customers"]["drive"]]
      why = (hit[0] if hit else "customer " + ", ".join(cust))
      emit("mydrive", i, f"{why}: belongs in {' or '.join(where)}")

  out = os.path.join(cs.CACHE, "filing-check.tsv")
  with open(out, "w") as f:
    f.write(cs.line("signal", "path", "why", "kind", "modified", "id") + "\n")
    for r in rows:
      f.write(cs.line(*r) + "\n")
  counts = collections.Counter(r[0] for r in rows)
  print(f"inventory: {len(inv)} items, {len(custs)} customers; flags: "
        + ", ".join(f"{counts[s]} {s}" for s in signals) + f"; full list: {out}")
  for sig in signals:
    rs = [r for r in rows if r[0] == sig]
    if not rs:
      continue
    print(f"\n[{sig}]")
    by_drive = collections.defaultdict(list)
    for r in rs:
      by_drive[r[1].split("/", 1)[0]].append(r)
    for drive, drs in sorted(by_drive.items(), key=lambda g: -len(g[1])):
      print(f"{drive}  ({len(drs)})")
      drs.sort(key=lambda r: r[4], reverse=True)
      for r in drs[: None if args.all else args.limit]:
        print("  " + cs.line(r[1].split("/", 1)[-1], r[2], r[3], r[4], r[5]))
      if not args.all and len(drs) > args.limit:
        print(f"  ... {len(drs) - args.limit} more")


def list_customers(args):
  cfg = cs.config()
  custs = customers(cfg, cs.load_inventory([cfg["customers"]["drive"]]))
  print(f"{len(custs)} customers from {cfg['customers']['drive']} folders at depth {cfg['customers']['depth']}")
  for n, p in sorted(custs.items()):
    print(cs.line(n, p))


def main():
  ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  sub = ap.add_subparsers(dest="cmd", required=True)
  p = sub.add_parser("check")
  p.add_argument("--signal", action="append", choices=SIGNALS)
  p.add_argument("--drive", action="append")
  p.add_argument("--limit", type=int, default=20)
  p.add_argument("--all", action="store_true")
  p.set_defaults(fn=check)
  sub.add_parser("customers").set_defaults(fn=list_customers)
  args = ap.parse_args()
  args.fn(args)


if __name__ == "__main__":
  main()
