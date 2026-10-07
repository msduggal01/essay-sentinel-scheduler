#!/usr/bin/env python3
"""
yt_meta.py - the words around every Essay desk upload: titles, descriptions, chapters,
hashtags, tags, captions, and the once-a-day check for Shorts.

Used by render_video.py (the long video's youtube_meta.txt and captions.srt), ops/reel_cut.py
(the Reel's reel_meta.txt and reel.srt), make_short.py (the old Short's short_meta.txt), and the
two uploaders (upload_youtube.py, upload_short.py).

Why it exists (channel audit, 7 October 2026): 32 Essay Shorts went up with the same title,
"Could you write this essay? Today's topic", because the topic slide's heading is often a label
("Today's Topic", "Today's Topic, Decoded") and the topic itself is only spoken. Long titles led
with "UPSC Essay Masterclass", which nobody searches for. So:

  titles       lead with the topic (or its key phrase) and "UPSC Essay"; the long title stays
               under 70 characters; the date and episode go to the description. Each meta file
               carries alternates after its Tags line, and the uploader takes the first one that
               is not already the title of a recent upload on the channel.
  descriptions two plain lines first that repeat the title's search words; chapters from 00:00
               built from the slide starts (at least three, each at least ten seconds); the three
               links; three to five specific hashtags.
  captions     an English SRT from the narration's word timings: cues of at most two lines of 42
               characters and at most six seconds.

Nothing here talks to YouTube except recent_titles() and short_already_today(), which the
uploaders call with their own client.
"""
import datetime
import json
import re

TELEGRAM = "https://t.me/upscdesk_essay"
EVALUATE = "https://evaluate.upscdesk.com"
SUBSCRIBE = "https://subscribe.upscdesk.com/essay/"
LONG_TITLE_MAX = 69          # "under 70 characters"
SHORT_TITLE_MAX = 100        # YouTube's own limit
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# a topic slide heading that names the slide, not the topic
_LABEL = re.compile(r"^\s*(today'?s|the|this)\s+(topic|proposition|essay|line|quote)\b", re.I)
# tags and hashtags that say nothing about the day's topic
_GENERIC = re.compile(r"upsc|\bessay|\bias\b|civil services|\bmains\b|prelims|preparation|strategy|\bcse\b|"
                      r"\b20\d\d\b|masterclass|\btopics?\b|answer writing|\bexam\b", re.I)


