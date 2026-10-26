#!/usr/bin/env python3
"""Compare the CS Content Catalog spreadsheet with what's in the shared drives and on the blog.

  catalog-diff.py read                    fetch the catalog (values and hyperlinks) into the cache
  catalog-diff.py diff [--limit 15] [--all] [--drive NAME ...]
  catalog-diff.py blog [--since 2025-01-01]

`read` keeps one entry per catalog row: tab, row, section heading, title and every link in the
row (cell text and hyperlinks, so a title like "Demo Video" still yields its Drive file).

`diff` needs a fresh inventory (drive-inventory.py refresh) and prints:
  [missing]    catalog links to a Drive file that isn't in the CS shared drives: says where it
               is (someone's My Drive, another shared drive), or that it's trashed or can't be
               opened
  [archived]   catalog links to a file in an archive/old folder
  [nolink]     catalog row with a title but no link
  [duplicate]  the same file, or the same title, on more than one row
  [candidate]  marketing-looking files in the drives (by folder and name, from the config's
               "content" section) that aren't on the catalog, grouped by folder; "~ Tab!row"
               marks one whose title is close to a catalog row (another version?)
Files inside a folder the catalog links to count as covered. Files Ian has decided on
(drive-decide.py, check "catalog") are left out. Everything also goes to
drive-cache/catalog-diff.tsv.

`blog` compares the Blogs tab with the blog's sitemap and lists posts that aren't on it. The
sitemap's lastmod is the last edit, not the publish date (many old posts share one bulk date).
"""

import argparse
import collections
import concurrent.futures
import difflib
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_drive as cs  # noqa: E402

CATALOG = os.path.join(cs.CACHE, "catalog.json")
STOP = {"a", "an", "the", "of", "and", "to", "in", "on", "is", "for", "with", "we", "our", "your", "s"}
SITEMAP = os.environ.get("CS_BLOG_SITEMAP", "https://blog.container-solutions.com/sitemap.xml")


def catalog_id():
  cid = cs.config().get("catalog_id")
  if not cid:
    cs.die("no catalog_id in ~/.claude/container-solutions/drive.json: ask Ian for the catalog's link", 2)
  return cs.drive_ids(cid)[0] if "/" in cid else cid


def quoted(tab):
  return "'" + tab.replace("'", "''") + "'"


def entries_for_tab(tab, values, links):
  """One entry per catalog row with something in it. Section headings and the tag-count row
  aren't entries; a heading names the section for the rows below it."""
  by_row = collections.defaultdict(list)
  for l in links:
    if l.get("link") and not l["link"].startswith("#"):
      by_row[l["row"]].append(l["link"])
  header, title_col = None, None
  for r, row in enumerate(values[:6]):
    low = [str(c).strip().lower() for c in row]
    for want in ("title", "link"):
      if want in low:
        header, title_col = r, low.index(want)
        break
    if header is not None:
      break
  out, section = [], ""
  for r, row in enumerate(values):
    if header is not None and r <= header:
      continue
    cells = [str(c).strip() for c in row]
    if not any(cells):
      continue
    row_urls = by_row.get(r + 1, []) + [u for c in cells for u in cs.urls(c)]
    if title_col is not None:
      title = cells[title_col] if title_col < len(cells) else ""
      filled = [i for i, c in enumerate(cells) if c]
      if not row_urls and filled == [title_col]:
        section = title
        continue
      if not title:
        continue  # the tag-count row under the header
    else:
      title = next((c for c in cells if c and not cs.urls(c)), cells[0] if cells else "")
    ids = []
    for u in row_urls:
      ids += [i for i in cs.drive_ids(u) if i not in ids]
    out.append({"tab": tab, "row": r + 1, "section": section, "title": title,
                "urls": list(dict.fromkeys(row_urls)), "ids": ids})
  return out


def read(args):
  cid = catalog_id()
  meta = cs.gog("sheets", "metadata", cid)
  tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]
  entries = []
  for tab in tabs:
    values = (cs.gog("sheets", "get", cid, quoted(tab)) or {}).get("values") or []
    links = (cs.gog("sheets", "links", "get", cid, quoted(tab)) or {}).get("links") or []
    got = entries_for_tab(tab, values, links)
    entries += got
    print(cs.line(tab, f"{len(got)} rows", f"{sum(1 for e in got if e['ids'])} with Drive links",
                  f"{sum(1 for e in got if e['urls'] and not e['ids'])} other links",
                  f"{sum(1 for e in got if not e['urls'])} no link"))
  os.makedirs(cs.CACHE, exist_ok=True)
  with open(CATALOG, "w") as f:
    json.dump({"id": cid, "tabs": tabs, "entries": entries}, f)


