#!/usr/bin/env python3
"""Tests for the container-solutions Drive scripts, against made-up fixtures and a fake gog.

  python3 -m unittest discover -s container-solutions/tests -v

Nothing here touches Drive or Ian's state: CS_STATE, CS_GOG and CS_BLOG_SITEMAP point into a
temporary folder. The names are made up (the repo is public).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)
import cs_drive  # noqa: E402

FOLDER = "application/vnd.google-apps.folder"
DOC = "application/vnd.google-apps.document"
SLIDES = "application/vnd.google-apps.presentation"
PDF = "application/pdf"
MP4 = "video/mp4"


def item(fid, path, mime=DOC, modified="2025-06-01T10:00:00Z"):
  return {"id": fid, "name": path.split("/")[-1], "path": path, "mimeType": mime,
          "modifiedTime": modified, "owners": ["someone@example.com"], "depth": path.count("/") + 1}


STATE = {
  "drives": [{"id": "d-" + n.strip().lower().replace(" ", "-"), "name": n} for n in
             ["CS Engineering", "CS Customers", "CS Marketing", "All Hands Recordings", "Content",
              "CS Operations", "CS Sales ", "Some Other Drive"]],
  "inventories": {
    "d-cs-customers": [
      item("fo-acme", "Acme Widgets Ltd", FOLDER),
      item("fo-globex", "Globex", FOLDER),
      item("fo-arch", "Archive", FOLDER),
      item("f-acme-review", "Acme Widgets Ltd/Acme Widgets architecture review"),
      item("f-wrong-cust", "Globex/Acme Widgets proposal"),
      item("f-assess", "Globex/Cloud Native Assessment - Globex", SLIDES),
      item("f-loose", "stray notes"),
    ],
    "d-cs-sales": [
      item("fo-coll", "Sales Collateral", FOLDER),
      item("fo-cases", "Sales Collateral/Case studies", FOLDER),
      item("f-case", "Sales Collateral/Case studies/Globex case study.pdf", PDF),
      item("f-bank", "Sales Collateral/Banking on the Cloud.pdf", PDF),
      item("f-onepager", "Sales Collateral/New one-pager", SLIDES),
      item("f-bank2", "Sales Collateral/Banking on the Cloud v2", SLIDES),
      item("f-olddeck", "Sales Collateral/Archive/old deck", SLIDES),
    ],
    "d-cs-marketing": [
      item("fo-inv", "Invoices", FOLDER),
      item("f-invoice", "Invoices/Invoice 2024-03"),
      item("f-ahrec", "Recordings/All Hands 2024-05 Recording.mp4", MP4),
      item("f-webscript", "Webinars/Webinar Sept 2025 script"),
      item("f-copy", "Copy of Plan"),
      item("f-acmeblog", "Acme Widgets blog post draft"),
    ],
    "d-all-hands-recordings": [
      item("f-ah1", "2024/All Hands 2024-01.mp4", MP4),
      item("f-exp", "2024/Expenses policy"),
    ],
    "root": [item("f-mine", "Globex SOW draft"), item("f-personal", "Holiday ideas")],
  },
  "files": {"f-lost": {"id": "f-lost", "name": "Demo video.mp4", "owners": [{"emailAddress": "leaver@example.com"}]}},
  "sheets": {
    "sheet-1": {
      "Most Popular": {
        "values": [["Type", "Link", "Notes"], ["White Paper", "Banking on the Cloud", ""],
                   ["Slide Deck", "Best Of slides", ""], ["Video", "Demo Video", ""]],
        "links": [{"row": 2, "col": 2, "value": "Banking on the Cloud", "link": "https://drive.google.com/file/d/f-bank/view"},
                  {"row": 4, "col": 2, "value": "Demo Video", "link": "https://drive.google.com/file/d/f-lost/view?usp=sharing"}],
      },
      "Internal Content": {
        "values": [["#", "Date", "Title", "Author", "Link (content)"], [], ["", "", "Tech Assessments"],
                   ["1", "2024-01-01", "Acme review", "", "https://docs.google.com/document/d/f-acme-review/edit"],
                   ["2", "2024-01-02", "Gone doc", "", "https://docs.google.com/document/d/f-gone/edit"],
                   ["3", "2024-01-03", "Acme review again", "", "https://docs.google.com/document/u/1/d/f-acme-review/edit#x"]],
      },
      "Types": {"values": [[""], ["", "case studies", "https://drive.google.com/drive/u/1/folders/fo-cases"]]},
      "Blogs": {
        "values": [["T", "Date", "Title"], ["", "", "", "40"], ["", "", "Blog posts"],
                   ["2", "2025-01-01", "Why Things Are Hard"], ["1", "2024-01-01", "https://blog.example.com/old-post"]],
      },
    },
  },
}

SITEMAP = """<?xml version='1.0'?><urlset>
<url><loc>https://blog.example.com/why-things-are-hard</loc><lastmod>2025-01-01</lastmod></url>
<url><loc>https://blog.example.com/old-post</loc><lastmod>2024-01-01</lastmod></url>
<url><loc>https://blog.example.com/brand-new-post</loc><lastmod>2026-09-01</lastmod></url>
<url><loc>https://blog.example.com/tag/kubernetes</loc></url>
</urlset>"""


class DriveScripts(unittest.TestCase):

  def setUp(self):
    self.tmp = tempfile.mkdtemp()
    self.state = os.path.join(self.tmp, "state")
    os.makedirs(self.state)
    with open(os.path.join(self.state, "drive.json"), "w") as f:
      json.dump({"catalog_id": "https://docs.google.com/spreadsheets/d/sheet-1/edit#gid=0"}, f)
    self.gog_state = os.path.join(self.tmp, "gog.json")
    with open(self.gog_state, "w") as f:
      json.dump(STATE, f)
    self.log = os.path.join(self.tmp, "gog.log")
    gog = os.path.join(self.tmp, "gog")
    with open(gog, "w") as f:
      f.write(f"#!/bin/sh\nexec {sys.executable} {os.path.join(HERE, 'fake_gog.py')} \"$@\"\n")
    os.chmod(gog, 0o755)
    sitemap = os.path.join(self.tmp, "sitemap.xml")
    with open(sitemap, "w") as f:
      f.write(SITEMAP)
    self.env = dict(os.environ, CS_STATE=self.state, CS_GOG=gog, FAKE_GOG_STATE=self.gog_state,
                    FAKE_GOG_LOG=self.log, CS_BLOG_SITEMAP="file://" + sitemap)

  def tearDown(self):
    shutil.rmtree(self.tmp)

  def run_script(self, name, *args, ok=True):
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, name)] + list(args), env=self.env,
                       capture_output=True, text=True)
    if ok:
      self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
    return p

  def calls(self):
    with open(self.log) as f:
      return [json.loads(l) for l in f]

  def refresh(self):
    return self.run_script("drive-inventory.py", "refresh", "--my-drive").stdout

  def test_refresh_caches_each_drive_and_skips_fresh_ones(self):
    out = self.refresh()
    self.assertIn("CS Sales\t7\tfetched", out)
    self.assertIn("My Drive\t2\tfetched", out)
    with open(os.path.join(self.state, "drive.json")) as f:
      self.assertEqual(json.load(f)["drive_ids"]["CS Sales"], "d-cs-sales")
    c = cs_drive_cache(self.state, "CS Sales")
    self.assertIn("CS Sales/Sales Collateral/Banking on the Cloud.pdf", [i["path"] for i in c["items"]])
    open(self.log, "w").close()
    out = self.refresh()
    self.assertIn("cached", out)
    self.assertEqual(self.calls(), [])
    status = self.run_script("drive-inventory.py", "status").stdout
    self.assertIn("CS Sales\t5 files\t2 folders", status)

  def test_every_gog_call_is_readonly(self):
    self.refresh()
    self.run_script("catalog-diff.py", "read")
    self.assertTrue(all("--readonly" in c for c in self.calls()))

  def test_unknown_drive_name_says_so(self):
    with open(os.path.join(self.state, "drive.json"), "w") as f:
      json.dump({"drives": ["CS Nonesuch"]}, f)
    p = self.run_script("drive-inventory.py", "refresh", ok=False)
    self.assertEqual(p.returncode, 2)
    self.assertIn("no shared drive called CS Nonesuch", p.stderr)

  def test_tree_and_find(self):
    self.refresh()
    tree = self.run_script("drive-inventory.py", "tree", "--drive", "CS Sales").stdout
    self.assertIn("5\tCS Sales/Sales Collateral\n", tree)
    self.assertIn("1\tCS Sales/Sales Collateral/Case studies\n", tree)
    found = self.run_script("drive-inventory.py", "find", "banking").stdout
    self.assertIn("f-bank2", found)

  def test_catalog_read_uses_hyperlinks_and_sections(self):
    self.refresh()
    out = self.run_script("catalog-diff.py", "read").stdout
    self.assertIn("Most Popular\t3 rows\t2 with Drive links\t0 other links\t1 no link", out)
    self.assertIn("Blogs\t2 rows\t0 with Drive links\t1 other links\t1 no link", out)
    with open(os.path.join(self.state, "drive-cache", "catalog.json")) as f:
      cat = json.load(f)
    acme = [e for e in cat["entries"] if e["title"] == "Acme review"][0]
    self.assertEqual((acme["section"], acme["ids"]), ("Tech Assessments", ["f-acme-review"]))

  def diff(self):
    self.refresh()
    self.run_script("catalog-diff.py", "read")
    return self.run_script("catalog-diff.py", "diff").stdout

  def test_diff_catalog_side(self):
    out = self.diff()
    self.assertIn("Most Popular!4\tDemo Video\tin leaver@example.com's My Drive: Demo video.mp4\tf-lost", out)
    self.assertIn("Internal Content!5\tGone doc\tcan't open it", out)
    self.assertIn("Most Popular!3\tBest Of slides", out)
    self.assertIn("Internal Content!4 Internal Content!6\tAcme review\tsame file\tf-acme-review", out)

  def test_diff_candidates(self):
    out = self.diff()
    cands = out.split("[candidate]")[1]
    self.assertIn("New one-pager", cands)
    self.assertIn("Cloud Native Assessment - Globex", cands)
    self.assertIn("Webinar Sept 2025 script", cands)
    self.assertIn("Banking on the Cloud v2\tslides 2025-06-01 ~ Most Popular!2", cands)
    self.assertNotIn("Globex case study", cands)  # inside a folder the catalog links to
    self.assertNotIn("old deck", cands)  # archive folder
    self.assertNotIn("Invoice", cands)

  def test_decision_drops_a_candidate(self):
    self.diff()
    self.run_script("drive-decide.py", "add", "f-onepager", "catalog", "not-marketing", "internal only")
    out = self.run_script("catalog-diff.py", "diff").stdout
    self.assertNotIn("New one-pager", out)
    listed = self.run_script("drive-decide.py", "list", "catalog").stdout
    self.assertEqual(listed, "f-onepager\tnot-marketing\tinternal only\n")
    self.run_script("drive-decide.py", "remove", "f-onepager")
    self.assertIn("New one-pager", self.run_script("catalog-diff.py", "diff").stdout)

  def test_filing_signals(self):
    self.refresh()
    out = self.run_script("filing-check.py", "check", "--all").stdout
    sections = {s.split("]")[0]: s for s in out.split("\n[")[1:]}
    self.assertIn("stray notes\tloose at the top", sections["root"])
    self.assertIn("Copy of Plan", sections["root"])
    self.assertIn("Copy of Plan\tcopy or untitled", sections["stray"])
    self.assertIn("Acme Widgets blog post draft\tnames acme widgets; customer files go in CS Customers or CS Sales",
                  sections["customer"])
    self.assertIn("Globex/Acme Widgets proposal\tnames acme widgets but is in Globex's folder", sections["customer"])
    self.assertNotIn("architecture review", sections["customer"])
    self.assertIn("Recordings/All Hands 2024-05 Recording.mp4\tall-hands recording outside", sections["allhands"])
    self.assertIn("2024/Expenses policy\tin the all-hands drive", sections["allhands"])
    self.assertNotIn("All Hands 2024-01.mp4", sections["allhands"])
    self.assertIn("Invoices/Invoice 2024-03\tfinance/people: expected in CS Operations", sections["rule"])
    self.assertIn("Globex SOW draft\tcontract/legal: belongs in", sections["mydrive"])
    self.assertNotIn("Holiday ideas", out)

  def test_customers_skip_non_customer_folders(self):
    self.refresh()
    out = self.run_script("filing-check.py", "customers").stdout
    self.assertIn("acme widgets\tCS Customers/Acme Widgets Ltd", out)
    self.assertNotIn("archive", out)

  def test_blog_posts_missing_from_the_blogs_tab(self):
    self.diff()
    out = self.run_script("catalog-diff.py", "blog").stdout
    self.assertIn("sitemap: 3 posts", out)
    self.assertIn("brand-new-post", out)
    self.assertNotIn("why-things-are-hard", out)
    self.assertNotIn("old-post", out)


class Helpers(unittest.TestCase):

  def test_drive_ids(self):
    for u, want in [
        ("https://docs.google.com/presentation/d/1bP6yKl_uS9-2M4/edit#slide=id.g1", "1bP6yKl_uS9-2M4"),
        ("https://docs.google.com/document/u/1/d/1abcdefghijk/edit", "1abcdefghijk"),
        ("https://drive.google.com/drive/u/1/folders/12EAb79Zzc15", "12EAb79Zzc15"),
        ("https://drive.google.com/file/d/1xyzxyzxyzxy/view?usp=sharing", "1xyzxyzxyzxy"),
        ("https://drive.google.com/open?id=1openopenopen", "1openopenopen")]:
      self.assertEqual(cs_drive.drive_ids(u), [want], u)
    self.assertEqual(cs_drive.drive_ids("https://www.youtube.com/watch?v=lm3Q-3WvYFo"), [])

  def test_norm_title(self):
    self.assertEqual(cs_drive.norm_title("Copy of Why I’m Here.pdf"), "why im here")


def cs_drive_cache(state, drive):
  with open(os.path.join(state, "drive-cache", cs_drive.slug(drive) + ".json")) as f:
    return json.load(f)


if __name__ == "__main__":
  unittest.main()
