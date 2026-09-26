#!/usr/bin/env python3
"""
meta_publish.py - post a finished Short as an Instagram Reel and a Facebook Page Reel.

  python3 meta_publish.py --video short.mp4 --meta short_meta.txt     # title line, then description
  python3 meta_publish.py --check                                      # token and ids only; posts nothing

One account serves all three desks (GS, Sociology, Essay), and this file is the same in all
three repositories. It uses the Graph API with a Facebook Page token: that one token
publishes to the Page and to the Instagram professional account linked to it, and a Page
token made from a long-lived user token does not expire.

  META_PAGE_TOKEN   the Page access token (repository secret)
  META_PAGE_ID      the Facebook Page id
  META_IG_USER_ID   the Instagram professional account id linked to that Page

Both uploads send the file itself (resumable upload to rupload.facebook.com), so the video
never has to be public anywhere first. Best-effort by design: without the secrets it says so
and stops, and any failure is printed and exits 0, so a Meta problem can never cost the
day's YouTube upload that ran before it.
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

VERSION = os.environ.get("META_GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{VERSION}"
EVALUATE = "Write your own answer and get it evaluated: evaluate.upscdesk.com (link in bio)"


def _req(url, data=None, headers=None, method=None, body=None, timeout=300):
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method or ("POST" if body is not None else "GET"))
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read() or b"{}")
    except urllib.error.HTTPError as e:
        # the token is in the query string or the Authorization header, never in this message
        raise RuntimeError(f"HTTP {e.code}: {e.read()[:400].decode('utf-8', 'replace')}") from None


def _get(path, token, **params):
    return _req(f"{GRAPH}/{path}?" + urllib.parse.urlencode({**params, "access_token": token}))


def _post(path, token, **params):
    return _req(f"{GRAPH}/{path}", data={**params, "access_token": token})


def _rupload(url, token, video):
    size = os.path.getsize(video)
    with open(video, "rb") as f:
        return _req(url, body=f.read(), method="POST", timeout=900,
                    headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)})


def caption_from(meta_path):
    """The Short's own title and description, fitted for Instagram: links cannot be clicked
    in a caption, so addresses become 'link in bio', and every post ends on the evaluator."""
    lines = open(meta_path, encoding="utf-8").read().strip().split("\n")
    body = []
    for ln in lines[1:]:
        if ln.startswith("Tags:"): break          # YouTube's tags line, not for a caption
        body.append(ln)
    title, desc = lines[0].strip(), "\n".join(body).strip()
    text = f"{title}\n\n{desc}" if desc else title
    text = re.sub(r"https?://\S+", "(link in bio)", text)
    text = re.sub(r"(?i)#shorts\b", "#reels", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if "evaluate.upscdesk.com" not in text:
        text += "\n\n" + EVALUATE
    return text[:2150]          # Instagram allows 2,200 characters


def instagram(video, caption, token, ig):
    c = _post(f"{ig}/media", token, media_type="REELS", upload_type="resumable", caption=caption, share_to_feed="true")
    cid, uri = c["id"], c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{VERSION}/{c['id']}"
    _rupload(uri, token, video)
    for _ in range(60):                          # up to ten minutes for Instagram to process it
        st = _get(cid, token, fields="status_code").get("status_code")
        if st == "FINISHED": break
        if st in ("ERROR", "EXPIRED"): raise RuntimeError(f"Instagram could not process the video ({st})")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram was still processing after ten minutes")
    return _post(f"{ig}/media_publish", token, creation_id=cid).get("id")


def facebook(video, caption, token, page):
    s = _post(f"{page}/video_reels", token, upload_phase="start")
    vid = s["video_id"]
    _rupload(s.get("upload_url") or f"https://rupload.facebook.com/video-upload/{VERSION}/{vid}", token, video)
    _post(f"{page}/video_reels", token, video_id=vid, upload_phase="finish", video_state="PUBLISHED", description=caption)
    return vid


def config():
    token, page, ig = (os.environ.get(k, "").strip() for k in ("META_PAGE_TOKEN", "META_PAGE_ID", "META_IG_USER_ID"))
    return token, page, ig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video"); ap.add_argument("--meta")
    ap.add_argument("--check", action="store_true", help="check the token and ids; post nothing")
    a = ap.parse_args()
    token, page, ig = config()
    if not token:
        print("meta: not configured (no META_PAGE_TOKEN); skipping Instagram and Facebook")
        return 0
    if a.check:
        print("meta: Page:", _get(page, token, fields="name").get("name"))
        print("meta: Instagram:", _get(ig, token, fields="username").get("username"))
        return 0
    caption = caption_from(a.meta)
    for name, fn, target in (("Instagram", instagram, ig), ("Facebook", facebook, page)):
        if not target:
            print(f"meta: no id for {name}; skipped"); continue
        try:
            print(f"meta: {name} reel published: {fn(a.video, caption, token, target)}")
        except Exception as e:
            print(f"meta: {name} failed (the rest of the run is unaffected): {e}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:                       # never fail the caller
        print(f"meta: skipped after an error: {e}")
        sys.exit(0)
