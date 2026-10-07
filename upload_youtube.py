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
      [--captions build/issue_028/captions.srt]  # English captions, uploaded after the video
      [--dry-run]                  # print what would be sent; no credentials, nothing sent

The daily long video is the one upload a day that notifies subscribers (notifySubscribers
true); the Reel and the Short do not (upload_short.py), which keeps the shared channel inside
YouTube's three notifications a day. Its title is the first of the meta file's title and
alternates that is not already the title of a recent upload on the channel.

Prints the uploaded video URL.
"""
import argparse
import json
import os
import sys

import yt_meta

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    if "--dry-run" not in sys.argv:
        print("Missing libraries. Run:\n  pip3 install google-api-python-client google-auth")
        sys.exit(1)

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
EDUCATION_CATEGORY = "27"


def parse_meta(path):
    """youtube_meta.txt = title (line 1), blank, description+chapters, blank, 'Tags: a, b, c',
    then 'Alternates: ...' (yt_meta.write_meta)"""
    title, description, tags, _ = yt_meta.parse_meta(path)
    return title, description, tags


def warn(msg):
    """a warning GitHub shows on the run's page, and a line in the run's summary"""
    print(f"::warning::{msg}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as f:
                f.write(f"- {msg}\n")
        except OSError:
            pass


def upload_captions(yt, vid, srt):
    """English captions from the narration; a failure is a warning, the video stands"""
    if not srt:
        return
    if not os.path.exists(srt):
        warn(f"no captions file at {srt}; the video is up without captions")
        return
    try:
        yt.captions().insert(part="snippet",
                             body={"snippet": {"videoId": vid, "language": "en", "name": "English"}},
                             media_body=MediaFileUpload(srt)).execute()
        print("Captions uploaded.")
    except Exception as ex:
        warn(f"the video is on YouTube, but its captions were not uploaded: {str(ex)[:200]}")


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
    ap.add_argument("--captions", help="an SRT to upload as the English captions after the video")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the request and the captions; no credentials, nothing is sent")
    args = ap.parse_args()

    title, description, tags, alternates = yt_meta.parse_meta(args.meta)
    if args.dry_run:
        yt = None
    else:
        yt = build("youtube", "v3", credentials=creds_from_env())
        # never the title of an earlier upload: the channel's recent uploads, all three desks
        try:
            taken = yt_meta.recent_titles(yt)
            picked = yt_meta.pick_title([title] + alternates, taken)
            if picked != title:
                print(f"Title {title!r} is already on the channel; using {picked!r}")
            title = picked
        except Exception as ex:
            warn(f"the channel's recent titles could not be read ({str(ex)[:120]}); the title is not checked for repeats")

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

    if args.dry_run:
        print("DRY RUN: videos().insert(part='snippet,status', notifySubscribers=True, body=")
        print(json.dumps(body, indent=1, ensure_ascii=False))
        if args.captions:
            print(f"DRY RUN: then captions().insert from {args.captions}"
                  + ("" if os.path.exists(args.captions) else " (missing: it would be a warning)"))
        return

    print(f"Uploading: {title}")
    media = MediaFileUpload(args.video, chunksize=-1, resumable=True, mimetype="video/mp4")
    # the day's long video is the one upload that notifies subscribers
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media, notifySubscribers=True)

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

    upload_captions(yt, vid, args.captions)

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