def load_catalog():
  if not os.path.exists(CATALOG):
    cs.die("no catalog in the cache: run catalog-diff.py read first", 2)
  with open(CATALOG) as f:
    return json.load(f)


def where(fid):
  """Where a Drive file is, for one the inventory doesn't have."""
  try:
    res = cs.gog("drive", "get", fid, "--fields", "id,name,trashed,driveId,owners(emailAddress)")
  except cs.GogError as e:
    return "can't open it (deleted, or not shared with Ian)" if re.search(r"404|not ?found", str(e), re.I) else str(e)[:120]
  f = res.get("file", res) if isinstance(res, dict) else {}
  name = f.get("name") or f.get("title") or "?"
  if f.get("trashed"):
    return f"trashed: {name}"
  owners = [o.get("emailAddress", o) if isinstance(o, dict) else o for o in f.get("owners") or []]
  if f.get("driveId"):
    return f"in another shared drive ({f['driveId']}): {name}"
  return f"in {', '.join(owners) or 'someone'}'s My Drive: {name}"


def ref(e):
  return f"{e['tab']}!{e['row']}"


def diff(args):
  cfg = cs.config()
  cat = load_catalog()
  inv = cs.load_inventory(args.drive or None)
  by_id = {i["id"]: i for i in inv}
  decided = cs.load_decisions("catalog")
  rows = []

  def emit(tag, *cols):
    rows.append((tag,) + cols)

  # Catalog -> drives.
  linked = collections.defaultdict(list)
  for e in cat["entries"]:
    for fid in e["ids"]:
      linked[fid].append(e)
  outside = [fid for fid in linked if fid not in by_id and fid not in decided]
  with concurrent.futures.ThreadPoolExecutor(8) as pool:
    found = dict(zip(outside, pool.map(where, outside)))
  for fid in outside:
    for e in linked[fid]:
      emit("missing", ref(e), e["title"], found[fid], fid)
  archived = re.compile(cfg["content"]["exclude_paths"])
  for fid, es in linked.items():
    if fid in by_id and archived.search(by_id[fid]["path"]) and fid not in decided:
      for e in es:
        emit("archived", ref(e), e["title"], by_id[fid]["path"], fid)
  for e in cat["entries"]:
    if not e["urls"]:
      emit("nolink", ref(e), e["title"], e["section"], "")
  for fid, es in linked.items():
    if len(es) > 1:
      emit("duplicate", " ".join(ref(e) for e in es), es[0]["title"], "same file", fid)
  by_title = collections.defaultdict(list)
  for e in cat["entries"]:
    if not cs.urls(e["title"]) and cs.norm_title(e["title"]):
      by_title[(e["tab"], cs.norm_title(e["title"]))].append(e)
  for (tab, _), es in by_title.items():
    if len(es) > 1:
      emit("duplicate", " ".join(ref(e) for e in es), es[0]["title"], "same title", "")

  # Drives -> catalog.
  covered = [by_id[fid]["path"] + "/" for fid in linked if fid in by_id and by_id[fid]["mime"] == cs.FOLDER]
  c = cfg["content"]
  paths, names = re.compile(c["paths"]), re.compile(c["names"])
  titles = [(cs.norm_title(e["title"]), e) for e in cat["entries"] if cs.norm_title(e["title"])]
  titles += [(cs.norm_title(by_id[fid]["name"]), es[0]) for fid, es in linked.items() if fid in by_id]
  candidates = []
  for i in inv:
    k = cs.kind(i["mime"])
    if k not in c["kinds"] or i["id"] in linked or i["id"] in decided or archived.search(i["path"]):
      continue
    if any(i["path"].startswith(p) for p in covered):
      continue
    in_folder = paths.search(i["folder"].split("/", 1)[-1]) if "/" in i["folder"] else None
    if not (in_folder or names.search(i["name"])):
      continue
    if k == "sheet" and not names.search(i["name"]):
      continue
    n = cs.norm_title(i["name"])
    close = ""
    for t, e in titles:
      if t == n or (abs(len(t) - len(n)) < 12 and difflib.SequenceMatcher(None, t, n).quick_ratio() > 0.9
                    and difflib.SequenceMatcher(None, t, n).ratio() > 0.9):
        close = "~ " + ref(e)
        break
    candidates.append(i)
    emit("candidate", i["folder"], i["name"], f"{k} {i['modified']} {close}".strip(), i["id"])

  out = os.path.join(cs.CACHE, "catalog-diff.tsv")
  with open(out, "w") as f:
    f.write(cs.line("check", "where", "title", "detail", "id") + "\n")
    for r in rows:
      f.write(cs.line(*r) + "\n")

  counts = collections.Counter(r[0] for r in rows)
  print("summary: " + ", ".join(f"{counts[t]} {t}" for t in ("missing", "archived", "nolink", "duplicate", "candidate")))
  print(f"catalog: {len(cat['entries'])} rows, {len(linked)} Drive files; inventory: {len(inv)} items; full list: {out}")
  for tag in ("missing", "archived", "duplicate", "nolink"):
    shown = [r for r in rows if r[0] == tag]
    if shown:
      print(f"\n[{tag}]")
      for r in shown[: None if args.all else args.limit * 4]:
        print(cs.line(*r[1:]))
      if not args.all and len(shown) > args.limit * 4:
        print(f"... {len(shown) - args.limit * 4} more in the TSV")
  groups = collections.defaultdict(list)
  for r in rows:
    if r[0] == "candidate":
      groups[r[1]].append(r)
  if groups:
    print("\n[candidate] by folder, most files first")
  for folder, rs in sorted(groups.items(), key=lambda g: -len(g[1])):
    print(f"{folder}  ({len(rs)})")
    rs.sort(key=lambda r: r[3].split()[1] if len(r[3].split()) > 1 else "", reverse=True)
    for r in rs[: None if args.all else args.limit]:
      print("  " + cs.line(r[2], r[3], r[4]))
    if not args.all and len(rs) > args.limit:
      print(f"  ... {len(rs) - args.limit} more")


