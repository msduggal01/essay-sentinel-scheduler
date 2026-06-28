#!/usr/bin/env python3
"""
Post a free-text announcement / message to the Essay Desk Telegram channel.

By default it REMOVES the "Comment" button from the announcement (announcements are
not meant for discussion). It does this by deleting the post's auto-mirrored copy in
the linked discussion group. Videos (posted via post_telegram.py) are untouched, so
they keep their Comment button.

REQUIREMENT for comment-removal: the bot must be an ADMIN of the discussion group
("UPSC Desk - Essay Chat") with "Delete Messages" permission.

USAGE:
  export TELEGRAM_BOT_TOKEN="..."   export TELEGRAM_CHANNEL="@upscdesk_essay"
  python3 post_announcement.py --text "Your message"
  python3 post_announcement.py --file message.txt
  python3 post_announcement.py --text "..." --pin
  python3 post_announcement.py --text "..." --allow-comments   # keep the Comment button
"""
import argparse, os, sys, time
try:
    import requests
except ImportError:
    print("Run: pip3 install requests"); sys.exit(1)

ap = argparse.ArgumentParser()
g = ap.add_mutually_exclusive_group(required=True)
g.add_argument("--text")
g.add_argument("--file")
ap.add_argument("--pin", action="store_true")
ap.add_argument("--preview", action="store_true", help="allow link previews (default off)")
ap.add_argument("--allow-comments", action="store_true", help="keep the Comment button (default: remove it)")
args = ap.parse_args()

token = os.environ.get("TELEGRAM_BOT_TOKEN")
channel = os.environ.get("TELEGRAM_CHANNEL")
if not token or not channel:
    print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL."); sys.exit(1)

text = open(args.file, encoding="utf-8").read().strip() if args.file else args.text
API = f"https://api.telegram.org/bot{token}"

r = requests.post(f"{API}/sendMessage",
                  data={"chat_id": channel, "text": text,
                        "disable_web_page_preview": not args.preview}, timeout=60).json()
if not r.get("ok"):
    print("Error:", r); sys.exit(1)
mid = r["result"]["message_id"]
print("Posted to channel ✓  message_id:", mid)

# remove the Comment button by deleting the auto-mirrored copy in the discussion group
if not args.allow_comments:
    time.sleep(3)  # give Telegram a moment to mirror the post into the group
    try:
        ups = requests.get(f"{API}/getUpdates", params={"timeout": 5, "allowed_updates": '["message"]'}, timeout=30).json()
        found = False
        for upd in reversed(ups.get("result", [])):
            m = upd.get("message") or {}
            if m.get("is_automatic_forward") and m.get("text", "").strip() == text.strip():
                d = requests.post(f"{API}/deleteMessage",
                                  data={"chat_id": m["chat"]["id"], "message_id": m["message_id"]}, timeout=30).json()
                print("Comment button removed ✓" if d.get("ok") else ("Could not remove: " + str(d)))
                found = True
                break
        if not found:
            print("Note: couldn't find the discussion-group copy. Is the bot an ADMIN of the group with delete rights?")
    except Exception as e:
        print("Comment-strip skipped:", str(e))

if args.pin:
    p = requests.post(f"{API}/pinChatMessage",
                      data={"chat_id": channel, "message_id": mid, "disable_notification": True}, timeout=60).json()
    print("Pinned ✓" if p.get("ok") else ("Pin failed: " + str(p)))
