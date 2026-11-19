"""Telegram helpers: load secrets, send messages, find your chat ID.

Run directly to test:
    python3 notify.py chatid   -> shows the chat ID of whoever messaged your bot
    python3 notify.py test     -> sends a test message to your phone
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"


def load_env():
    """Read KEY=VALUE lines from .env into os.environ (doesn't override real env vars,
    so GitHub Actions secrets win when running in the cloud)."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _token():
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or "paste-your" in token:
        sys.exit("TELEGRAM_BOT_TOKEN is missing. Put it in the .env file.")
    return token


def _call(method, params=None):
    url = f"https://api.telegram.org/bot{_token()}/{method}"
    data = urllib.parse.urlencode(params).encode() if params else None
    try:
        with urllib.request.urlopen(url, data=data, timeout=20) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        # Never print the URL: it contains the token.
        raise RuntimeError(f"Telegram error {e.code}: {body}") from None


def send_message(text):
    load_env()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not chat_id:
        sys.exit("TELEGRAM_CHAT_ID is missing. Run: python3 notify.py chatid")
    return _call("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    })


def find_chat_ids():
    result = _call("getUpdates")
    chats = {}
    for update in result.get("result", []):
        msg = update.get("message") or update.get("edited_message") or {}
        chat = msg.get("chat")
        if chat:
            chats[chat["id"]] = chat.get("first_name") or chat.get("title") or ""
    return chats


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test"
    if cmd == "chatid":
        chats = find_chat_ids()
        if not chats:
            print("No messages found. Open your bot in Telegram, send it 'hi', then run this again.")
        for cid, name in chats.items():
            print(f"Chat ID: {cid}   (from: {name})")
    elif cmd == "test":
        send_message("✅ PS5 Pro stock alert: test message. Your bot works!")
        print("Sent! Check Telegram on your phone.")
    else:
        print(__doc__)
