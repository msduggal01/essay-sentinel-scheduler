#!/usr/bin/env python3
"""
One-time helper: turn client_secret.json (downloaded from Google Cloud Console)
into a permanent YouTube refresh token for autonomous uploads.

SETUP (once):
  pip3 install google-auth-oauthlib google-api-python-client
  # put client_secret.json in this same folder, then:
  python3 get_refresh_token.py

It opens a browser, you log in to the channel's Google account and approve.
At the end it prints CLIENT_ID, CLIENT_SECRET and REFRESH_TOKEN. Save all three
(they are the credentials the daily uploader uses).
"""
import json
import os
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Missing libraries. Run:\n  pip3 install google-auth-oauthlib google-api-python-client")
    sys.exit(1)

# upload covers videos.insert + thumbnails.set; force-ssl lets us later read/reply
# to comments (for the email-in-comments subscription flow) without re-authorising.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = os.path.join(HERE, "client_secret.json")

if not os.path.exists(SECRET):
    print(f"client_secret.json not found in {HERE}")
    print("Download it from Google Cloud Console -> Credentials -> your OAuth client -> Download JSON,")
    print("save it as client_secret.json in this folder, then re-run.")
    sys.exit(1)

flow = InstalledAppFlow.from_client_secrets_file(SECRET, SCOPES)
# access_type=offline + prompt=consent guarantees a refresh_token is returned
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

info = json.load(open(SECRET))
node = info.get("installed", info.get("web", {}))

print("\n" + "=" * 70)
print("SUCCESS. Save these three values securely (you will paste them as secrets).")
print("=" * 70)
print("CLIENT_ID     :", node.get("client_id"))
print("CLIENT_SECRET :", node.get("client_secret"))
print("REFRESH_TOKEN :", creds.refresh_token)
print("=" * 70)

# also write them to a local file you can copy from (keep it private, do not commit)
with open(os.path.join(HERE, "youtube_credentials.txt"), "w") as f:
    f.write("CLIENT_ID=" + str(node.get("client_id")) + "\n")
    f.write("CLIENT_SECRET=" + str(node.get("client_secret")) + "\n")
    f.write("REFRESH_TOKEN=" + str(creds.refresh_token) + "\n")
print("Also saved to youtube_credentials.txt (keep private, never commit).")