def blog(args):
  cat = load_catalog()
  with urllib.request.urlopen(SITEMAP, timeout=60) as r:
    xml = r.read().decode("utf-8", "replace")
  posts = []
  for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
    loc = re.search(r"<loc>([^<]+)</loc>", block)
    mod = re.search(r"<lastmod>([^<]+)</lastmod>", block)
    if not loc:
      continue
    u = loc.group(1).strip()
    path = re.sub(r"^https?://[^/]+/?", "", u).strip("/")
    if not path or re.match(r"(tag|author|page|topic)(/|$)", path) or "/page/" in path:
      continue
    posts.append((mod.group(1)[:10] if mod else "", u, path))
  blog_rows = [e for e in cat["entries"] if e["tab"].lower().startswith("blog")]
  slugs = {re.sub(r"^https?://[^/]+/?", "", u).strip("/") for e in blog_rows for u in e["urls"]}
  slugs |= {re.sub(r"^https?://[^/]+/?", "", e["title"]).strip("/") for e in blog_rows if cs.urls(e["title"])}
  # Slugs are often a cut-down title ("how-company-culture-impacts-code-quality" for "A Conway's
  # Law Variant: How Company Culture Impacts Code Quality"), so match on words, not strings.
  titles = [set(cs.norm_title(e["title"]).split()) - STOP for e in blog_rows]
  missing = []
  for mod, u, path in posts:
    if args.since and mod and mod < args.since:
      continue
    words = set(path.replace("-", " ").split()) - STOP
    if path in slugs or any(words and (words <= t or len(words & t) >= max(3, int(0.8 * len(words)))) for t in titles):
      continue
    missing.append((mod, u))
  print(f"sitemap: {len(posts)} posts; Blogs tab: {len(blog_rows)} rows; not on the tab: {len(missing)}")
  for mod, u in sorted(missing, reverse=True):
    print(cs.line(mod, u))


def main():
  ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  sub = ap.add_subparsers(dest="cmd", required=True)
  sub.add_parser("read").set_defaults(fn=read)
  p = sub.add_parser("diff")
  p.add_argument("--limit", type=int, default=15)
  p.add_argument("--all", action="store_true")
  p.add_argument("--drive", action="append")
  p.set_defaults(fn=diff)
  p = sub.add_parser("blog")
  p.add_argument("--since")
  p.set_defaults(fn=blog)
  args = ap.parse_args()
  try:
    args.fn(args)
  except cs.GogError as e:
    cs.die(str(e))


if __name__ == "__main__":
  main()
