#!/usr/bin/env python3
"""set_thumbnail.py - set a published video's YouTube thumbnail.

  python3 set_thumbnail.py VIDEO_ID thumb.png      (needs YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN)

For a video that went out with the wrong thumbnail (copied from the Sociology desk, 15 Oct 2026).
"""
import sys

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from upload_youtube import creds_from_env

vid, png = sys.argv[1], sys.argv[2]
yt = build("youtube", "v3", credentials=creds_from_env())
yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(png, mimetype="image/jpeg" if png.lower().endswith((".jpg", ".jpeg")) else "image/png")).execute()
print(f"thumbnail set on https://youtu.be/{vid}")
