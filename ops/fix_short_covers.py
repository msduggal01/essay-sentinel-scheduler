#!/usr/bin/env python3
"""
fix_short_covers.py - re-render and set the cover of Essay Shorts already on YouTube.

  python3 ops/fix_short_covers.py --since 2026-09-26 [--apply]

Lists the Shorts in the "Essay Desk - Shorts" playlist published on or after --since, renders
each one's cover with the desk's own copy (make_short.make_cover, the Short's title as its
line) and, only with --apply, sets it as the video's thumbnail. Without --apply it lists what
it would change and writes the covers to covers/ for a look.
"""
import argparse, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import make_short
from upload_short import creds_from_env, find_or_create_playlist
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def cover_line(title, info):
    """The essay topic for the cover: the title without its question and label, completed
    from the description when YouTube's 100-character title cut it off mid-word."""
    t = re.sub(r"\s*#\w+", "", title).split(" | ")[0].strip()
    t = re.sub(r"^Could you write this essay\?\s*", "", t)
    desc = ((info.get("items") or [{}])[0].get("snippet") or {}).get("description", "")
    i = desc.find(t)
    if t and i >= 0:
        rest = re.split(r"[\n|]", desc[i:])[0].strip()
        if len(rest) >= len(t):
            t = rest
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help="YYYY-MM-DD, UTC")
    ap.add_argument("--playlist", default="Essay Desk - Shorts")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    make_short.set_desk("essay")
    yt = build("youtube", "v3", credentials=creds_from_env(), cache_discovery=False)
    pid = find_or_create_playlist(yt, a.playlist)
    os.makedirs("covers", exist_ok=True)
    req = yt.playlistItems().list(part="snippet,contentDetails", playlistId=pid, maxResults=50)
    n = 0
    while req is not None:
        resp = req.execute()
        for it in resp.get("items", []):
            vid = it["contentDetails"]["videoId"]
            when = it["contentDetails"].get("videoPublishedAt") or it["snippet"].get("publishedAt", "")
            if when[:10] < a.since:
                continue
            title = it["snippet"]["title"]
            line = cover_line(title, yt.videos().list(part="snippet", id=vid).execute())
            out = f"covers/{vid}.png"
            make_short.make_cover({"events": [{"event": line}]}, out)
            n += 1
            if a.apply:
                yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(out, mimetype="image/png")).execute()
                print(f"cover set: https://youtu.be/{vid}  {when[:16]}  {title}")
            else:
                print(f"would set: https://youtu.be/{vid}  {when[:16]}  {title}")
        req = yt.playlistItems().list_next(req, resp)
    print(f"{n} Shorts since {a.since}" + ("" if a.apply else " (dry run: nothing changed)"))


if __name__ == "__main__":
    main()
