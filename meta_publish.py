#!/usr/bin/env python3
"""
meta_publish.py - post a finished Short as an Instagram Reel and a Facebook Page Reel.

  python3 meta_publish.py --video short.mp4 --meta short_meta.txt     # title line, then description
  python3 meta_publish.py --video reel.mp4 --meta reel_meta.txt --cover reel_cover.png --thumb-offset 4750
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
and stops, and any failure exits 0, so a Meta problem can never cost the day's YouTube upload
that ran before it. A failure is never quiet, though: it is a ::warning:: on the run's page
and a line in the run's summary, because a green run with no Reel on Instagram is what hid
the problem before.

The cover. Without one, Instagram showed the Reel's first frame, which is nearly empty (every
element waits for its spoken beat), so the Reels went up with a blank cover. --cover is a
1080 x 1920 PNG, a still of the Reel itself where the hook is whole on screen (the old
Short's own cover card on the fallback path). Instagram takes a cover only as a public URL,
so the PNG goes to the Page as an unpublished photo (upload_cover) and Instagram gets that
photo's address as cover_url. If that fails, Instagram is given --thumb-offset instead, the
same moment in milliseconds, and picks the frame itself. The Facebook reel gets the same PNG
as its preferred thumbnail once it is finished (set_fb_thumbnail). A cover that cannot be
set is a warning; the Reel still goes.

--check posts nothing. It confirms that the token is a Page token for META_PAGE_ID and that
META_IG_USER_ID is the Instagram account linked to that Page, and exits 1 if either is not
so (meta_check.yml runs it every week, so an expired token shows before a day is lost).

The fallback caption line is worded for the desk (UPSC_DESK, set by each repository's
workflow): the Essay desk's aspirants write an essay, the others an answer.
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, uuid

VERSION = os.environ.get("META_GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{VERSION}"
EVALUATE = "Write your own {work} and get it evaluated: evaluate.upscdesk.com (link in bio)"


def desk_work(text=""):
    """'essay' on the Essay desk, 'answer' elsewhere: UPSC_DESK first, else the caption itself"""
    desk = os.environ.get("UPSC_DESK", "").strip().lower()
    if desk:
        return "essay" if desk == "essay" else "answer"
    return "essay" if re.search(r"(?i)#UPSCEssay\b|\bthis essay\b", text) else "answer"


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


def _post_file(path, token, image, **params):
    """a multipart POST with the image file itself as 'source', so it never has to be public
    anywhere first; the token goes in the form, never in the address"""
    b = "upscdesk" + uuid.uuid4().hex
    fields = {**params, "access_token": token}
    body = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items())
    kind = "image/png" if image.lower().endswith(".png") else "image/jpeg"
    with open(image, "rb") as f:
        body += (f'--{b}\r\nContent-Disposition: form-data; name="source"; filename="{os.path.basename(image)}"\r\n'
                 f"Content-Type: {kind}\r\n\r\n").encode() + f.read() + f"\r\n--{b}--\r\n".encode()
    return _req(f"{GRAPH}/{path}", body=body, method="POST", timeout=120,
                headers={"Content-Type": f"multipart/form-data; boundary={b}"})


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
        text += "\n\n" + EVALUATE.format(work=desk_work(text))
    return text[:2150]          # Instagram allows 2,200 characters


def upload_cover(page_id, token, png):
    """The cover as an unpublished photo on the Page, and the address of its largest size:
    Instagram fetches a Reel's cover from a public URL, and this way the image need not be
    public anywhere else. Nothing appears on the Page. None, with a warning, on any failure."""
    if not png:
        return None
    if not os.path.isfile(png):
        warn(f"meta: the Reel's cover {png} is missing; Instagram gets the frame at thumb_offset instead")
        return None
    try:
        pid = _post_file(f"{page_id}/photos", token, png, published="false")["id"]
        images = _get(pid, token, fields="images").get("images") or []
        best = max(images, key=lambda i: int(i.get("width") or 0) * int(i.get("height") or 0), default={})
        if not best.get("source"):
            raise RuntimeError("the photo came back without an image address")
        print(f"meta: cover uploaded to the Page unpublished ({best.get('width')}x{best.get('height')})")
        return best["source"]
    except Exception as e:
        warn(f"meta: the Reel's cover could not be uploaded to the Page ({e}); Instagram gets the frame at thumb_offset instead")
        return None


def set_fb_thumbnail(video_id, token, png):
    """The PNG as the Facebook reel's preferred thumbnail. The reel may still be processing
    just after it is finished, so a refusal is tried again for about two minutes."""
    last = None
    for attempt in range(6):
        try:
            _post_file(f"{video_id}/thumbnails", token, png, is_preferred="true")
            print("meta: Facebook reel cover set")
            return True
        except Exception as e:
            last = e
            if attempt < 5: time.sleep(20)
    warn(f"meta: the Facebook reel's cover was not set (the reel is up with Facebook's own frame): {last}")
    return False


def _ig_container(video, caption, token, ig, **cover):
    c = _post(f"{ig}/media", token, media_type="REELS", upload_type="resumable", caption=caption, share_to_feed="true", **cover)
    cid, uri = c["id"], c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{VERSION}/{c['id']}"
    _rupload(uri, token, video)
    for _ in range(60):                          # up to ten minutes for Instagram to process it
        st = _get(cid, token, fields="status_code").get("status_code")
        if st == "FINISHED": return cid
        if st in ("ERROR", "EXPIRED"): raise RuntimeError(f"Instagram could not process the video ({st})")
        time.sleep(10)
    raise RuntimeError("Instagram was still processing after ten minutes")


def instagram(video, caption, token, ig, cover_url=None, thumb_ms=None):
    """cover_url when there is one; if Instagram will not take it, the container is made again
    with thumb_offset, so a bad cover never costs the Reel. Nothing is published until a
    container has finished, so the second try cannot post the Reel twice."""
    offset = {"thumb_offset": str(int(thumb_ms))} if thumb_ms is not None else {}
    try:
        cid = _ig_container(video, caption, token, ig, **({"cover_url": cover_url} if cover_url else offset))
    except Exception as e:
        if not cover_url:
            raise
        warn(f"meta: Instagram did not take the Reel's cover ({e}); trying again with the frame at thumb_offset")
        cid = _ig_container(video, caption, token, ig, **offset)
    return _post(f"{ig}/media_publish", token, creation_id=cid).get("id")


def facebook(video, caption, token, page, cover=None):
    s = _post(f"{page}/video_reels", token, upload_phase="start")
    vid = s["video_id"]
    _rupload(s.get("upload_url") or f"https://rupload.facebook.com/video-upload/{VERSION}/{vid}", token, video)
    _post(f"{page}/video_reels", token, video_id=vid, upload_phase="finish", video_state="PUBLISHED", description=caption)
    if cover and os.path.isfile(cover):
        set_fb_thumbnail(vid, token, cover)      # a warning at worst; the reel is already up
    return vid


def config():
    token, page, ig = (os.environ.get(k, "").strip() for k in ("META_PAGE_TOKEN", "META_PAGE_ID", "META_IG_USER_ID"))
    return token, page, ig


def check(token, page, ig):
    """Posts nothing. Problems as a list; empty means the next Reel can go out."""
    problems = []
    if not token: return ["META_PAGE_TOKEN is not set"]
    if not page: problems.append("META_PAGE_ID is not set")
    if not ig: problems.append("META_IG_USER_ID is not set")
    try:
        me = _get("me", token, fields="id,name")
        if page and me.get("id") != page:
            problems.append("the token is not a Page token for META_PAGE_ID (it belongs to something else)")
        else:
            print("meta: the token is the Page's own:", me.get("name"))
    except Exception as e:
        problems.append(f"the token was refused: {e}")
        return problems
    if page:
        try:
            linked = (_get(page, token, fields="name,instagram_business_account").get("instagram_business_account") or {}).get("id")
            if not linked: problems.append("no Instagram professional account is linked to the Page")
            elif ig and linked != ig: problems.append("META_IG_USER_ID is not the Instagram account linked to the Page")
        except Exception as e:
            problems.append(f"the Page could not be read: {e}")
    if ig:
        try:
            print("meta: Instagram:", _get(ig, token, fields="username").get("username"))
        except Exception as e:
            problems.append(f"the Instagram account could not be read: {e}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video"); ap.add_argument("--meta")
    ap.add_argument("--check", action="store_true", help="check the token and ids; post nothing; exit 1 on a problem")
    ap.add_argument("--cover", help="1080 x 1920 PNG for the Reel's cover on Instagram and Facebook")
    ap.add_argument("--thumb-offset", default="", help="the cover's moment in ms, Instagram's frame if the cover cannot be sent")
    a = ap.parse_args()
    token, page, ig = config()
    if a.check:
        problems = check(token, page, ig)
        for p in problems:
            print(f"::error::meta check: {p}")
        if not problems:
            print("meta: check passed; Instagram and Facebook are ready")
        return 1 if problems else 0
    if not token:
        warn("meta: not configured (no META_PAGE_TOKEN); the Reel did not go to Instagram or Facebook")
        return 0
    caption = caption_from(a.meta)
    thumb_ms = int(a.thumb_offset) if str(a.thumb_offset).strip().isdigit() else None
    cover_url = upload_cover(page, token, a.cover) if (a.cover and page and ig) else None
    if a.cover and not page:
        warn("meta: the Reel's cover was not sent: no META_PAGE_ID to hold it; Instagram gets the frame at thumb_offset")
    legs = (("Instagram", lambda: instagram(a.video, caption, token, ig, cover_url, thumb_ms), ig),
            ("Facebook", lambda: facebook(a.video, caption, token, page, a.cover), page))
    for name, fn, target in legs:
        if not target:
            warn(f"meta: no id for {name}; the Reel did not go there"); continue
        try:
            print(f"meta: {name} reel published: {fn()}")
        except Exception as e:
            warn(f"meta: {name} failed (the rest of the run is unaffected): {e}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:                       # never fail the caller, but never quietly
        warn(f"meta: skipped after an error: {e}")
        sys.exit(1 if "--check" in sys.argv else 0)
