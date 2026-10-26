#!/usr/bin/env python3
"""obs-auto-record.py: run by launchd every 20 seconds (see com.ianmiell.obs-auto-record.plist and
install-obs-auto-record.sh).

If a call is live and OBS isn't recording, start recording: through obs-websocket
(localhost:4455, no auth) when OBS is running, or by launching OBS with --startrecording when it
isn't. A call is live when
  - Zoom's meeting process (CptHost) is running, or
  - a browser tab (Chrome, Safari, Arc, Edge, Brave) is on a meeting URL: a Google Meet code
    (meet.google.com/abc-defg-hij, or the meet.google.com/meet/abc-defg-hij Meet redirects to),
    the Zoom web client, a Teams meeting, a Slack huddle, Whereby, Jitsi or Webex.
A recording this script started is stopped once no call has been seen for STOP_AFTER checks in a
row. A recording Ian started by hand is never stopped.

Must be quick and safe to run repeatedly. The first browser check makes macOS ask to allow
control of each browser; allow it.
"""

import base64
import json
import os
import re
import socket
import subprocess
import sys
import time

OBS_PORT = int(os.environ.get("OBS_PORT", "4455"))
STATE_DIR = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
                         "personal-assistant")
STATE = os.path.join(STATE_DIR, "obs-auto-record.json")
STOP_AFTER = 3   # checks with no call before stopping a recording this script started

MEETING_URL = re.compile(
    r"meet\.google\.com/(meet/)?[a-z]{3}-[a-z]{4}-[a-z]{3}"
    r"|zoom\.us/wc/"
    r"|teams\.(microsoft|live)\.com/.*(meetup-join|/meet/|light-meetings|/v2/\?meetingjoin)"
    r"|app\.slack\.com/huddle/"
    r"|whereby\.com/[^/?#]+"
    r"|meet\.jit\.si/[^/?#]+"
    r"|\.webex\.com/(meet|wbxmjs|webappng)",
    re.I)
BROWSERS = {   # process name -> AppleScript application name
    "Google Chrome": "Google Chrome",
    "Safari": "Safari",
    "Arc": "Arc",
    "Microsoft Edge": "Microsoft Edge",
    "Brave Browser": "Brave Browser",
}


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def running(name):
    return subprocess.run(["/usr/bin/pgrep", "-x", name], capture_output=True).returncode == 0


def browser_urls(app):
    script = (f'tell application "{app}" to get URL of every tab of every window'
              if app != "Safari" else
              'tell application "Safari" to get URL of every tab of every window')
    try:
        out = subprocess.run(["/usr/bin/osascript", "-e", script],
                             capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return []
    return [u.strip() for u in out.stdout.split(",")]


def live_call():
    if running("CptHost"):
        return "Zoom"
    for proc, app in BROWSERS.items():
        if not running(proc):
            continue   # telling a closed browser anything would launch it
        for url in browser_urls(app):
            if MEETING_URL.search(url):
                return f"{app}: {url}"
    return None


class OBS:
    """Just enough of a websocket client for obs-websocket 5 requests."""

    def __init__(self):
        self.sock = socket.create_connection(("127.0.0.1", OBS_PORT), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            "GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Protocol: obswebsocket.json\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ConnectionError("obs-websocket closed during handshake")
            head += chunk
        self._recv()   # Hello
        self._send({"op": 1, "d": {"rpcVersion": 1, "eventSubscriptions": 0}})
        self._recv()   # Identified

    def _read(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("obs-websocket closed")
            data += chunk
        return data

    def _recv(self):
        head = self._read(2)
        n = head[1] & 127
        if n == 126:
            n = int.from_bytes(self._read(2), "big")
        elif n == 127:
            n = int.from_bytes(self._read(8), "big")
        return json.loads(self._read(n))

    def _send(self, obj):
        payload = json.dumps(obj).encode()
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + n.to_bytes(2, "big"))
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def request(self, kind):
        self._send({"op": 6, "d": {"requestType": kind, "requestId": kind}})
        while True:
            msg = self._recv()
            if msg.get("op") == 7:
                return msg["d"].get("responseData") or {}


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(state, f)


def main():
    state = load_state()
    call = live_call()

    if call:
        state["missed"] = 0
        if not running("OBS"):
            log(f"Call live ({call}); launching OBS to record")
            subprocess.run(["/usr/bin/open", "-a", "OBS", "--args", "--startrecording"])
            state["started_by_us"] = True
        else:
            obs = OBS()
            if not obs.request("GetRecordStatus").get("outputActive"):
                log(f"Call live ({call}); starting recording")
                obs.request("StartRecord")
                state["started_by_us"] = True
    elif state.get("started_by_us"):
        state["missed"] = state.get("missed", 0) + 1
        if state["missed"] >= STOP_AFTER:
            if running("OBS"):
                obs = OBS()
                if obs.request("GetRecordStatus").get("outputActive"):
                    log("No call for a while; stopping the recording this script started")
                    obs.request("StopRecord")
            state = {}

    save_state(state)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ConnectionError) as e:
        log(f"OBS unreachable: {e}")
        sys.exit(0)