def clean(s):
    """plain words: no [breath] tags, no surrounding quotes, single spaces"""
    s = re.sub(r"\[[^\]]*\]", " ", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s.strip("\"'“”‘’ ").strip()


def _topic_slide(data):
    return next((s for s in data.get("slides", []) if s.get("type") == "topic_title"), {})


def essay_topic(data):
    """The day's essay topic as set, e.g. 'Her seat in the panchayat arrived decades before her
    place at the family table.' The thumbnail block carries it on every run so far; failing
    that, the topic slide's heading unless it is only a label; failing that, the line the
    topic slide speaks after 'topic:'; failing that, the key phrase."""
    t = clean((data.get("thumbnail") or {}).get("topic"))
    if t and len(t.split()) >= 4:
        return t
    sl = _topic_slide(data)
    h = clean(sl.get("heading"))
    if h and not _LABEL.match(h) and len(h.split()) >= 4:
        return h
    m = re.search(r"(?:topic|proposition)\b[^:.?]{0,80}:\s*(.+?[.?])(?:\s|$)", clean(sl.get("narration")), re.I)
    if m:
        s = m.group(1).strip()
        return s[0].upper() + s[1:]
    return t or h or key_phrase(data, fallback=False) or "Today's UPSC Essay topic"


def key_phrase(data, fallback=True):
    """The agent's short name for the topic, the middle of its video title
    ('UPSC Essay Masterclass | When the Ballot Outpaces the Home | 06 Oct 2026 (Ep 080)'),
    else its thumbnail text, else the topic's first words."""
    for part in str(data.get("video_title", "")).split("|"):
        p = re.sub(r"\(\s*Ep\.?\s*\d+\s*\)", "", part, flags=re.I).strip(" -:,")
        if not p or re.search(r"masterclass|essay desk|^ep\.?\s*\d+$|^\d{1,2}\s+\w{3,9}\s+\d{4}$|^upsc essay$", p, re.I):
            continue
        return clean(p)
    tt = clean(data.get("thumbnail_text"))
    if tt and len(tt.split()) >= 3:
        return tt
    if not fallback:
        return tt
    words = essay_topic(data).rstrip(".?").split()
    return " ".join(words[:7])


def episode_of(data):
    try:
        return f"{int(re.sub(r'[^0-9]', '', str(data.get('issue_no', ''))) or 0):03d}"
    except ValueError:
        return str(data.get("issue_no", ""))


def theme_of(data):
    return clean((data.get("thumbnail") or {}).get("theme"))


def section_of(data):
    s = clean((data.get("thumbnail") or {}).get("section"))
    if s:
        return s
    for b in _topic_slide(data).get("bullets") or []:
        m = re.search(r"Section\s+[AB]", b)
        if m:
            return m.group(0)
    return ""


# ----------------------------------------------------------------------------
# Titles
# ----------------------------------------------------------------------------
def norm_title(t):
    """what makes two titles 'the same': case, #Shorts, punctuation and spacing do not"""
    t = re.sub(r"#shorts\b", "", str(t), flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def _fit(core, limit, tail=""):
    """core + tail within limit; a core too long is cut at a word, never mid-word"""
    if len(core + tail) <= limit:
        return core + tail
    words, out = core.split(), ""
    for w in words:
        if len((out + " " + w).strip() + tail) > limit:
            break
        out = (out + " " + w).strip()
    return out.rstrip(",:;.") + tail if out else (core + tail)[:limit]


def long_titles(data):
    """The long video's title first, then alternates, all under 70 characters and distinct:
    'UPSC Essay: <topic> | how to write it' when the topic fits, else its key phrase."""
    topic = essay_topic(data).rstrip(".")
    key = key_phrase(data).rstrip(".")
    ep = episode_of(data)
    out = []
    tails = [" | how to write it", " | decode, thesis and structure", " | how to approach it", ""]
    for core in (topic, key):
        for tail in tails:
            t = f"UPSC Essay: {core}{tail}"
            if len(t) <= LONG_TITLE_MAX:
                out.append(t)
    out.append(_fit(f"UPSC Essay: {key}", LONG_TITLE_MAX, f" (Ep {ep})"))
    if len(out) < 2:                      # a key phrase too long for any form: cut at a word
        out.append(_fit(f"UPSC Essay: {key}", LONG_TITLE_MAX))
    return _distinct(out)


def short_titles(data):
    """The Reel's (or the old Short's) title first, then alternates: the topic itself, with
    'UPSC Essay', never the 'Could you write this essay?' line that all 32 Shorts shared."""
    topic = essay_topic(data).rstrip(".")
    key = key_phrase(data).rstrip(".")
    ep = episode_of(data)
    cands = [f"{topic} | UPSC Essay #Shorts",
             f"UPSC Essay: {topic} #Shorts",
             f"UPSC Essay: {key} | how to open it #Shorts",
             f"{key} | UPSC Essay opening #Shorts"]
    out = [t for t in cands if len(t) <= SHORT_TITLE_MAX]
    out.append(_fit(f"UPSC Essay: {key}", SHORT_TITLE_MAX, f" (Ep {ep}) #Shorts"))
    return _distinct(out)


def _distinct(titles):
    seen, out = set(), []
    for t in titles:
        k = norm_title(t)
        if t and k not in seen:
            seen.add(k)
            out.append(t)
    return out


def pick_title(candidates, taken):
    """the first candidate that is not the title of an earlier upload; when every one is
    taken (it has never happened), the first with a counter, so it still differs"""
    taken = {norm_title(t) for t in taken}
    for t in candidates:
        if norm_title(t) not in taken:
            return t
    base = candidates[0]
    for n in range(2, 50):
        t = re.sub(r"( #Shorts)?$", f" ({n})\\1", base, count=1)
        if norm_title(t) not in taken:
            return t
    return base


# ----------------------------------------------------------------------------
# Hashtags and tags
# ----------------------------------------------------------------------------
def camel(t):
    words = re.sub(r"[^0-9A-Za-z ]", " ", str(t)).split()
    return "".join(w[:1].upper() + w[1:] for w in words)


def specific_tags(data):
    """the day's own tags that name the topic, not the exam"""
    out = []
    for t in [theme_of(data)] + list(data.get("tags") or []):
        t = clean(t)
        if t and not _GENERIC.search(t) and t.lower() not in [o.lower() for o in out]:
            out.append(t)
    return out


def hashtags(data, short=False):
    """three to five, specific: #UPSCEssay, the theme, the topic's own tags (and #Shorts on a Short)"""
    hs = ["#UPSCEssay"] + (["#Shorts"] if short else [])
    for t in specific_tags(data):
        h = "#" + camel(t)
        if 3 < len(h) <= 26 and h.lower() not in [x.lower() for x in hs]:
            hs.append(h)
        if len(hs) >= 5:
            break
    for filler in ("#UPSCMains", "#EssayWriting"):
        if len(hs) < 3:
            hs.append(filler)
    return hs[:5]


def long_tags(data):
    """topic first, then the day's own tags, then the exam: at most 15 and 450 characters"""
    out = []
    for t in [key_phrase(data), essay_topic(data).rstrip(".")] + specific_tags(data) + \
             [t for t in (data.get("tags") or []) if _GENERIC.search(str(t))] + ["UPSC Essay", "UPSC Essay topic", "essay writing", "UPSC Mains"]:
        t = clean(t)
        if not t or len(t) > 100 or t.lower() in [o.lower() for o in out]:
            continue
        if sum(len(x) + 3 for x in out) + len(t) + 3 > 450 or len(out) >= 15:
            break
        out.append(t)
    return out


def short_tags(data, lenses=(), last="essay opening"):
    """five to eight, about the topic"""
    out = []
    for t in [key_phrase(data)] + specific_tags(data) + list(lenses) + ["UPSC Essay", "UPSC Essay topic", last]:
        t = clean(t)
        if t and len(t) <= 60 and t.lower() not in [o.lower() for o in out]:
            out.append(t)
    return out[:8]


# ----------------------------------------------------------------------------
# Chapters
# ----------------------------------------------------------------------------
def fmt_ts(seconds):
    s = int(seconds)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _settle(points, total, min_len=10.0):
    """sorted, first at 0, every chapter at least min_len seconds (a short one is folded into
    the one before it), the last one too"""
    pts = sorted({round(t, 2): ti for t, ti in points}.items())
    if not pts or pts[0][0] > 0:
        pts = [(0.0, "Introduction")] + [p for p in pts if p[0] > 0]
    out = [pts[0]]
    for t, ti in pts[1:]:
        if t - out[-1][0] < min_len:
            continue
        out.append((t, ti))
    while len(out) > 1 and total - out[-1][0] < min_len:
        out.pop()
    # whole seconds on the page: two chapters must not print the same second, or be under ten
    final = []
    for t, ti in out:
        if final and int(t) - int(final[-1][0]) < min_len:
            continue
        final.append((t, ti))
    return final


def chapters(data, starts, total):
    """[(seconds, title)] from the slide starts: 00:00 Introduction, the topic slide, then the
    agent's chapters at their slides. With fewer than three that last ten seconds, one per
    slide by its heading; with fewer than three still, none (YouTube would ignore them)."""
    slides = data.get("slides", [])
    pts = [(0.0, "Introduction")]
    ts = _topic_slide(data)
    if ts.get("id") in starts and starts[ts["id"]] > 0:
        pts.append((starts[ts["id"]], "The topic"))
    for ch in data.get("chapters") or []:
        sid = ch.get("slide_id")
        if sid in starts and clean(ch.get("title")):
            pts.append((starts[sid], clean(ch["title"])))
    out = _settle(pts, total)
    if len(out) < 3:
        per = [(starts[s["id"]], clean(s.get("heading")) or s.get("type", "").replace("_", " ").title())
               for s in slides if s.get("id") in starts]
        out = _settle(per, total)
    return out if len(out) >= 3 else []


# ----------------------------------------------------------------------------
# Descriptions
# ----------------------------------------------------------------------------
def _first_paragraph(text, limit=600):
    p = next((x.strip() for x in str(text or "").split("\n\n") if x.strip()), "")
    if len(p) > limit:
        p = p[:limit].rsplit(". ", 1)[0] + "."
    return p


def long_description(data, title, chaps, subscribe=SUBSCRIBE):
    topic = essay_topic(data)
    key = key_phrase(data)
    core = re.sub(r"^UPSC Essay:\s*", "", title).split(" | ")[0].split(" (Ep")[0].rstrip(".")
    sec, theme = section_of(data), theme_of(data)
    where = ", ".join(x for x in (sec, theme.lower() if theme else "") if x)
    L = [f"UPSC Essay: {core}, and how to write it. The topic decoded, one thesis held, "
         f"the dimensions, the anchors, and an opening and close you can use.",
         f"Topic: \"{topic.rstrip('.')}.\"" + (f" ({where})." if where else "")
         + f" The Essay Desk, episode {episode_of(data)}, {clean(data.get('date'))}."]
    para = _first_paragraph(data.get("video_description"))
    if para:
        L += ["", para]
    if chaps:
        L += ["", "Chapters"] + [f"{fmt_ts(t)} {ti}" for t, ti in chaps]
    L += ["",
          f"Write this essay and get it evaluated (five free every month): {EVALUATE}",
          f"The daily topic on Telegram: {TELEGRAM}",
          f"Two model essays with the examiner's commentary, three mornings a week: {subscribe}",
          "", " ".join(hashtags(data))]
    if key and key.lower() not in "\n".join(L).lower():
        L.insert(1, key)
    return "\n".join(L)


def short_description(data, decode="", lenses=(), verb="open"):
    topic = essay_topic(data).rstrip(".")
    L = [f"How to {verb} the UPSC Essay on \"{topic}.\""]
    if decode:
        L.append(f"What it asks: {clean(decode)}")
    if lenses:
        L.append("Read it through: " + ", ".join(clean(l) for l in lenses) + ".")
    L += ["",
          f"Write it, then get it evaluated (five free every month): {EVALUATE}",
          f"The full masterclass and the daily topic on Telegram: {TELEGRAM}",
          "", " ".join(hashtags(data, short=True))]
    return "\n".join(L)


def write_meta(path, titles, description, tags):
    """title, blank, description, blank, Tags:, then the alternates the uploader may need.
    Everything that reads these files stops at the Tags line (meta_publish.py included)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(titles[0] + "\n\n" + description.strip() + "\n\nTags: " + ", ".join(tags) + "\n")
        if len(titles) > 1:
            f.write("Alternates: " + " || ".join(titles[1:]) + "\n")


def parse_meta(path):
    """(title, description, tags, alternates) from a meta file written by write_meta (or the
    older form, which has no alternates)"""
    lines = open(path, encoding="utf-8").read().split("\n")
    title, tags, body, alts, after = lines[0].strip(), [], [], [], False
    for ln in lines[1:]:
        if after:
            if ln.startswith("Alternates:"):
                alts = [t.strip() for t in ln[len("Alternates:"):].split("||") if t.strip()]
            continue
        if ln.startswith("Tags:"):
            tags = [t.strip() for t in ln[len("Tags:"):].split(",") if t.strip()]
            after = True
            continue
        body.append(ln)
    return title, "\n".join(body).strip(), tags, alts


# ----------------------------------------------------------------------------
# Captions
# ----------------------------------------------------------------------------
def words_from_alignment(chars, starts, ends, offset=0.0, scale=1.0):
    """[(word, start, end)] from ElevenLabs' character alignment; audio tags such as
    [breath] are not words and are dropped. Times are (offset + t) * scale."""
    out, cur, t0, t1 = [], "", None, None
    def flush():
        w = re.sub(r"\[[^\]]*\]", "", cur).strip()
        if w and t0 is not None:
            out.append((w, (offset + t0) * scale, (offset + t1) * scale))
    in_tag = False
    for ch, st, en in zip(chars, starts, ends):
        if ch == "[":
            in_tag = True
        if ch.isspace() and not in_tag:
            flush(); cur, t0, t1 = "", None, None
            continue
        if not in_tag:
            if t0 is None:
                t0 = st
            t1 = en
        cur += ch
        if ch == "]":
            in_tag = False
    flush()
    return out


def _wrap2(text, width):
    """text as one line, or two balanced lines, each at most width; None if it cannot be"""
    if len(text) <= width:
        return [text]
    words, best = text.split(), None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if len(a) <= width and len(b) <= width:
            score = max(len(a), len(b))
            if best is None or score < best[0]:
                best = (score, [a, b])
    return best[1] if best else None


def _srt_time(t):
    ms = int(round(max(0.0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def cues(words, width=42, max_dur=6.0):
    """[(start, end, [line, line])]: as many words as fit two lines of width characters and
    max_dur seconds, a new cue after a full stop once the cue is half full"""
    out, cur = [], []
    def close():
        if cur:
            lines = _wrap2(" ".join(w for w, _, _ in cur), width) or [" ".join(w for w, _, _ in cur)[:width]]
            out.append([cur[0][1], cur[-1][2], lines])
    for w in words:
        trial = cur + [w]
        text = " ".join(x for x, _, _ in trial)
        if cur and (_wrap2(text, width) is None or w[2] - cur[0][1] > max_dur):
            close(); cur = [w]
        else:
            cur = trial
        if re.search(r"[.?!]$", w[0]) and len(" ".join(x for x, _, _ in cur)) >= width:
            close(); cur = []
    close()
    for i, c in enumerate(out):
        nxt = out[i + 1][0] if i + 1 < len(out) else None
        end = c[1] + 0.25                          # a beat to read the last word
        if nxt is not None:
            end = min(end, nxt - 0.02)
        c[1] = max(min(end, c[0] + max_dur), c[0] + 0.3)
        if nxt is not None and c[1] > nxt:
            c[1] = nxt
    return [tuple(c) for c in out]


def srt(words, width=42, max_dur=6.0):
    blocks = []
    for i, (a, b, lines) in enumerate(cues(words, width, max_dur), 1):
        blocks.append(f"{i}\n{_srt_time(a)} --> {_srt_time(b)}\n" + "\n".join(lines) + "\n")
    return "\n".join(blocks)


def check_srt(text, width=42, max_dur=6.0):
    """the faults in an SRT against the rules (empty when it is sound)"""
    errs = []
    def secs(s):
        h, m, rest = s.split(":"); sec, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000
    prev_end = 0.0
    for blk in [b for b in text.strip().split("\n\n") if b.strip()]:
        ln = blk.split("\n")
        a, b = [secs(x.strip()) for x in ln[1].split("-->")]
        body = ln[2:]
        if len(body) > 2: errs.append(f"cue {ln[0]}: {len(body)} lines")
        if any(len(x) > width for x in body): errs.append(f"cue {ln[0]}: a line over {width}")
        if b - a > max_dur + 1e-6: errs.append(f"cue {ln[0]}: {b - a:.2f}s")
        if b <= a: errs.append(f"cue {ln[0]}: ends before it starts")
        if a < prev_end - 1e-6: errs.append(f"cue {ln[0]}: overlaps the one before")
        prev_end = b
    return errs


# ----------------------------------------------------------------------------
# YouTube reads (the uploaders' own client)
# ----------------------------------------------------------------------------
def recent_titles(yt, pages=4):
    """the titles of the channel's last ~200 uploads (all three desks share the channel)"""
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    titles, token = [], None
    for _ in range(pages):
        r = yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=50,
                                    **({"pageToken": token} if token else {})).execute()
        titles += [i["snippet"]["title"] for i in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    return titles


def short_already_today(yt, playlist_title, now=None):
    """True when the desk's Shorts playlist had a video added today (India time)"""
    now = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(IST).date()
    req = yt.playlists().list(part="snippet", mine=True, maxResults=50)
    pid = None
    while req is not None and pid is None:
        resp = req.execute()
        for it in resp.get("items", []):
            if it["snippet"]["title"].strip().lower() == playlist_title.strip().lower():
                pid = it["id"]
                break
        else:
            req = yt.playlists().list_next(req, resp)
    if not pid:
        return False
    token = None
    for _ in range(20):
        r = yt.playlistItems().list(part="snippet", playlistId=pid, maxResults=50,
                                    **({"pageToken": token} if token else {})).execute()
        for it in r.get("items", []):
            at = it["snippet"].get("publishedAt", "")
            try:
                d = datetime.datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone(IST).date()
            except ValueError:
                continue
            if d == now:
                return True
        token = r.get("nextPageToken")
        if not token:
            break
    return False


if __name__ == "__main__":
    import sys
    d = json.load(open(sys.argv[1]))
    print("topic:", essay_topic(d))
    print("key:  ", key_phrase(d))
    print("long: ", long_titles(d))
    print("short:", short_titles(d))
    print("tags: ", hashtags(d), hashtags(d, short=True))
