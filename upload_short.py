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
      [--cover reel_cover.png --thumb-offset 4750]
      [--no-playlist]

--cover is the Reel's cover (a 1080 x 1920 still of the Reel where its hook is whole on
screen): it is the YouTube thumbnail when no --thumbnail is given, and with --crosspost it
goes to meta_publish.py as the Instagram and Facebook cover. On the old Short's path
--thumbnail (make_short.make_cover's card) is the cover as well. A thumbnail or cover that
does not take is a warning on the run and a line in its summary; the upload stands.

A vertical video <= 3 min with #Shorts in the title/description is auto-classified
by YouTube as a Short. Prints the uploaded video URL.

A Reel or a Short never notifies subscribers (notifySubscribers false): the day's long video
does, and the shared channel stays inside YouTube's three notifications a day. Its title is
the first of the meta file's title and alternates that is not already the title of a recent
upload on the channel.

  --captions reel.srt        English captions, uploaded after the video (a failure is a warning)
  --done-file F              the video's id is written to F the moment the upload is accepted,
                             so the old Short's fallback in the same job knows a Short went up
  --once-per-day open|closed skip the upload when the playlist already had a video added today
                             (India time) and print "ALREADY TODAY:"; "open" uploads anyway when
                             the playlist cannot be read, "closed" (the old Short's fallback) does not
  --dry-run                  print the request; no credentials, nothing sent
"""
import argparse
import json
import os
import sys

import yt_meta


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

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    if "--dry-run" not in sys.argv:
        print("Missing libraries. Run:\n  pip3 install google-api-python-client google-auth")
        # non-blocking: do not fail the daily run for a Shorts dependency
        sys.exit(0)

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
EDUCATION_CATEGORY = "27"
SHORTS_PLAYLIST = "Sociology Desk - Shorts"


def parse_meta(path):
    """short_meta.txt = title (line 1), blank, description, blank, 'Tags: a, b, c', then
    'Alternates: ...' (yt_meta.write_meta)"""
    title, description, tags, _ = yt_meta.parse_meta(path)
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
    ap.add_argument("--crosspost", action="store_true",
                    help="after YouTube, also post it as an Instagram and Facebook Reel (meta_publish.py)")
    ap.add_argument("--cover", help="the Reel's cover PNG: the YouTube thumbnail unless --thumbnail is given, and the "
                                    "Instagram and Facebook cover with --crosspost")
    ap.add_argument("--thumb-offset", default="",
                    help="the cover's moment in ms, passed to meta_publish.py for Instagram's fallback frame")
    ap.add_argument("--no-playlist", action="store_true",
                    help="skip adding the Short to the Shorts playlist")
    ap.add_argument("--captions", help="an SRT to upload as the English captions after the video")
    ap.add_argument("--done-file", help="write the video's id here as soon as the upload is accepted")
    ap.add_argument("--once-per-day", choices=["open", "closed"],
                    help="skip when the playlist already had a video added today (India time)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the request; no credentials, nothing is sent")
    args = ap.parse_args()

    if not os.path.exists(args.video):
        print(f"No Short to upload at {args.video}; skipping (non-blocking).")
        return 0
    if not os.path.exists(args.meta):
        print(f"No meta at {args.meta}; skipping (non-blocking).")
        return 0

    title, description, tags, alternates = yt_meta.parse_meta(args.meta)
    title, description = ensure_shorts(title, description)

    try:
        yt = None if args.dry_run else build("youtube", "v3", credentials=creds_from_env())

        # one Reel or Short a day on the desk's playlist: a rerun, or the old Short after a Reel
        # that went up, must not add a second
        if args.once_per_day and not args.dry_run:
            try:
                if yt_meta.short_already_today(yt, args.playlist):
                    print(f"ALREADY TODAY: {args.playlist!r} already had a video added today; nothing uploaded")
                    return 0
            except Exception as ex:
                if args.once_per_day == "closed":
                    warn(f"the Shorts playlist could not be read ({str(ex)[:120]}), so no Short was uploaded")
                    return 0
                warn(f"the Shorts playlist could not be read ({str(ex)[:120]}); uploading anyway")

        # never the title of an earlier upload: the channel's recent uploads, all three desks
        if not args.dry_run:
            try:
                picked = yt_meta.pick_title([title] + [ensure_shorts(a, "")[0] for a in alternates],
                                            yt_meta.recent_titles(yt))
                if picked != title:
                    print(f"Title {title!r} is already on the channel; using {picked!r}")
                title = picked
            except Exception as ex:
                warn(f"the channel's recent titles could not be read ({str(ex)[:120]}); the title is not checked for repeats")

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

        if args.dry_run:
            print("DRY RUN: videos().insert(part='snippet,status', notifySubscribers=False, body=")
            print(json.dumps(body, indent=1, ensure_ascii=False))
            if args.captions:
                print(f"DRY RUN: then captions().insert from {args.captions}"
                      + ("" if os.path.exists(args.captions) else " (missing: it would be a warning)"))
            return 0

        print(f"Uploading Short: {title}")
        media = MediaFileUpload(args.video, chunksize=-1, resumable=True, mimetype="video/mp4")
        # a Short never notifies: the day's long video is the one notification
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media, notifySubscribers=False)
        response = None
        while response is None:
            progress, response = req.next_chunk()
            if progress:
                print(f"  {int(progress.progress() * 100)}%")
        vid = response["id"]
        print("Uploaded. Video ID:", vid)
        if args.done_file:
            try:
                with open(args.done_file, "w") as f:
                    f.write(vid + "\n")
            except OSError as ex:
                warn(f"could not record the upload in {args.done_file}: {ex}")

        thumb = args.thumbnail or args.cover
        if thumb and os.path.exists(thumb):
            try:
                yt.thumbnails().set(videoId=vid,
                                    media_body=MediaFileUpload(thumb)).execute()
                print("Thumbnail set.")
            except Exception as ex:
                warn(f"the Short is on YouTube, but its thumbnail was not set: {str(ex)[:200]}")
        elif thumb:
            warn(f"no thumbnail at {thumb}; YouTube picks the Short's frame itself")

        if args.captions:
            if not os.path.exists(args.captions):
                warn(f"no captions file at {args.captions}; the Short is up without captions")
            else:
                try:
                    yt.captions().insert(part="snippet",
                                         body={"snippet": {"videoId": vid, "language": "en", "name": "English"}},
                                         media_body=MediaFileUpload(args.captions)).execute()
                    print("Captions uploaded.")
                except Exception as ex:
                    warn(f"the Short is on YouTube, but its captions were not uploaded: {str(ex)[:200]}")

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
        if args.crosspost:
            # its own process, best-effort: Instagram or Facebook can never undo the YouTube upload
            import subprocess
            cover = args.cover or args.thumbnail
            mp = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "meta_publish.py"),
                                 "--video", args.video, "--meta", args.meta]
                                + (["--cover", cover] if cover else [])
                                + (["--thumb-offset", str(args.thumb_offset)] if str(args.thumb_offset).strip() else []),
                                capture_output=True, text=True)
            print((mp.stdout + mp.stderr).strip())
    except Exception as ex:
        # best-effort: never break the daily run because of the Short
        print("Short upload failed (non-blocking):", str(ex))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
