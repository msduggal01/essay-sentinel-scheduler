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
and stops, and any failure exits 0, so a Meta problem can never cost the day's YouTube upload
that ran before it. A failure is never quiet, though: it is a ::warning:: on the run's page
and a line in the run's summary, because a green run with no Reel on Instagram is what hid
the problem before.

--check posts nothing. It confirms that the token is a Page token for META_PAGE_ID and that
META_IG_USER_ID is the Instagram account linked to that Page, and exits 1 if either is not
so (meta_check.yml runs it every week, so an expired token shows before a day is lost).

The fallback caption line is worded for the desk (UPSC_DESK, set by each repository's
workflow): the Essay desk's aspirants write an essay, the others an answer.
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

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
    for name, fn, target in (("Instagram", instagram, ig), ("Facebook", facebook, page)):
        if not target:
            warn(f"meta: no id for {name}; the Reel did not go there"); continue
        try:
            print(f"meta: {name} reel published: {fn(a.video, caption, token, target)}")
        except Exception as e:
            warn(f"meta: {name} failed (the rest of the run is unaffected): {e}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:                       # never fail the caller, but never quietly
        warn(f"meta: skipped after an error: {e}")
        sys.exit(1 if "--check" in sys.argv else 0)
