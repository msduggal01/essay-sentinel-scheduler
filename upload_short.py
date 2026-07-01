#!/usr/bin/env python3
"""
Upload one rendered vertical Short to YouTube, reusing the SAME OAuth as
upload_youtube.py (no new app, no new secret). Best-effort / non-blocking: a
failure here must never break the main brief/video/telegram run, so this script
exits 0 even on most errors (mirrors the additive "Step 8.5" pattern).

Needs the same three env vars as upload_youtube.py:
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

USAGE
  pip3 install google-api-python-client google-auth
  export YT_CLIENT_ID=...  YT_CLIENT_SECRET=...  YT_REFRESH_TOKEN=...
  python3 upload_short.py \
      --video build/issue_030/short/short_issue_030.mp4 \
      --meta  build/issue_030/short/short_meta.txt \
      --privacy private          # private | unlisted | public  (default: private)
      [--thumbnail path.png]
      [--no-playlist]

A vertical video <= 3 min with #Shorts in the title/description is auto-classified
by YouTube as a Short. Prints the uploaded video URL.
"""
import argparse
import os
import sys

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    print("Missing libraries. Run:\n  pip3 install google-api-python-client google-auth")
    # non-blocking: do not fail the daily run for a Shorts dependency
    sys.exit(0)

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
EDUCATION_CATEGORY = "27"
SHORTS_PLAYLIST = "Sociology Desk - Shorts"


def parse_meta(path):
    """short_meta.txt = title (line 1), blank, description, blank, 'Tags: a, b, c'."""
    lines = open(path, encoding="utf-8").read().split("\n")
    title = lines[0].strip()
    tags = []
    body = []
    for ln in lines[1:]:
        if ln.startswith("Tags:"):
            tags = [t.strip() for t in ln[len("Tags:"):].split(",") if t.strip()]
            break
        body.append(ln)
    description = "\n".join(body).strip()
    return title, description, tags


def ensure_shorts(title, description):
    """Reinforce Short classification: #Shorts in title (if it fits) and description."""
    if "#shorts" not in title.lower():
        cand = (title + " #Shorts")
        title = cand if len(cand) <= 100 else title
    if "#shorts" not in description.lower():
        description = description + "\n\n#Shorts"
    return title, description


def creds_from_env():
    cid = os.environ.get("YT_CLIENT_ID")
    csec = os.environ.get("YT_CLIENT_SECRET")
    rt = os.environ.get("YT_REFRESH_TOKEN")
    if not (cid and csec and rt):
        print("Set YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN in the environment.")
        # non-blocking
        sys.exit(0)
    return Credentials(token=None, refresh_token=rt, client_id=cid, client_secret=csec,
                       token_uri=TOKEN_URI, scopes=SCOPES)


def find_or_create_playlist(yt, title):
    req = yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req is not None:
        resp = req.execute()
        for item in resp.get("items", []):
            if item["snippet"]["title"].strip().lower() == title.strip().lower():
                return item["id"]
        req = yt.playlists().list_next(req, resp)
    created = yt.playlists().insert(part="snippet,status", body={
        "snippet": {"title": title,
                    "description": "Daily 30-45s Sociology Optional hooks for UPSC Mains. "
                                   "Full brief on Telegram @upscdesk_sociology."},
        "status": {"privacyStatus": "public"}
    }).execute()
    print("Created playlist:", title)
    return created["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    ap.add_argument("--thumbnail")
    ap.add_argument("--publish-at",
                    help="ISO8601 UTC (e.g. 2026-07-02T09:30:00Z): schedule the public "
                         "release; the video is uploaded private until then. Used to "
                         "stagger the day's Shorts.")
    ap.add_argument("--playlist", default=SHORTS_PLAYLIST,
                    help="playlist to file the Short under (Essay reuse passes its own)")
    ap.add_argument("--no-playlist", action="store_true",
                    help="skip adding the Short to the Shorts playlist")
    args = ap.parse_args()

    if not os.path.exists(args.video):
        print(f"No Short to upload at {args.video}; skipping (non-blocking).")
        return 0
    if not os.path.exists(args.meta):
        print(f"No meta at {args.meta}; skipping (non-blocking).")
        return 0

    title, description, tags = parse_meta(args.meta)
    title, description = ensure_shorts(title, description)

    try:
        yt = build("youtube", "v3", credentials=creds_from_env())

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags,
                "categoryId": EDUCATION_CATEGORY,
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
            },
            "status": {
                # a scheduled publish must be uploaded private until publishAt
                "privacyStatus": "private" if args.publish_at else args.privacy,
                "selfDeclaredMadeForKids": False,
            },
        }
        if args.publish_at:
            body["status"]["publishAt"] = args.publish_at

        print(f"Uploading Short: {title}")
        media = MediaFileUpload(args.video, chunksize=-1, resumable=True, mimetype="video/mp4")
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            progress, response = req.next_chunk()
            if progress:
                print(f"  {int(progress.progress() * 100)}%")
        vid = response["id"]
        print("Uploaded. Video ID:", vid)

        if args.thumbnail and os.path.exists(args.thumbnail):
            try:
                yt.thumbnails().set(videoId=vid,
                                    media_body=MediaFileUpload(args.thumbnail)).execute()
                print("Thumbnail set.")
            except Exception as ex:
                print("Thumbnail set failed (Short still uploaded):", str(ex))

        if not args.no_playlist:
            try:
                pid = find_or_create_playlist(yt, args.playlist)
                yt.playlistItems().insert(part="snippet", body={
                    "snippet": {"playlistId": pid,
                                "resourceId": {"kind": "youtube#video", "videoId": vid}}
                }).execute()
                print("Added to playlist:", args.playlist)
            except Exception as ex:
                print("Playlist add failed (Short still uploaded):", str(ex))

        print("URL: https://youtu.be/" + vid)
        print("Studio: https://studio.youtube.com/video/" + vid + "/edit")
    except Exception as ex:
        # best-effort: never break the daily run because of the Short
        print("Short upload failed (non-blocking):", str(ex))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
