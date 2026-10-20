#!/usr/bin/env python3
"""Read Ian's WhatsApp from the Mac desktop app's local database, and hand
drafts back to the app for him to send.

Never writes to WhatsApp's files: each run takes a read-only snapshot of
ChatStorage.sqlite (and ContactsV2.sqlite, for phone numbers) into memory.
Nothing is sent: `draft` opens the chat with the text typed in, or copies
it to the clipboard, and Ian presses Enter himself.

  whatsapp.py chats [--since 2d] [--unread] [--dms|--groups] [--limit N]
  whatsapp.py read CHAT [--since 7d] [--limit 40]
  whatsapp.py search TEXT [--chat CHAT] [--since 30d] [--limit 30]
  whatsapp.py mine [--since 365d] [--dms|--groups] [--limit 500]
  whatsapp.py draft CHAT [--dry-run] <<'EOF'
  draft text
  EOF

CHAT is a chat id from `chats` (the number in the first column), a phone
number, or part of the chat's name (it must match one chat). Add --json to
any read command for machine-readable output. Exits 0 on success, 1 when
nothing matched or the database can't be read, 2 on bad usage.
"""

import argparse
import datetime
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.parse

CONTAINER = os.path.expanduser(
  "~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared")
CHAT_DB = os.path.join(CONTAINER, "ChatStorage.sqlite")
CONTACTS_DB = os.path.join(CONTAINER, "ContactsV2.sqlite")

# Core Data stores dates as seconds since 2001-01-01 UTC.
APPLE_EPOCH = 978307200

DM, GROUP, BROADCAST, STATUS = 0, 1, 2, 3

# ZMESSAGETYPE values, worked out from the media files they point at
# (October 2026). Anything else shows as "[other N]".
TYPES = {
  0: None,
  1: "photo",
  2: "video",
  3: "voice note",
  4: "contact card",
  5: "location",
  6: "system",
  7: None,          # text with a link preview
  8: "document",
  10: "system",
  11: "GIF",
  15: "sticker",
}
SYSTEM_TYPES = {6, 10}


def body_text(mtype, text):
  """A message's text, with a [photo]-style label for anything that isn't plain text."""
  if mtype is None:
    return ""
  label = TYPES.get(mtype, f"other {mtype}")
  if label and text:
    return f"[{label}] {text}"
  if label:
    return f"[{label}]"
  return text or ""


def real_name(name):
  """Some name columns hold encoded blobs (eg '+Q2xhcmVuY2U='): drop those."""
  if not name:
    return None
  if re.fullmatch(r"\+?[A-Za-z0-9+/]{8,}={0,2}", name) and (
      name.endswith("=") or (re.search(r"\d", name) and re.search(r"[A-Z].*[A-Z]", name))):
    return None
  return name


def die(msg, code=1):
  print(f"whatsapp: {msg}", file=sys.stderr)
  sys.exit(code)


def snapshot(path):
  """Copy a WhatsApp database into memory without touching the original."""
  if not os.path.exists(path):
    die(f"{path} not found: is the WhatsApp desktop app installed and signed in?")
  try:
    src = sqlite3.connect(f"file:{urllib.parse.quote(path)}?mode=ro", uri=True)
    mem = sqlite3.connect(":memory:")
    src.backup(mem)
    src.close()
  except sqlite3.Error as e:
    die(f"can't read {path} ({e}). If it's 'unable to open', give your "
        "terminal Full Disk Access in System Settings > Privacy & Security.")
  mem.row_factory = sqlite3.Row
  return mem


def to_time(apple):
  if apple is None:
    return None
  return datetime.datetime.fromtimestamp(apple + APPLE_EPOCH)


def fmt_time(dt):
  if dt is None:
    return "-"
  now = datetime.datetime.now()
  if dt.date() == now.date():
    return dt.strftime("%H:%M")
  if (now - dt).days < 6:
    return dt.strftime("%a %H:%M")
  if dt.year == now.year:
    return dt.strftime("%d %b %H:%M")
  return dt.strftime("%d %b %Y")


