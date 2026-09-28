#!/usr/bin/env python3
"""
meta_publish.py - post a finished Short as an Instagram Reel and a Facebook Page Reel.

  python3 meta_publish.py --video short.mp4 --meta short_meta.txt     # title line, then description
  python3 meta_publish.py --video reel.mp4 --meta reel_meta.txt --cover reel_cover.png --thumb-offset 4750
  python3 meta_publish.py --carousel carousel_out --caption carousel_out/caption.txt --result r.json [--done r.json] [--dry-run]
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


# ------------------------------------------------------------------ carousels
# The day's carousel (carousel.yml): 2 to 10 PNG slides of one size, to Instagram as a
# CAROUSEL post, and to the Facebook Page as a link carousel. Instagram takes images only from
# a public address, so each slide goes to the Page first as an unpublished photo (nothing
# appears on the Page) and Instagram gets their addresses. A slide that cannot be uploaded
# stops both legs, so half a carousel is never posted. The token travels in the form body or
# the Authorization header, never in an address. --done is the result of an earlier run for
# the same day: a leg it already records is not posted again, so a re-run never posts twice.
#
# Facebook. A feed post with the photos attached showed as a grid of tiles, not as slides.
# The Facebook leg is now a link carousel (POST /{page}/feed with link, child_attachments,
# multi_share_optimized=false so the order stays ours, multi_share_end_card=false): the first
# slide with a swipe to the rest, every card linking to the evaluator. Link-carousel cards
# show square, so each slide is set on a 1080 x 1080 card in the desk's band colour
# (square_cards, into fb_cards/ next to the slides) and uploaded as an unpublished Page photo
# for its public address. Facebook lets only the verified owner of a link's domain set its
# picture, so until upscdesk.com is verified for the Page it refuses the carousel; on that,
# or on any other refusal, the leg falls back to one published photo of slide 1 with the
# caption and a line that the full carousel is on Instagram. The photo grid is never posted.

FB_LINK = "https://evaluate.upscdesk.com"
IG_HANDLE = "@upscdesk.official"
DESK_PRIMARY = {"gs": (0x3E, 0x2A, 0x52), "sociology": (0x1E, 0x3A, 0x5F), "essay": (0x7A, 0x2D, 0x3A)}
_NAME_BAD = re.compile("[\u2013\u2014\u2012\u2015]|\\s-+\\s|[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")


def _get_h(path, token, **params):
    """a GET with the token in the Authorization header, never in the address"""
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    return _req(f"{GRAPH}/{path}{q}", headers={"Authorization": f"OAuth {token}"})


def _png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"{os.path.basename(path)} is not a PNG")
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def carousel_slides(folder):
    """slide_01.png ... in order; 2 to 10 of them, all one size (Instagram crops a carousel to
    its first slide's shape)"""
    pngs = sorted(os.path.join(folder, f) for f in os.listdir(folder) if re.fullmatch(r"slide_\d+\.png", f))
    if not 2 <= len(pngs) <= 10:
        raise RuntimeError(f"{len(pngs)} slides in {folder}; a carousel takes 2 to 10")
    sizes = {_png_size(p) for p in pngs}
    if len(sizes) != 1:
        raise RuntimeError(f"the slides are not all one size: {sorted(sizes)}")
    return pngs


def carousel_caption(path):
    text = open(path, encoding="utf-8").read().strip()
    if re.search(r"(?i)link\s+in\s+(the\s+)?bio", text):
        raise RuntimeError("the caption says 'link in bio'; there is no link-in-bio page")
    if len(text) > 2200 or len(re.findall(r"#\w+", text)) > 30:
        raise RuntimeError("the caption is over Instagram's 2,200 characters or 30 hashtags")
    return text


def _page_photo(page_id, token, png, **fields):
    """a PNG to the Page's photos: the file itself as 'source', the token in the form body"""
    return _post_file(f"{page_id}/photos", token, png, **fields)


def upload_photo(page_id, token, png):
    """one image as an unpublished Page photo: (photo id, the address of its largest size, read
    with the token in a header)"""
    pid = _page_photo(page_id, token, png, published="false")["id"]
    images = _get_h(pid, token, fields="images").get("images") or []
    best = max(images, key=lambda i: int(i.get("width") or 0) * int(i.get("height") or 0), default={})
    if not best.get("source"):
        raise RuntimeError(f"the photo for {os.path.basename(png)} came back without an image address")
    return pid, best["source"]


def _ig_ready(cid, token, tries=60, pause=5):
    for _ in range(tries):
        st = _get_h(cid, token, fields="status_code").get("status_code")
        if st == "FINISHED": return
        if st in ("ERROR", "EXPIRED"): raise RuntimeError(f"Instagram could not process container {cid} ({st})")
        time.sleep(pause)
    raise RuntimeError(f"Instagram was still processing container {cid}")


def ig_carousel(urls, caption, token, ig):
    kids = []
    for u in urls:
        kids.append(_post(f"{ig}/media", token, image_url=u, is_carousel_item="true")["id"])
    for k in kids:
        _ig_ready(k, token)
    cid = _post(f"{ig}/media", token, media_type="CAROUSEL", children=",".join(kids), caption=caption)["id"]
    _ig_ready(cid, token)
    return _post(f"{ig}/media_publish", token, creation_id=cid).get("id")


def _desk(folder):
    """the desk the carousel is for: props.json's desk, else UPSC_DESK"""
    try:
        d = json.load(open(os.path.join(folder, "props.json"), encoding="utf-8")).get("desk")
    except (OSError, ValueError, AttributeError):
        d = None
    return str(d or os.environ.get("UPSC_DESK", "")).strip().lower()


def square_cards(pngs, outdir, desk=""):
    """each 1080 x 1350 slide scaled to the card's height (864 x 1080) and centred on a 1080 x
    1080 card in the slide's own band colour (its top-left pixel; the desk's primary if that
    pixel is page white). A square slide is copied as it is. Returns the cards' paths."""
    from PIL import Image                        # only the carousel path needs Pillow
    os.makedirs(outdir, exist_ok=True)
    cards = []
    for k, p in enumerate(pngs, 1):
        im = Image.open(p).convert("RGB")
        band = im.getpixel((0, 0))
        if sum(band) > 3 * 230:
            band = DESK_PRIMARY.get(desk, DESK_PRIMARY["gs"])
        scale = min(1080 / im.width, 1080 / im.height)
        w, h = round(im.width * scale), round(im.height * scale)
        card = Image.new("RGB", (1080, 1080), band)
        card.paste(im if (w, h) == im.size else im.resize((w, h), Image.LANCZOS), ((1080 - w) // 2, (1080 - h) // 2))
        out = os.path.join(outdir, f"card_{k:02d}.png")
        card.save(out, optimize=True)
        cards.append(out)
    return cards


def _name_ok(s):
    return bool(s) and not _NAME_BAD.search(s)


def _first_line_name(caption, limit=60):
    """the caption's first line, cut at a word boundary to limit characters (an ellipsis, and
    a closing quote when the cut leaves one open, count within the limit)"""
    line = re.sub(r"\s+", " ", (caption.strip().splitlines() or [""])[0]).strip()
    if len(line) <= limit:
        return line
    cut = line[:limit - 1]
    cut = cut[:cut.rfind(" ")] if " " in cut else cut[:limit - 2]
    cut = re.sub(r"[\s,;:.\u201c\"'(]+$", "", cut)
    return cut + "\u2026" + ("\u201d" if cut.count("\u201c") > cut.count("\u201d") else "")


def card_names(folder, caption, n):
    """slide 1: the caption's first line (60 characters at most); the others, their own short
    title or label from props.json (45 at most), else 'Slide N of M'. A name that has a dash or
    an emoji is not used."""
    try:
        slides = json.load(open(os.path.join(folder, "props.json"), encoding="utf-8")).get("slides") or []
    except (OSError, ValueError, AttributeError):
        slides = []
    if len(slides) != n:                         # the props do not match the slides: numbers only
        slides = []
    names = []
    for i in range(n):
        name = ""
        if i == 0:
            name = _first_line_name(caption)
        elif slides:
            for key in ("title", "label"):
                t = re.sub(r"\s+", " ", re.sub(r"[*_]", "", str(slides[i].get(key) or ""))).strip()
                if t and len(t) <= 45 and _name_ok(t):
                    name = t; break
        names.append(name if _name_ok(name) else f"Slide {i + 1} of {n}")
    return names


def link_carousel_fields(caption, pictures, names):
    """the Page feed request for a link carousel (the token is added by _post)"""
    kids = [{"link": FB_LINK, "picture": u, "name": nm} for u, nm in zip(pictures, names)]
    return {"message": caption, "link": FB_LINK, "child_attachments": json.dumps(kids, ensure_ascii=False),
            "multi_share_optimized": "false", "multi_share_end_card": "false"}


def fallback_caption(caption, n):
    """the caption with one line that the whole carousel is on Instagram, above the hashtags"""
    line = f"All {n} slides are on our Instagram, {IG_HANDLE}."
    paras = caption.strip().split("\n\n")
    if len(paras) > 1 and re.fullmatch(r"(#\w+\s*)+", paras[-1].strip()):
        return "\n\n".join(paras[:-1] + [line, paras[-1]])
    return caption.strip() + "\n\n" + line


def _refusal(e):
    msg = str(e)
    if re.search(r"(?i)owners? of the (url|link|domain)|ability to specify the picture|verif|domain|picture", msg):
        return "Facebook refused the cards' pictures (upscdesk.com is not verified as the Page's domain yet)"
    return "Facebook refused the link carousel"


def fb_carousel(pngs, folder, caption, token, page):
    """the Facebook leg: a link carousel of square cards, else one photo of slide 1. Returns
    the post id; raises only when both fail."""
    n = len(pngs)
    try:
        cards = square_cards(pngs, os.path.join(folder, "fb_cards"), _desk(folder))
        pictures = [upload_photo(page, token, c)[1] for c in cards]
        fields = link_carousel_fields(caption, pictures, card_names(folder, caption, n))
        pid = _post(f"{page}/feed", token, **fields).get("id")
        if not pid:
            raise RuntimeError("Facebook answered without a post id")
        print(f"::notice::meta: Facebook got the link carousel ({n} cards, first slide with a swipe to the rest)")
        return pid
    except Exception as e:
        why = f"{_refusal(e)}: {str(e)[:300]}"
    try:
        r = _page_photo(page, token, pngs[0], caption=fallback_caption(caption, n), published="true")
        pid = r.get("post_id") or r.get("id")
        if not pid:
            raise RuntimeError("Facebook answered without a post id")
    except Exception as e:
        raise RuntimeError(f"the single photo of slide 1 was not posted either ({str(e)[:300]}); first, {why}") from None
    warn(f"meta: Facebook got slide 1 as a single photo, not the link carousel. Why: {why}")
    return pid


def plan(folder, pngs, caption, legs):
    """dry run: the square cards built for real, and the requests the post would make"""
    n = len(pngs)
    try:
        cards = square_cards(pngs, os.path.join(folder, "fb_cards"), _desk(folder))
        print(f"meta: dry run: {len(cards)} square cards in {os.path.join(folder, 'fb_cards')}")
    except Exception as e:
        warn(f"meta: dry run: the Facebook cards could not be built ({e}); a real run would post slide 1 as a single photo")
        cards = []
    pics = [f"<public address of fb_cards/{os.path.basename(c)}, an unpublished Page photo>" for c in cards] or ["<card>"] * n
    fields = link_carousel_fields(caption, pics, card_names(folder, caption, n))
    shown = {**fields, "message": f"<the caption, {len(caption)} characters>", "child_attachments": json.loads(fields["child_attachments"])}
    print("meta: dry run: Facebook POST /{page}/feed " + json.dumps(shown, ensure_ascii=False, indent=1))
    print("meta: dry run: if Facebook refuses it, POST /{page}/photos with source=" + os.path.basename(pngs[0])
          + ", published=true, caption=<the caption and: " + f"All {n} slides are on our Instagram, {IG_HANDLE}.>")
    if "instagram" in legs:
        print(f"meta: dry run: Instagram: {n} carousel items, a CAROUSEL container, media_publish")


def post_carousel(folder, caption_path, result=None, done=None, dry_run=False):
    """posts the carousel in folder to Instagram and Facebook; returns {instagram, facebook} ids
    (None for a leg not posted). Warnings, never a failure."""
    state = {"instagram": None, "facebook": None}
    if done and os.path.isfile(done):
        try:
            state.update({k: v for k, v in json.load(open(done)).items() if k in state})
        except (OSError, ValueError):
            pass
    def save():
        if result:
            json.dump(state, open(result, "w"))
    try:
        pngs, caption = carousel_slides(folder), carousel_caption(caption_path)
    except Exception as e:
        warn(f"meta: carousel not posted: {e}")
        save(); return state
    token, page, ig = config()
    legs = [leg for leg, target in (("instagram", ig), ("facebook", page)) if not state[leg]]
    if dry_run:
        print(f"meta: dry run: {len(pngs)} slides of {_png_size(pngs[0])[0]}x{_png_size(pngs[0])[1]}, caption {len(caption)} characters; "
              f"would post to {', '.join(legs) or 'nothing (both legs already posted)'}; nothing was posted")
        plan(folder, pngs, caption, legs)
        save(); return state
    if not legs:
        print("meta: this carousel is already on Instagram and Facebook; not posting again")
        save(); return state
    if not token or not page:
        warn("meta: carousel not posted: META_PAGE_TOKEN or META_PAGE_ID is not set")
        save(); return state
    photos = []
    if "instagram" in legs and ig:
        try:
            photos = [upload_photo(page, token, p) for p in pngs]
            print(f"meta: {len(photos)} slides uploaded to the Page unpublished")
        except Exception as e:
            warn(f"meta: carousel not posted: a slide could not be uploaded ({e})")
            save(); return state
    for leg in legs:
        if leg == "instagram" and not ig:
            warn("meta: no META_IG_USER_ID; the carousel did not go to Instagram"); continue
        try:
            state[leg] = (ig_carousel([u for _, u in photos], caption, token, ig) if leg == "instagram"
                          else fb_carousel(pngs, folder, caption, token, page))
            print(f"meta: {leg} carousel published: {state[leg]}")
        except Exception as e:
            warn(f"meta: the {leg} carousel failed: {e}")
        save()
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video"); ap.add_argument("--meta")
    ap.add_argument("--check", action="store_true", help="check the token and ids; post nothing; exit 1 on a problem")
    ap.add_argument("--cover", help="1080 x 1920 PNG for the Reel's cover on Instagram and Facebook")
    ap.add_argument("--thumb-offset", default="", help="the cover's moment in ms, Instagram's frame if the cover cannot be sent")
    ap.add_argument("--carousel", help="a folder of slide_NN.png: post them as one carousel to Instagram and Facebook")
    ap.add_argument("--caption", help="the carousel's caption (a text file)")
    ap.add_argument("--result", help="the carousel's {instagram, facebook} ids (null when not posted) go here")
    ap.add_argument("--done", help="an earlier --result for the same carousel: legs it records are not posted again")
    ap.add_argument("--dry-run", action="store_true", help="check the carousel and its caption, build the Facebook cards; post nothing")
    a = ap.parse_args()
    if a.carousel:
        post_carousel(a.carousel, a.caption, a.result, a.done, a.dry_run)
        return 0
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
