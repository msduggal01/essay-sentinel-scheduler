#!/usr/bin/env python3
"""
Upload one rendered video to YouTube using stored OAuth credentials.

Needs three env vars (from get_refresh_token.py):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

USAGE
  pip3 install google-api-python-client google-auth
  export YT_CLIENT_ID=...   YT_CLIENT_SECRET=...   YT_REFRESH_TOKEN=...
  python3 upload_youtube.py \
      --video  ../video_pipeline/build/issue_028/video_issue_028.mp4 \
      --meta   ../video_pipeline/build/issue_028/youtube_meta.txt \
      --privacy private            # private | unlisted | public  (default: private)
      [--thumbnail path.png]
      [--publish-at 2026-06-24T01:30:00Z]   # schedule (implies privacy=private)

Prints the uploaded video URL.
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
    sys.exit(1)

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
EDUCATION_CATEGORY = "27"


def parse_meta(path):
    """youtube_meta.txt = title (line 1), blank, description+chapters, blank, 'Tags: a, b, c'."""
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


def creds_from_env():
    cid = os.environ.get("YT_CLIENT_ID")
    csec = os.environ.get("YT_CLIENT_SECRET")
    rt = os.environ.get("YT_REFRESH_TOKEN")
    if not (cid and csec and rt):
        print("Set YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN in the environment.")
        sys.exit(1)
    return Credentials(token=None, refresh_token=rt, client_id=cid, client_secret=csec,
                       token_uri=TOKEN_URI, scopes=SCOPES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    ap.add_argument("--thumbnail")
    ap.add_argument("--publish-at", help="ISO8601 UTC, e.g. 2026-06-24T01:30:00Z (schedules; forces private)")
    ap.add_argument("--playlist", default="The Essay Desk - UPSC Essay Masterclass",
                    help="playlist title to add the video to (found by name, created if missing)")
    args = ap.parse_args()

    title, description, tags = parse_meta(args.meta)
    yt = build("youtube", "v3", credentials=creds_from_env())

    status = {
        "privacyStatus": "private" if args.publish_at else args.privacy,
        "selfDeclaredMadeForKids": False,
    }
    if args.publish_at:
        status["publishAt"] = args.publish_at

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": EDUCATION_CATEGORY,
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": status,
    }

    print(f"Uploading: {title}")
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
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(args.thumbnail)).execute()
            print("Thumbnail set.")
        except Exception as ex:
            # custom thumbnails require a phone-verified channel; don't let this block the playlist step
            print("Thumbnail skipped (channel not verified for custom thumbnails?):", str(ex)[:120])

    # add to the playlist (found by title, created if missing)
    if args.playlist:
        try:
            pid = find_or_create_playlist(yt, args.playlist)
            yt.playlistItems().insert(part="snippet", body={
                "snippet": {"playlistId": pid,
                            "resourceId": {"kind": "youtube#video", "videoId": vid}}
            }).execute()
            print("Added to playlist:", args.playlist)
        except Exception as ex:
            print("Playlist add failed (video still uploaded):", str(ex))

    print("URL: https://youtu.be/" + vid)
    print("Studio: https://studio.youtube.com/video/" + vid + "/edit")


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
                    "description": "UPSC Essay writing masterclasses: decode the topic, build the dimensions, deploy the anchors, and master the craft of a top essay."},
        "status": {"privacyStatus": "public"}
    }).execute()
    print("Created playlist:", title)
    return created["id"]


if __name__ == "__main__":
    main()