def parse_since(text):
  """'2d', '6h', '90m', 'today', 'YYYY-MM-DD' -> Core Data timestamp."""
  if text is None:
    return None
  now = datetime.datetime.now()
  m = re.fullmatch(r"(\d+)([mhdw])", text)
  if m:
    n, unit = int(m.group(1)), m.group(2)
    delta = {"m": datetime.timedelta(minutes=n), "h": datetime.timedelta(hours=n),
             "d": datetime.timedelta(days=n), "w": datetime.timedelta(weeks=n)}[unit]
    dt = now - delta
  elif text == "today":
    dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
  elif text == "yesterday":
    dt = (now - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
  else:
    try:
      dt = datetime.datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
      die(f"can't read --since {text!r}: use 2d, 6h, today, yesterday or YYYY-MM-DD", 2)
  return dt.timestamp() - APPLE_EPOCH


class WhatsApp:
  def __init__(self):
    self.db = snapshot(CHAT_DB)
    self.lid_phone = {}
    self.names = {}
    # Fallbacks first, so better names overwrite them: WhatsApp profile name,
    # then the first name the group shows, then Ian's address book.
    for row in self.db.execute("select ZJID, ZPUSHNAME from ZWAPROFILEPUSHNAME"):
      if real_name(row["ZPUSHNAME"]):
        self.names[row["ZJID"]] = "~" + row["ZPUSHNAME"]
    for row in self.db.execute("select ZMEMBERJID, ZCONTACTNAME, ZFIRSTNAME from ZWAGROUPMEMBER"):
      name = real_name(row["ZCONTACTNAME"]) or real_name(row["ZFIRSTNAME"])
      if name:
        self.names[row["ZMEMBERJID"]] = name
    if os.path.exists(CONTACTS_DB):
      contacts = snapshot(CONTACTS_DB)
      for row in contacts.execute(
          "select ZLID, ZWHATSAPPID, nullif(ZFULLNAME, '') name from ZWAADDRESSBOOKCONTACT"):
        lid, wid, name = row["ZLID"], row["ZWHATSAPPID"] or "", real_name(row["name"])
        if lid and re.fullmatch(r"\d+@s\.whatsapp\.net", wid):
          self.lid_phone[lid] = wid.split("@")[0]
        for jid in (lid, wid):
          if jid and name:
            self.names[jid] = name
      contacts.close()
    self.muted = set()
    for row in self.db.execute("select ZJID, ZMUTEDUNTIL from ZWACHATPUSHCONFIG"):
      until = to_time(row["ZMUTEDUNTIL"])
      if until and until > datetime.datetime.now():
        self.muted.add(row["ZJID"])

  def phone(self, chat):
    """The chat's phone number for a whatsapp://send link, or None."""
    jid = chat["ZCONTACTJID"] or ""
    if chat["ZSESSIONTYPE"] != DM:
      return None
    if re.fullmatch(r"\d+@s\.whatsapp\.net", jid):
      return jid.split("@")[0]
    return self.lid_phone.get(jid)

  def chat_dict(self, row):
    kind = {DM: "dm", GROUP: "group", BROADCAST: "broadcast", STATUS: "status"}.get(
      row["ZSESSIONTYPE"], str(row["ZSESSIONTYPE"]))
    return {
      "id": row["Z_PK"],
      "kind": kind,
      "name": row["ZPARTNERNAME"] or row["ZCONTACTJID"],
      "jid": row["ZCONTACTJID"],
      "unread": row["ZUNREADCOUNT"] or 0,
      "last": to_time(row["ZLASTMESSAGEDATE"]),
      "last_from_me": bool(row["last_from_me"]),
      "last_text": body_text(row["last_type"], row["last_body"]),
      "archived": bool(row["ZARCHIVED"]),
      "muted": row["ZCONTACTJID"] in self.muted,
      "unsent_draft": row["ZSAVEDINPUT"] or None,
      "phone": self.phone(row),
    }

  CHAT_SQL = (
    "select c.*, m.ZISFROMME last_from_me, m.ZTEXT last_body, m.ZMESSAGETYPE last_type "
    "from ZWACHATSESSION c "
    "left join ZWAMESSAGE m on m.Z_PK = c.ZLASTMESSAGE "
    "where coalesce(c.ZREMOVED, 0) = 0 and coalesce(c.ZHIDDEN, 0) = 0 ")

  def chats(self, since=None, unread=False, kind=None, limit=50):
    sql = self.CHAT_SQL + "and c.ZSESSIONTYPE in (0, 1) "
    args = []
    if since is not None:
      sql += "and c.ZLASTMESSAGEDATE >= ? "
      args.append(since)
    if unread:
      sql += "and c.ZUNREADCOUNT > 0 "
    if kind is not None:
      sql += "and c.ZSESSIONTYPE = ? "
      args.append(kind)
    sql += "order by c.ZLASTMESSAGEDATE desc limit ?"
    args.append(limit)
    return [self.chat_dict(r) for r in self.db.execute(sql, args)]

  def find_chat(self, ref):
    """A chat by id, phone number or unique part of its name."""
    rows = []
    if re.fullmatch(r"\d{1,6}", ref):
      rows = list(self.db.execute(self.CHAT_SQL + "and c.Z_PK = ?", [int(ref)]))
    if not rows and re.fullmatch(r"\+?[\d ]{7,}", ref):
      digits = re.sub(r"\D", "", ref)
      jids = [digits + "@s.whatsapp.net"] + [l for l, p in self.lid_phone.items() if p == digits]
      marks = ",".join("?" * len(jids))
      rows = list(self.db.execute(self.CHAT_SQL + f"and c.ZCONTACTJID in ({marks})", jids))
    if not rows:
      rows = list(self.db.execute(
        self.CHAT_SQL + "and c.ZSESSIONTYPE in (0, 1) and c.ZPARTNERNAME like ? "
        "order by c.ZLASTMESSAGEDATE desc", [f"%{ref}%"]))
      exact = [r for r in rows if (r["ZPARTNERNAME"] or "").lower() == ref.lower()]
      if len(exact) == 1:
        rows = exact
    if not rows:
      die(f"no chat matches {ref!r}")
    if len(rows) > 1:
      names = "; ".join(f"{r['Z_PK']} {r['ZPARTNERNAME']}" for r in rows[:10])
      die(f"{ref!r} matches {len(rows)} chats, use the id: {names}")
    return self.chat_dict(rows[0])

  def sender(self, row, chat_kind):
    if row["ZISFROMME"]:
      return "Ian"
    if chat_kind == "dm":
      return row["partner"] or row["ZFROMJID"]
    # The message's own ZPUSHNAME is an encoded blob, not a name.
    jid = row["member_jid"]
    if jid in self.names:
      return self.names[jid]
    if jid and re.fullmatch(r"\d+@s\.whatsapp\.net", jid):
      return "+" + jid.split("@")[0]
    return "unknown member"

  def message_dict(self, row, chat_kind):
    mtype = row["ZMESSAGETYPE"]
    return {
      "id": row["Z_PK"],
      "chat_id": row["ZCHATSESSION"],
      "chat": row["partner"],
      "time": to_time(row["ZMESSAGEDATE"]),
      "from": self.sender(row, chat_kind or ("dm" if row["ZSESSIONTYPE"] == DM else "group")),
      "from_me": bool(row["ZISFROMME"]),
      "system": mtype in SYSTEM_TYPES,
      "starred": bool(row["ZSTARRED"]),
      "text": body_text(mtype, row["ZTEXT"]),
    }

  MSG_SQL = (
    "select m.*, c.ZPARTNERNAME partner, c.ZSESSIONTYPE, g.ZMEMBERJID member_jid "
    "from ZWAMESSAGE m join ZWACHATSESSION c on c.Z_PK = m.ZCHATSESSION "
    "left join ZWAGROUPMEMBER g on g.Z_PK = m.ZGROUPMEMBER ")

  def messages(self, chat, since=None, limit=40):
    sql = self.MSG_SQL + "where m.ZCHATSESSION = ? "
    args = [chat["id"]]
    if since is not None:
      sql += "and m.ZMESSAGEDATE >= ? "
      args.append(since)
    sql += "order by m.ZMESSAGEDATE desc limit ?"
    args.append(limit)
    rows = list(self.db.execute(sql, args))
    rows.reverse()
    return [self.message_dict(r, chat["kind"]) for r in rows]

  def search(self, text, chat=None, since=None, limit=30):
    sql = self.MSG_SQL + "where m.ZTEXT like ? and c.ZSESSIONTYPE in (0, 1) "
    args = [f"%{text}%"]
    if chat:
      sql += "and m.ZCHATSESSION = ? "
      args.append(chat["id"])
    if since is not None:
      sql += "and m.ZMESSAGEDATE >= ? "
      args.append(since)
    sql += "order by m.ZMESSAGEDATE desc limit ?"
    args.append(limit)
    return [self.message_dict(r, None) for r in self.db.execute(sql, args)]

  def mine(self, since=None, kind=None, limit=500):
    """Ian's own sent text messages, newest first: source for voices/whatsapp.md."""
    sql = self.MSG_SQL + ("where m.ZISFROMME = 1 and m.ZMESSAGETYPE in (0, 7) "
                          "and m.ZTEXT is not null and c.ZSESSIONTYPE in (0, 1) ")
    args = []
    if kind is not None:
      sql += "and c.ZSESSIONTYPE = ? "
      args.append(kind)
    if since is not None:
      sql += "and m.ZMESSAGEDATE >= ? "
      args.append(since)
    sql += "order by m.ZMESSAGEDATE desc limit ?"
    args.append(limit)
    return [self.message_dict(r, None) for r in self.db.execute(sql, args)]


def as_json(items):
  def default(o):
    if isinstance(o, datetime.datetime):
      return o.isoformat(timespec="seconds")
    raise TypeError(o)
  print(json.dumps(items, default=default, ensure_ascii=False, indent=2))


def one_line(text, width=70):
  text = " ".join((text or "").split())
  return text if len(text) <= width else text[:width - 1] + "…"


def print_chats(chats):
  for c in chats:
    flags = []
    if c["unread"]:
      flags.append(f"{c['unread']} unread")
    if not c["last_from_me"] and c["kind"] == "dm":
      flags.append("waiting")
    if c["muted"]:
      flags.append("muted")
    if c["archived"]:
      flags.append("archived")
    if c["unsent_draft"]:
      flags.append("unsent draft")
    who = "Ian: " if c["last_from_me"] else ""
    print(f"{c['id']:>5}  {c['kind']:<5}  {fmt_time(c['last']):<12}  {one_line(c['name'], 28):<28}  "
          f"{', '.join(flags):<22}  {who}{one_line(c['last_text'], 50)}")


def print_messages(msgs, show_chat=False):
  for m in msgs:
    where = f"[{one_line(m['chat'], 20)}] " if show_chat else ""
    star = " *" if m["starred"] else ""
    print(f"{fmt_time(m['time']):<12} {where}{m['from']}{star}: {m['text']}")


def kind_arg(args):
  if getattr(args, "dms", False):
    return DM
  if getattr(args, "groups", False):
    return GROUP
  return None


def draft(wa, chat, text, dry_run):
  text = text.strip()
  if not text:
    die("no draft text on stdin", 2)
  phone = chat["phone"]
  if phone:
    url = "whatsapp://send?" + urllib.parse.urlencode(
      {"phone": phone, "text": text}, quote_via=urllib.parse.quote)
    if dry_run:
      print(f"would open: {url}")
      return
    subprocess.run(["open", url], check=True)
    print(f"opened the chat with {chat['name']} with the draft typed in: press Enter in WhatsApp to send it")
    return
  if dry_run:
    print(f"would copy the draft to the clipboard and open WhatsApp at '{chat['name']}' by hand "
          f"({chat['kind']}, no phone number for a link)")
    return
  subprocess.run(["pbcopy"], input=text.encode(), check=True)
  subprocess.run(["open", "-a", "WhatsApp"], check=True)
  print(f"copied the draft to the clipboard: open '{chat['name']}' in WhatsApp, paste and send "
        f"(no direct link for a {'group' if chat['kind'] == 'group' else 'contact without a known number'})")


def main():
  parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  sub = parser.add_subparsers(dest="cmd", required=True)

  def common(p, since_default=None, limit_default=40):
    p.add_argument("--since", default=since_default)
    p.add_argument("--limit", type=int, default=limit_default)
    p.add_argument("--json", action="store_true")

  def kinds(p):
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dms", action="store_true")
    g.add_argument("--groups", action="store_true")

  p = sub.add_parser("chats", help="recent chats, newest first")
  common(p, limit_default=50)
  kinds(p)
  p.add_argument("--unread", action="store_true")

  p = sub.add_parser("read", help="messages in one chat, oldest first")
  common(p)
  p.add_argument("chat")

  p = sub.add_parser("search", help="messages containing TEXT")
  common(p, limit_default=30)
  p.add_argument("text")
  p.add_argument("--chat")

  p = sub.add_parser("mine", help="Ian's own sent messages, for the voice guide")
  common(p, limit_default=500)
  kinds(p)

  p = sub.add_parser("draft", help="put a draft (stdin) in front of Ian to send")
  p.add_argument("chat")
  p.add_argument("--dry-run", action="store_true")

  args = parser.parse_args()
  wa = WhatsApp()
  since = parse_since(getattr(args, "since", None))

  if args.cmd == "chats":
    items = wa.chats(since, args.unread, kind_arg(args), args.limit)
    as_json(items) if args.json else print_chats(items)
  elif args.cmd == "read":
    chat = wa.find_chat(args.chat)
    items = wa.messages(chat, since, args.limit)
    if args.json:
      as_json({"chat": chat, "messages": items})
    else:
      print(f"== {chat['name']} ({chat['kind']}, id {chat['id']})")
      print_messages(items)
  elif args.cmd == "search":
    chat = wa.find_chat(args.chat) if args.chat else None
    items = wa.search(args.text, chat, since, args.limit)
    as_json(items) if args.json else print_messages(items, show_chat=True)
  elif args.cmd == "mine":
    items = wa.mine(since, kind_arg(args), args.limit)
    as_json(items) if args.json else print_messages(items, show_chat=True)
  elif args.cmd == "draft":
    draft(wa, wa.find_chat(args.chat), sys.stdin.read(), args.dry_run)
  if args.cmd in ("chats", "search", "mine") and not items:
    sys.exit(1)


if __name__ == "__main__":
  main()
