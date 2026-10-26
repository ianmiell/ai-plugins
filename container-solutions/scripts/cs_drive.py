"""Shared helpers for the container-solutions Drive scripts: config, gog, the inventory cache.

Not run directly. The scripts next to it import it.

The repo is public, so nothing about Container Solutions' files lives in it. The catalog ID,
the cached inventory and Ian's decisions are local, under CS_STATE (~/.claude/container-solutions).
"""

import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "..", "skills", "drive", "default-config.json")
STATE = os.path.expanduser(os.environ.get("CS_STATE", "~/.claude/container-solutions"))
CONFIG = os.path.join(STATE, "drive.json")
CACHE = os.path.join(STATE, "drive-cache")
DECISIONS = os.path.join(STATE, "drive-decisions.tsv")
# CS_GOG lets the tests put a fake gog in place of the real one.
GOG = os.environ.get("CS_GOG", "gog")
MY_DRIVE = "My Drive"

FOLDER = "application/vnd.google-apps.folder"
SHORTCUT = "application/vnd.google-apps.shortcut"
KIND = {
  "application/vnd.google-apps.document": "doc",
  "application/vnd.google-apps.presentation": "slides",
  "application/vnd.google-apps.spreadsheet": "sheet",
  "application/vnd.google-apps.form": "form",
  "application/pdf": "pdf",
  FOLDER: "folder",
  SHORTCUT: "shortcut",
}


def die(msg, code=1):
  print(msg, file=sys.stderr)
  sys.exit(code)


def kind(mime):
  if mime in KIND:
    return KIND[mime]
  for prefix in ("video", "audio", "image"):
    if (mime or "").startswith(prefix + "/"):
      return prefix
  if "word" in (mime or "") or "opendocument.text" in (mime or ""):
    return "doc"
  if "presentation" in (mime or ""):
    return "slides"
  if "sheet" in (mime or "") or "excel" in (mime or ""):
    return "sheet"
  return "other"


def config():
  """The defaults from the skill, with the local drive.json laid over them key by key."""
  with open(DEFAULT_CONFIG) as f:
    cfg = json.load(f)
  if os.path.exists(CONFIG):
    with open(CONFIG) as f:
      cfg.update(json.load(f))
  return cfg


def save_local_config(updates):
  os.makedirs(STATE, exist_ok=True)
  local = {}
  if os.path.exists(CONFIG):
    with open(CONFIG) as f:
      local = json.load(f)
  local.update(updates)
  with open(CONFIG, "w") as f:
    json.dump(local, f, indent=2)
    f.write("\n")


class GogError(Exception):
  pass


def auth_hint(text, account):
  fix = f"! gog auth add {account} --services drive,sheets --force-consent"
  if re.search(r"invalid_grant|token (has been )?expired|revoked", text, re.I):
    return f"gog's login for {account} has expired. Ask Ian to run: {fix}"
  if re.search(r"no (stored )?(refresh )?token|not authenticated|unknown account|no auth|missing.*token", text, re.I):
    return f"gog has no login for {account}. Ask Ian to run: {fix}"
  if re.search(r"API is not enabled|has not been used in project", text, re.I):
    return ("The Drive or Sheets API is off in gog's Cloud project. Run: gcloud services enable "
            "drive.googleapis.com sheets.googleapis.com --project ianmiell-gog-personal --account ian.miell@gmail.com")
  return None


def gog(*args, account=None, timeout=3600):
  """Run gog read-only for the work account and return parsed JSON."""
  account = account or config()["account"]
  cmd = [GOG, "-a", account, "--readonly", "--no-input", "--json"] + [str(a) for a in args]
  for wait in (5, 15, 30, 60, None):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode == 0 or not re.search(r"rateLimitExceeded|userRateLimit|429", p.stderr + p.stdout) or wait is None:
      break
    time.sleep(wait)
  if p.returncode != 0:
    text = (p.stderr or p.stdout).strip()
    hint = auth_hint(text, account)
    raise GogError(hint or f"{' '.join(cmd[1:])}: {text}")
  out = p.stdout.strip()
  return json.loads(out) if out else None


def listing(result, *keys):
  """The list inside a gog JSON reply, whichever key it came under."""
  if isinstance(result, list):
    return result
  for k in keys + ("items", "files", "drives", "results"):
    if isinstance(result, dict) and isinstance(result.get(k), list):
      return result[k]
  return []


# Drive file IDs in the links people paste: Docs/Sheets/Slides/Forms, drive file and folder
# links (with or without /u/N/), and the old open?id= form.
ID_RES = [
  re.compile(r"docs\.google\.com/(?:a/[^/]+/)?(?:document|presentation|spreadsheets|forms|drawings|file)/(?:u/\d+/)?d/(?:e/)?([\w-]{6,})"),
  re.compile(r"drive\.google\.com/(?:a/[^/]+/)?(?:drive/)?(?:u/\d+/)?(?:folders|file/d)/([\w-]{6,})"),
  re.compile(r"(?:drive|docs)\.google\.com/[^\s]*[?&]id=([\w-]{6,})"),
]
URL_RE = re.compile(r"https?://[^\s\"'<>|]+")


def drive_ids(text):
  ids = []
  for r in ID_RES:
    for m in r.findall(text or ""):
      if m not in ids:
        ids.append(m)
  return ids


def urls(text):
  return [u.rstrip(".,);") for u in URL_RE.findall(text or "")]


def norm_title(s):
  """Lower case, no extension, punctuation or 'copy of', for matching titles loosely."""
  s = (s or "").lower()
  s = re.sub(r"\.(pdf|docx?|pptx?|xlsx?|mp4|mov|key)$", "", s)
  s = re.sub(r"^copy of ", "", s)
  s = re.sub(r"[‘’']", "", s)
  s = re.sub(r"[^a-z0-9]+", " ", s)
  return s.strip()


def slug(name):
  return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def cache_file(drive):
  return os.path.join(CACHE, slug(drive) + ".json")


def load_cache(drive):
  p = cache_file(drive)
  if not os.path.exists(p):
    return None
  with open(p) as f:
    return json.load(f)


def load_inventory(drives=None, need=True):
  """Every cached item across the given drives (default: the configured ones, plus My Drive
  if cached). Exits with the refresh command if a configured drive has no cache."""
  cfg = config()
  names = drives or cfg["drives"] + [MY_DRIVE]
  items, missing = [], []
  for d in names:
    c = load_cache(d)
    if c is None:
      if d != MY_DRIVE or drives:
        missing.append(d)
      continue
    items.extend(c["items"])
  if missing and need:
    die("no inventory for " + ", ".join(missing) + ": run drive-inventory.py refresh first", 2)
  return items


def load_decisions(check=None):
  """{file_id: (decision, note)} for one check ('catalog' or 'filing'), or for all."""
  out = {}
  if not os.path.exists(DECISIONS):
    return out
  with open(DECISIONS) as f:
    for line in f:
      parts = line.rstrip("\n").split("\t")
      if len(parts) < 3 or line.startswith("#"):
        continue
      fid, chk, decision = parts[:3]
      if check is None or chk == check:
        out[fid] = (decision, parts[3] if len(parts) > 3 else "")
  return out


def age(ts):
  h = (time.time() - ts) / 3600
  return f"{h:.0f}h" if h < 48 else f"{h / 24:.0f}d"


def line(*cols):
  return "\t".join(str(c) for c in cols)
