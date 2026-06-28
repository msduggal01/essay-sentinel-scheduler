#!/usr/bin/env python3
"""
Post a rendered Essay Desk masterclass video to its Telegram channel, with a
caption built from the video_script JSON.

SETUP (one-time):
  pip3 install requests
  export TELEGRAM_BOT_TOKEN="123456:ABC..."         # @BotFather (reuse upscdesk_poster_bot)
  export TELEGRAM_CHANNEL="@upscdesk_essay"         # the NEW Essay Desk channel handle
  export ESSAY_SUBSCRIBE_URL="https://...netlify.app/"  # the Essay subscribe page

USAGE:
  python3 post_telegram.py \
      --video build/issue_030/video_issue_030.mp4 \
      --json  video_script_issue_030.json \
      [--youtube https://youtu.be/XXXX]             # optional, adds the YouTube link

Notes:
  - Telegram Bot API uploads up to 50 MB per video; your files (~16-25 MB) fit.
  - Caption is capped at 1024 chars (Telegram limit) and trimmed automatically.
"""
import argparse, json, os, sys

try:
    import requests
except ImportError:
    print("Run: pip3 install requests")
    sys.exit(1)

SUBSCRIBE = os.environ.get("ESSAY_SUBSCRIBE_URL", "https://essaydesk.netlify.app/")

def build_caption(data, youtube=None):
    """HTML link-card caption: bold heading, a daily one-liner hook, blank line
    between every section, and the enquiry email highlighted. The YouTube URL is
    placed so Telegram renders its landscape preview card. parse_mode = HTML."""
    import html as H
    esc = lambda s: H.escape(str(s), quote=False)
    L = []
    L.append("<b>📘 " + esc(data["video_title"]) + "</b>")

    hook = (data.get("telegram_hook") or "").strip()
    if hook:
        L.append("")
        L.append("<i>" + esc(hook) + "</i>")

    if youtube:
        L.append("")
        L.append("▶️ Watch the full breakdown: " + youtube)

    L.append("")
    L.append("📌 <b>Today's masterclass:</b>")
    for ch in data.get("chapters", []):
        L.append("• " + esc(ch["title"]))

    L.append("")
    L.append("🎯 The full brief - three model essays of 1000 to 1200 words, the dimensions maps, the anchor banks and the model intros and conclusions - goes to subscribers only.")
    L.append("Subscribe: " + SUBSCRIBE)

    L.append("")
    L.append("✉️ For any enquiry, write to us at:")
    L.append("<b>team@upscdesk.com</b>")

    L.append("")
    tags = [t.replace(" ", "") for t in data.get("tags", [])][:6]
    if tags:
        L.append(" ".join("#" + t for t in tags))
    return "\n".join(L)[:4000]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", help="only needed for file-upload fallback (no --youtube)")
    ap.add_argument("--json", required=True)
    ap.add_argument("--youtube")
    ap.add_argument("--thumb", help="local image to use as the post thumbnail (else YouTube's thumbnail)")
    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL")
    if not token or not channel:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL in the environment.")
        sys.exit(1)

    data = json.load(open(args.json))
    caption = build_caption(data, args.youtube)

    # LINK-CARD mode: post a text message whose first link is the YouTube URL, so
    # Telegram renders its landscape preview card with the readable caption.
    if args.youtube:
        print(f"Posting YouTube link card to {channel} ...")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, data={"chat_id": channel, "text": caption, "parse_mode": "HTML",
                                     "disable_web_page_preview": False}, timeout=60)
    else:
        # Fallback: no YouTube URL -> upload the video file directly.
        size_mb = os.path.getsize(args.video) / 1e6
        print(f"No --youtube given; uploading file {args.video} ({size_mb:.0f} MB) to {channel} ...")
        url = f"https://api.telegram.org/bot{token}/sendVideo"
        with open(args.video, "rb") as vf:
            r = requests.post(url, data={"chat_id": channel, "caption": caption,
                                         "supports_streaming": True},
                              files={"video": vf}, timeout=600)
    out = r.json()
    if out.get("ok"):
        print("Posted to Telegram ✓  message_id:", out["result"].get("message_id"))
    else:
        print("Telegram error:", out)
        sys.exit(1)

if __name__ == "__main__":
    main()
