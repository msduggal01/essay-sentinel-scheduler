#!/usr/bin/env python3
"""
thumb_v3.py - the desk thumbnails v3 (approved 15 Oct 2026): the format F1 to F7 for a day's
video, chosen by its content type and the desk's recent formats, and the props for
remotion/src/DeskThumbV3.tsx. The same file is in all three desk repos.

  python3 ops/thumb_v3.py <sociology|gs|essay> script.json [--video prelims|mains]
          [--history state.json] [--out props.json] [--state-out state.json]
          [--plate subject.jpg] [--format F5] [--no-llm]

Exit 0 with the props written; exit 3 when no format fits the day (the caller then draws the
T1 to T6 fallback with the compact header, as before). Never raises past main().

How a format is chosen (docs/THUMBNAILS.md):
  1. The day's content type: one small Claude call picks it from the desk's list; without a key,
     or after three bad replies, the desk's default.
  2. The formats the day can fill: each needs its own fields in the script (two thinkers for
     Versus, marks before and after for Proof, ...). Nothing is invented.
  3. The rotation: the content type's first choice, unless it was the desk's previous format; then
     its second; neither when both were used in the last two videos; no format more than twice in
     five; and the Ladder (the light surface) when the last five had none and the day can fill it.
  4. The words: one small Claude call per format, checked in code (word counts, the accent inside
     the hook, every number from the script, no dashes, emojis, "!" or hype), three tries; formats
     that can be written in code fall back to that, the others pass to the next format.
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.request

MODEL = os.environ.get("THUMB_MODEL", "claude-sonnet-5")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MATRIX = {
    "current_affairs": ("F1", "F4"),
    "sociology_topic": ("F3", "F2"),
    "concept": ("F6", "F4"),
    "thinkers": ("F1", "F2"),
    "essay_topic": ("F6", "F2"),
    "essay_structure": ("F7", "F3"),
    "answer_writing": ("F5", "F7"),
    "gs_current_affairs": ("F4", "F3"),
    "gs_laws": ("F7", "F5"),
    "pyq": ("F5", "F3"),
    "geography_ir": ("F4", "F2"),
}
TYPE_NOTES = {
    "current_affairs": "the news story itself is the draw; a thinker explains it",
    "sociology_topic": "a standing syllabus topic (caste, family, religion, kinship, work) read through several thinkers",
    "concept": "one sociological concept carries the day, seen in the news",
    "thinkers": "a thinker, or a clash between two thinkers, carries the day",
    "essay_topic": "the essay topic itself, decoded",
    "essay_structure": "how to build the essay: openings, dimensions, structure",
    "answer_writing": "how an answer gains marks: the average answer against the better one",
    "gs_current_affairs": "the week's news for GS, one issue or the whole set",
    "gs_laws": "a law, scheme or reform: what changed",
    "pyq": "a question UPSC has asked before",
    "geography_ir": "a place, a map or a relation between countries",
}
TYPES = {
    ("sociology", ""): ["current_affairs", "sociology_topic", "concept", "thinkers", "answer_writing"],
    ("essay", ""): ["essay_topic", "essay_structure", "answer_writing"],
    ("gs", "prelims"): ["gs_current_affairs", "geography_ir", "gs_laws"],
    ("gs", "mains"): ["answer_writing", "gs_laws", "pyq"],
}
DEFAULT = {("sociology", ""): "current_affairs", ("essay", ""): "essay_topic",
           ("gs", "prelims"): "gs_current_affairs", ("gs", "mains"): "answer_writing"}
DATED = {"current_affairs", "gs_current_affairs", "geography_ir"}     # rule 08: issue and date only on these
MAX_WORDS = 6
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍⬀-⯿]")
DASH = re.compile(r"[‒-―−]|--|\s-\s")
BANNED = re.compile(r"\b(scripts?|candidates?|shocking|secret|insane|guaranteed|topper)\b", re.I)
NUMW = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
        "eighteen": 18, "nineteen": 19, "twenty": 20, "twentyfive": 25, "thirty": 30}
ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV", "one": "I", "two": "II", "three": "III", "four": "IV"}
SMALL = {"a", "an", "the", "of", "and", "in", "on", "for", "to", "as", "at", "with", "by", "from", "or"}


def log(msg):
    print(f"thumb_v3: {msg}", file=sys.stderr, flush=True)


# ------------------------------------------------------------------ small helpers
def words(t):
    return [w for w in str(t).split() if w.strip()]


GENERIC = {"subjects", "subject", "questions", "question", "lenses", "lens", "dimensions", "steps", "three", "four", "five",
           "today", "week", "weekly", "daily", "prelims", "mains", "upsc", "news", "current", "affairs", "with", "from", "that", "this"}


def norm(t):
    return " ".join(re.findall(r"[a-z0-9']+", str(t).lower().replace("’", "'")))


def nice_date(t):
    import datetime
    t = str(t or "").strip()
    for f in ("%d %B %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            x = datetime.datetime.strptime(t, f)
            return f"{x.day} {x.strftime('%B %Y')}"
        except ValueError:
            pass
    return t


def issue_of(d):
    return re.sub(r"\D", "", str(d.get("issue_no", ""))).lstrip("0") or str(d.get("issue_no", "")).strip()


PARTICLES = {"de", "da", "van", "von", "du", "le", "la", "di", "del"}


def surname(name):
    ws = [w for w in re.split(r"\s+", re.sub(r"[(),]", " ", str(name)).strip()) if w]
    ws = [w for w in ws if not re.fullmatch(r"([A-Z]\.)+[A-Z]?\.?|[A-Z]", w) and w.lower() not in PARTICLES]
    return ws[-1].strip(".") if ws else ""


def nums_in(t):
    out = []
    for tok in re.findall(r"\d+|[a-z]+", str(t).lower()):
        if tok.isdigit(): out.append(int(tok))
        elif tok in NUMW: out.append(NUMW[tok])
    return out


def digits_ok(text, src):
    """every number written in `text` appears in the source (rule 07)"""
    s = re.sub(r"[,\s]", "", src)
    for n in re.findall(r"\d[\d,.]*", str(text)):
        if re.sub(r"[,.]$", "", n.replace(",", "")) not in s: return False
    return True


def flat(x):
    if isinstance(x, dict): return " ".join(flat(v) for v in x.values())
    if isinstance(x, list): return " ".join(flat(v) for v in x)
    return str(x)


def short(t, cap):
    """at most `cap` words, cut at a natural break, never ending on a small word"""
    t = re.sub(r"\s+", " ", str(t)).strip(" ,.;:")
    w = t.split()
    if len(w) <= cap: return t
    for sep in (": ", ", ", " and ", " as ", " in ", " of "):
        i = t.lower().find(sep)
        if 0 < i and 1 < len(t[:i].split()) <= cap: return t[:i]
    w = w[:cap]
    while len(w) > 1 and w[-1].lower() in SMALL: w.pop()
    return " ".join(w)


def years_out(t):
    return re.sub(r"\b(19|20)\d\d\b", " ", str(t))


# ------------------------------------------------------------------ what the day's script holds
LABELS = re.compile(r"^\s*(average(\s+(script|answer))?|topper(\s+(script|answer))?|top\s+(script|answer))\s*[:,.]?\s*", re.I)


def unlabel(t):
    """'Average script narrates the judgment' -> 'Narrates the judgment' (no script or topper on a thumbnail)"""
    t = LABELS.sub("", str(t)).strip()
    return t[:1].upper() + t[1:]


def soc_facts(d):
    slides = d.get("slides") or []
    blocks, cur = [], None
    for sl in slides:
        t = sl.get("type")
        if t == "topic_title":
            if cur: blocks.append(cur)
            cur = {"event": re.sub(r"^Event \w+\s*[:.-]\s*", "", sl.get("heading", "")).strip(), "bullets": sl.get("bullets") or [],
                   "narration": sl.get("narration", ""), "concept": "", "thinker": None, "bridge": None, "question": None}
        elif cur is None:
            continue
        elif t == "concept" and not cur["concept"]:
            cur["concept"] = (sl.get("concept") or sl.get("heading", "")).strip()
        elif t == "thinker" and not cur["thinker"]:
            name = (sl.get("thinker") or sl.get("heading", "").split(":")[0]).strip()
            if name: cur["thinker"] = {"name": name, "idea": (sl.get("concept") or sl.get("heading", "").split(":")[-1]).strip(),
                                       "bullets": sl.get("bullets") or [], "heading": sl.get("heading", "")}
        elif t == "answer_bridge" and not cur["bridge"]:
            cur["bridge"] = sl
        elif t == "question" and not cur["question"]:
            cur["question"] = sl
    if cur: blocks.append(cur)
    blocks = [b for b in blocks if b["event"]]
    lead = next((b for b in blocks if b["thinker"] and b["question"]), None) or next((b for b in blocks if b["thinker"]), None) \
        or (blocks[0] if blocks else None)
    names, seen = [], set()
    for b in blocks:
        if b["thinker"] and surname(b["thinker"]["name"]).lower() not in seen:
            seen.add(surname(b["thinker"]["name"]).lower()); names.append(b["thinker"])
    f = {"blocks": blocks, "lead": lead, "thinkers": names, "src": flat(slides) + " " + flat([d.get("video_title"), d.get("tags")])}
    # the marks: "Fourteen Marks versus Nineteen Marks" over "Twenty marks, Paper 2"
    for b in ([lead] if lead else []) + [x for x in blocks if x is not lead]:
        br = b.get("bridge")
        if not br: continue
        n = nums_in(br.get("heading", ""))
        tot = None
        for q in (b.get("question") or {}).get("bullets", []) or []:
            m = re.search(r"(\d+|[a-z]+)\s+marks", str(q).lower())
            if m: tot = int(m.group(1)) if m.group(1).isdigit() else NUMW.get(m.group(1))
        if len(n) == 2 and tot and n[0] < n[1] <= tot:
            top = next((unlabel(x) for x in br.get("bullets", []) if re.match(r"\s*(topper|top\s)", x, re.I)), "")
            f["marks"] = {"before": n[0], "after": n[1], "outOf": tot, "block": b, "note": top}
            break
    for b in ([lead] if lead else []) + blocks:
        br = (b or {}).get("bridge") or {}
        avg = next((unlabel(x) for x in br.get("bullets", []) if re.match(r"\s*average", x, re.I)), "")
        top = next((unlabel(x) for x in br.get("bullets", []) if re.match(r"\s*(topper|top\s)", x, re.I)), "")
        if avg and top:
            f["swap"] = {"old": avg, "new": top, "block": b}
            break
    return f


def soc_paper(b):
    for x in (b or {}).get("bullets", []) if b else []:
        m = re.match(r"\s*paper\s*(\d|one|two)\b", str(x), re.I)
        if m: return f"Paper {ROMAN[m.group(1).lower()]}"
    return "Sociology Optional"


def _content(d, layout):
    return next((s.get("content") or {} for s in d.get("slides", []) if s.get("layout") == layout), {})


def gs_facts(d, video):
    slides = d.get("slides") or []
    f = {"src": flat([s.get("content") for s in slides]) + " " + flat([d.get("video_title"), d.get("tags")]),
         "cold": _content(d, "cold_open"), "video": video}
    if video == "prelims":
        secs = []
        for s in slides:
            if s.get("layout") == "prelims_question":
                sec = str((s.get("content") or {}).get("section", "")).strip()
                if sec and sec not in secs: secs.append(sec)
        f["sections"] = secs
        f["stems"] = [(s.get("content") or {}).get("stem", "") for s in slides if s.get("layout") == "prelims_question"]
        f["statements"] = [st.get("text", "") for s in slides if s.get("layout") == "prelims_question"
                           for st in ((s.get("content") or {}).get("statements") or []) if isinstance(st, dict)]
        f["pill"] = "Prelims"
    else:
        qc = _content(d, "question_card")
        f["question"] = qc.get("question", "")
        tag = str(qc.get("tag1", ""))
        m = re.search(r"\b(?:GS\s*PAPER|PAPER|GS)\s*(I{1,3}|IV|\d)\b", tag, re.I)
        f["pill"] = f"GS {m.group(1).upper() if not m.group(1).isdigit() else ROMAN.get(m.group(1), m.group(1))}" if m else "GS Mains"
        bs = _content(d, "band_shift")
        sheet = _content(d, "answer_sheet")
        tot = nums_in(sheet.get("label", ""))
        if bs.get("before") is not None and bs.get("after") is not None and len(tot) >= 2:
            b, a, o = int(bs["before"]), int(bs["after"]), tot[-1]
            if b < a <= o:
                rows = bs.get("rows") or []
                f["marks"] = {"before": b, "after": a, "outOf": o, "note": short((rows[0] or {}).get("head", ""), 6) if rows else "",
                              "sheet": f"{f['pill']} · {sheet.get('q', '')}".strip(" ·")}
        pairs = (_content(d, "word_swaps").get("pairs") or [])
        if pairs and pairs[0].get("a") and pairs[0].get("b"):
            f["swap"] = {"old": pairs[0]["a"], "new": pairs[0]["b"]}
        lines = _content(d, "statement_cards").get("lines") or []
        if len(lines) > 1 and lines[1].get("text"): f["topic_line"] = short(lines[1]["text"], 4)
        bal = _content(d, "balance")
        if bal.get("left") and bal.get("right"):
            f["balance"] = bal
    return f


def essay_facts(d):
    slides = d.get("slides") or []
    th = d.get("thumbnail") or {}
    f = {"src": flat(slides) + " " + flat(th) + " " + str(d.get("video_title", "")), "topic": th.get("topic") or "",
         "theme": th.get("theme") or "", "pill": th.get("section") or "Essay Paper"}
    for s in slides:                                    # "Political: file culture ..." x 3 or more
        labs = [m.group(1).strip() for b in (s.get("bullets") or []) for m in [re.match(r"\s*([A-Z][A-Za-z ]{2,18}):\s+\S", str(b))] if m]
        labs = [x for x in labs if x.lower() not in ("hook", "close", "opening", "closing", "topic", "thesis")]
        if len(labs) >= 3:
            f["dimensions"] = labs[:4]; break
    avoid = next((re.sub(r"^\s*avoid\s+", "", b, flags=re.I) for s in slides for b in (s.get("bullets") or []) if re.match(r"\s*avoid\s+", str(b), re.I)), "")
    opening = next((re.sub(r"^\s*opening:\s*", "", b, flags=re.I) for s in slides for b in (s.get("bullets") or []) if re.match(r"\s*opening:", str(b), re.I)), "")
    if avoid and opening:
        f["swap"] = {"old": avoid[:1].upper() + avoid[1:], "new": opening[:1].upper() + opening[1:]}
    topics = d.get("topics") or th.get("topics") or []
    if isinstance(topics, list) and len(topics) >= 3:
        f["cards"] = [short(t, 3) for t in topics[:4]]
    return f


def facts_for(desk, d, video):
    if desk == "sociology": return soc_facts(d)
    if desk == "gs": return gs_facts(d, video)
    return essay_facts(d)


def fillable(desk, f):
    """the formats the day's own fields can fill"""
    have = set()
    if desk == "sociology":
        if f.get("lead") and f["lead"].get("thinker"): have |= {"F1", "F6"}
        if len(f["thinkers"]) >= 2: have.add("F2")
        if len(f["thinkers"]) >= 3: have.add("F3")
        lead = f.get("lead") or {}
        if re.search(r"\d", years_out(flat([lead.get("bullets"), lead.get("narration")]))): have.add("F4")
        if f.get("marks"): have.add("F5")
        if f.get("swap"): have.add("F7")
    elif desk == "gs":
        if f["video"] == "prelims":
            if len(f.get("sections", [])) >= 3: have.add("F3")
            if re.search(r"\d", years_out(flat(f.get("stems")) + " " + flat(f.get("cold")))): have.add("F4")
            have.add("F7")                                  # only when the model finds an old/new pair in the material
        else:
            if f.get("marks"): have.add("F5")
            if f.get("swap"): have.add("F7")
            if f.get("balance"): have.add("F2")
            if re.search(r"\d", years_out(f.get("question", "") + " " + flat(f.get("cold")))): have.add("F4")
    else:
        if f.get("topic"): have.add("F6")
        if f.get("swap"): have.add("F7")
        if f.get("dimensions"): have.add("F3")
        if f.get("cards"): have.add("F2")
    return have


# ------------------------------------------------------------------ the rotation
def order(ctype, have, history):
    """the formats to try, best first; empty means the T1 to T6 fallback"""
    first, second = MATRIX[ctype]
    hist = [h for h in history if h]
    last = hist[-1] if hist else None
    if {first, second} <= set(hist[-2:]): return []
    out = []
    if len(hist) >= 5 and "F3" not in hist[-5:] and "F3" in have and last != "F3":
        out.append("F3")                                    # one light surface in every six
    for fm in (first, second):
        if fm in have and fm != last and hist[-4:].count(fm) < 2 and fm not in out:
            out.append(fm)
    return out


# ------------------------------------------------------------------ the model
def call(system, user):
    body = {"model": MODEL, "max_tokens": 4000, "system": system, "messages": [{"role": "user", "content": user}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                 headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    for attempt in (1, 2, 3):
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=180).read())
            text = "".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
            m = re.search(r"\{.*\}", text, re.S)
            return json.loads(m.group(0)) if m else {}
        except urllib.error.HTTPError as e:
            log(f"HTTP {e.code} {e.read()[:160]!r}")
            if e.code < 500 and e.code != 429: raise
        except (TimeoutError, OSError, json.JSONDecodeError) as e:
            log(f"attempt {attempt}: {e}")
        time.sleep(8 * attempt)
    raise RuntimeError("the model call failed three times")


def ask(system, user, check, use_llm):
    if not use_llm or not os.environ.get("ANTHROPIC_API_KEY"): return None
    msg = user
    for attempt in (1, 2, 3):
        try:
            c = call(system, msg)
        except Exception as e:                       # noqa: BLE001
            log(f"attempt {attempt}: {e}"); continue
        errs = check(c)
        if not errs:
            log(f"{MODEL}: {json.dumps(c, ensure_ascii=False)[:300]}")
            return c
        log(f"attempt {attempt} rejected: {'; '.join(errs)} ({json.dumps(c, ensure_ascii=False)[:200]})")
        msg = user + "\n\nYour previous reply was rejected for these reasons. Fix every one:\n- " + "\n- ".join(errs) + \
            "\n\nYour previous reply:\n" + json.dumps(c, ensure_ascii=False)
    return None


VOICE = """You write words for one YouTube thumbnail of {desk_name}, a UPSC channel. It is read on a phone in one
second. The voice is serious and exam-wise: no hype, no clickbait, no "!", no emojis, no dashes of any
kind, never the words script, candidate, topper, shocking or secret, and no income claims. Use only names, facts and
numbers that appear in the material you are given; never invent one. Title Case for hooks.
Return ONLY a JSON object."""
DESK_NAME = {"sociology": "The Sociology Desk (UPSC Sociology Optional)", "gs": "The GS Desk (UPSC General Studies)",
             "essay": "The Essay Desk (UPSC Essay paper)"}


def common_errors(c, keys, src, max_words=MAX_WORDS):
    errs = []
    if not isinstance(c, dict): return ["the reply is not a JSON object"]
    hook, accent = str(c.get("hook") or "").strip(), str(c.get("accent") or "").strip()
    if "hook" in keys:
        if not hook: return ["hook: missing"]
        if len(words(hook)) > max_words: errs.append(f"hook: {len(words(hook))} words, at most {max_words}")
        if not accent: errs.append("accent: missing")
        elif accent.lower() not in hook.lower(): errs.append(f"accent: {accent!r} is not part of the hook exactly as written")
        elif len(words(accent)) > 3: errs.append("accent: at most three words")
        elif accent.lower().strip("?.") == hook.lower().strip("?."): errs.append("accent: only the key words, not the whole hook")
    text = " ".join(str(c.get(k) or "") if not isinstance(c.get(k), dict) else flat(c.get(k)) for k in keys)
    if DASH.search(text): errs.append("no dashes")
    if "!" in text: errs.append("no exclamation marks")
    if EMOJI.search(text): errs.append("no emojis")
    if BANNED.search(text): errs.append(f"never the word {BANNED.search(text).group(0)!r}")
    if not digits_ok(text, src): errs.append("every number must appear in the material exactly")
    return errs


# ------------------------------------------------------------------ the formats
def write(fm, desk, ctype, f, d, use_llm):
    """the format's own fields, or None when the day cannot fill it after all"""
    src = f["src"]
    sysmsg = VOICE.format(desk_name=DESK_NAME[desk])
    if fm == "F1":                                            # Sociology: the lead thinker and a question on the news
        lead = f["lead"]; t = lead["thinker"]; sur = surname(t["name"])
        facts = {"event": lead["event"], "news_facts": lead["bullets"], "thinker": t["name"], "concept": t["idea"]}
        def chk(c):
            e = common_errors(c, ["hook", "accent"], src, 5)
            if sur and re.search(rf"\b{re.escape(sur)}\b", str(c.get("hook", "")), re.I): e.append(f"the hook must not name {sur}: the kicker already does")
            return e
        c = ask(sysmsg, "Write {\"hook\", \"accent\"}: a question or statement of at most five words naming today's news in brief "
                "(a person, a place, a case, a policy), as the thinker would frame it. The accent is the news part, copied exactly "
                "from the hook, one to three words.\n\n" + json.dumps(facts, ensure_ascii=False), chk, use_llm)
        if not c:
            ev = short(lead["event"], 5)
            c = {"hook": ev + "?", "accent": short(ev, 2)}
        return {"kicker": f"{sur} on", "hook": c["hook"], "accent": c["accent"], "name": sur, "portrait": portrait_for(t["name"])}
    if fm == "F2":
        if desk == "sociology":
            a, b = f["thinkers"][0], f["thinkers"][1]
            left, right = {"name": surname(a["name"]), "sub": short(a["idea"], 4)}, {"name": surname(b["name"]), "sub": short(b["idea"], 4)}
            facts = {"left": a, "right": b, "events": [x["event"] for x in f["blocks"]]}
            c = ask(sysmsg, "Two thinkers face each other on this thumbnail. Write {\"hook\", \"accent\"}: the verdict line, at most six "
                    "words, naming the topic they disagree on and posing the choice (e.g. \"Census 2027: Hierarchy or Equality?\"). The "
                    "accent is one to three words copied exactly from the hook.\n\n" + json.dumps(facts, ensure_ascii=False),
                    lambda c: common_errors(c, ["hook", "accent"], src), use_llm)
            if not c: return None
            return {"left": left, "right": right, "hook": c["hook"], "accent": c["accent"]}
        if desk == "gs":
            bal = f["balance"]
            def chk(c):
                e = common_errors(c, ["hook", "accent", "left", "right"], src)
                for k in ("left", "right"):
                    n = str(c.get(k) or "")
                    if not n or len(n) > 14 or len(words(n)) > 2: e.append(f"{k}: one or two words, at most 14 letters")
                    elif not all(w.lower().strip(".,") in src.lower() for w in words(n)): e.append(f"{k}: its words must come from the material")
                return e
            c = ask(sysmsg, "This thumbnail sets two sides of a GS Mains question against each other. Write {\"left\", \"right\", "
                    "\"hook\", \"accent\"}: left and right are one or two words each naming the two sides, taken from the material; the "
                    "hook (at most six words) poses the choice; the accent is copied exactly from the hook.\n\n" +
                    json.dumps({"question": f.get("question"), "balance": bal}, ensure_ascii=False), chk, use_llm)
            if not c: return None
            return {"left": {"name": c["left"], "sub": short(bal["left"].get("title", ""), 5)},
                    "right": {"name": c["right"], "sub": short(bal["right"].get("title", ""), 5)}, "hook": c["hook"], "accent": c["accent"]}
        cards = f["cards"]                                      # Essay: the topics to choose from
        return {"cards": cards, "pick": 0, "hook": "Which One Would You Write?", "accent": "You"}
    if fm == "F3":
        if desk == "sociology":
            steps = [{"label": surname(t["name"])} for t in f["thinkers"][:4]]
            topic = (f.get("lead") or {}).get("event", "")
            fallback = {"hook": f"One Day, {len(steps)} Lenses", "accent": f"{len(steps)} Lenses"}
            what = f"The steps are the day's thinkers: {[s['label'] for s in steps]}. The day's stories: {[b['event'] for b in f['blocks']]}."
        elif desk == "gs":
            secs = f["sections"][:4]
            steps = [{"label": s.title() if len(s) > 4 else s} for s in secs]
            lead = short(f["cold"].get("headline", ""), 3) or "Ten Questions"
            fallback = {"hook": f"{lead}, {len(steps)} Subjects", "accent": f"{len(steps)} Subjects"}
            what = f"The steps are the subjects of the week's questions: {secs}. The week's headline: {f['cold'].get('headline', '')}."
        else:
            steps = [{"label": x} for x in f["dimensions"]]
            fallback = {"hook": f"{len(steps)} Dimensions, One Thesis", "accent": "One Thesis"}
            what = f"The steps are the essay's dimensions, in order: {f['dimensions']}. The topic: {f.get('topic')}."
        subject_text = {"sociology": " ".join(b["event"] for b in f.get("blocks", [])), "gs": str(f.get("cold", {}).get("headline", "")),
                        "essay": str(f.get("topic", ""))}[desk]
        fallback = {"hook": fallback["hook"].replace("3 ", "Three ").replace("4 ", "Four "), "accent": fallback["accent"].replace("3 ", "Three ").replace("4 ", "Four ")}
        topic_words = {w for w in re.findall(r"[a-z]{4,}", what.split("The steps are")[-1].split(":", 1)[-1].lower() + " " + subject_text.lower())} - GENERIC
        def chk(c):
            e = common_errors(c, ["hook", "accent"], src)
            hw = set(re.findall(r"[a-z]{4,}", str(c.get("hook", "")).lower()))
            if not (hw & topic_words): e.append("the hook must name the day's own subject (a story, a place, a scheme or the topic), not only the count")
            if hw & {"steps", "step", "staircase", "ladder"}: e.append("never describe the picture (steps, ladder)")
            return e
        c = ask(sysmsg, "This thumbnail shows a staircase of steps rising left to right. " + what + " Write {\"hook\", \"accent\"}: "
                "at most six words that name the day's own subject and the number of steps (e.g. \"Caste Census, Four Lenses\", "
                "\"Nobel Week, Four Subjects\"); the accent is one to three words copied exactly from the hook.", chk, use_llm) or fallback
        return {"steps": steps, "hook": c["hook"], "accent": c["accent"]}
    if fm == "F4":
        if desk == "sociology":
            lead = f["lead"]
            mat = {"event": lead["event"], "news_facts": lead["bullets"], "narration": str(lead.get("narration", ""))[:1500],
                   "thinker": (lead.get("thinker") or {}).get("name", ""), "concept": (lead.get("thinker") or {}).get("idea", "")}
        elif desk == "gs":
            mat = {"headline": f["cold"].get("headline"), "stems": f.get("stems"), "statements": f.get("statements"), "question": f.get("question")}
        else:
            mat = {"topic": f.get("topic")}
        news = flat(mat if desk != "gs" else [f.get("stems"), f.get("statements"), f.get("question")])
        def chk(c):
            e = common_errors(c, ["hook", "accent", "kicker", "number", "label", "caption"], src)
            num = str(c.get("number") or "")
            if not re.search(r"\d", num) or len(num) > 12: e.append("number: one real figure from the material, at most 12 characters")
            elif re.fullmatch(r"(19|20)\d\d", num.strip()): e.append("number: not a year")
            elif re.sub(r"\D", "", num) not in re.sub(r"[,\s]", "", news): e.append("number: a figure from the news facts themselves")
            elif desk == "gs" and re.sub(r"\D", "", num) == "10": e.append("number: a figure from the news, never the number of questions")
            elif num.strip() not in str(c.get("hook", "")) and re.sub(r"\D", "", num) not in re.sub(r"\D", "", str(c.get("hook", ""))):
                e.append("the hook must carry the number")
            if len(words(c.get("label", ""))) > 3: e.append("label: at most three words")
            if len(words(c.get("caption", ""))) > 8: e.append("caption: at most eight words")
            if len(words(c.get("kicker", ""))) > 5: e.append("kicker: at most five words")
            return e
        c = ask(sysmsg, "This thumbnail puts one real number from the material on a card, with an arrow from the hook. Write "
                "{\"number\", \"label\", \"caption\", \"kicker\", \"hook\", \"accent\"}: number is the figure exactly as the material "
                "gives it (with its unit, e.g. \"50%\", \"59 GW\", \"4.2\"), never a year; label names it (at most three words); caption "
                "says what it is (at most eight words); kicker is the topic (at most five words); the hook (at most six words) asks "
                "or states something plain about the number and contains it, never a quiz or a dare to the viewer; the accent is copied exactly from the hook and contains the "
                "number.\n\n" + json.dumps(mat, ensure_ascii=False), chk, use_llm)
        if not c: return None
        num = c["number"].strip()
        g = float(num.rstrip("%").replace(",", "")) if re.fullmatch(r"\d+(\.\d+)?%", num) else None
        return {"number": num, "label": c.get("label", ""), "caption": c.get("caption", ""), "kicker": c.get("kicker", ""),
                "hook": c["hook"], "accent": c["accent"], "gauge": g if g is not None and g <= 100 else None}
    if fm == "F5":
        m = f["marks"]
        gain = m["after"] - m["before"]
        if desk == "sociology":
            b = m["block"]; kick = short((b.get("thinker") or {}).get("idea") or b.get("concept") or b["event"], 4)
            sheet = f"{soc_paper(b)} · probable question"
        else:
            kick = (f.get("topic_line") if desk == "gs" else f.get("theme")) or "The answer, rewritten"
            sheet = m.get("sheet") or "Answer sheet"
        return {"kicker": kick, "hook": f"Same Answer. +{gain} Marks.", "accent": f"+{gain}", "before": m["before"], "after": m["after"],
                "outOf": m["outOf"], "note": short(m.get("note", ""), 6), "sheet": sheet}
    if fm == "F6":
        if desk == "sociology":
            lead = f["lead"]; t = lead["thinker"]
            big = (t["idea"] or lead.get("concept") or "").strip()
            if not big or len(words(big)) > 4: big = (lead.get("concept") or big)
            if not big or len(words(big)) > 4: return None
            def chk(c):
                e = common_errors(c, ["line", "accent"], src)
                ln, ac = str(c.get("line") or ""), str(c.get("accent") or "")
                if not ln.lower().startswith("seen today in "): e.append("line: must start with \"seen today in\"")
                if len(words(ln)) > 8: e.append("line: at most eight words")
                if not ac or ac.lower() not in ln.lower() or "seen today" in ac.lower(): e.append("accent: the news words, copied exactly from the line")
                return e
            c = ask(sysmsg, "This thumbnail shows one concept as a dictionary entry and, under it, where it is seen in today's news. "
                    "Write {\"line\", \"accent\"}: line is \"seen today in\" plus the news in at most five words, lower case except "
                    "names; accent is the news words copied exactly from the line.\n\n" + json.dumps(
                        {"concept": big, "event": lead["event"], "news_facts": lead["bullets"]}, ensure_ascii=False), chk, use_llm)
            if not c:
                ev = short(lead["event"], 5)
                c = {"line": f"seen today in {ev}", "accent": ev}
            return {"big": big[:1].lower() + big[1:] if not big[:2].isupper() else big, "sub": t["name"], "line": c["line"], "accent": c["accent"], "upper": False}
        if desk == "essay":
            # the topic exactly as UPSC-style wording gives it, fitted to its box; a clause only when it is too long
            topic = re.sub(r"\s+", " ", f["topic"]).strip()
            if len(words(topic)) > 18:
                return None
            big = topic if topic[-1:] in ".?!" else topic + "."
            def chk(c):
                e = common_errors(c, ["accent"], src)
                ac = str(c.get("accent") or "")
                if not ac or ac not in big or len(words(ac)) > 2: e.append("accent: one or two words copied exactly, same case, from the topic")
                return e
            c = ask(sysmsg, "This thumbnail shows the essay topic in large type, exactly as written. Write {\"accent\"}: the one or two "
                    "words of it that carry the tension, copied exactly with the same case.\n\nThe topic: " + big, chk, use_llm) or {"accent": ""}
            c["big"] = big
            return {"kicker": " · ".join(x for x in ["Essay", f.get("theme", "")] if x), "big": c["big"], "accent": c["accent"], "upper": False}
        return None
    if fm == "F7":
        sw = f.get("swap")
        if desk == "gs" and f["video"] == "prelims":
            def chk(c):
                e = common_errors(c, ["hook", "accent", "old", "new"], src)
                for k in ("old", "new"):
                    v = str(c.get(k) or "")
                    if not v or len(words(v)) > 8: e.append(f"{k}: at most eight words")
                    elif sum(w.lower().strip(".,") in src.lower() for w in words(v)) < len(words(v)) * 0.8: e.append(f"{k}: in the material's own words")
                return e
            c = ask(sysmsg, "If the week's material states that one law, rule or arrangement replaced another (an old thing and the "
                    "new thing), write {\"old\", \"new\", \"hook\", \"accent\"} in the material's own words: old and new at most eight "
                    "words each, the hook at most six words. If it does not, reply {\"none\": true}.\n\n" +
                    json.dumps({"headline": f["cold"].get("headline"), "stems": f.get("stems")}, ensure_ascii=False),
                    lambda c: [] if c.get("none") else chk(c), use_llm)
            if not c or c.get("none"): return None
            sw = {"old": c["old"], "new": c["new"]}
            hook = {"hook": c["hook"], "accent": c["accent"]}
        else:
            if not sw: return None
            what = {"sociology": "the average answer's move against the better answer's move",
                    "gs": "the weak phrase in an answer against the scoring phrase",
                    "essay": "the opening to avoid against the opening to use"}[desk]
            hook = ask(sysmsg, f"This thumbnail crosses out one line and ticks another: {what}. Write {{\"hook\", \"accent\"}}: at most "
                       "six words telling the viewer what to stop or change (e.g. \"Never Open Like This\", \"Stop Describing the Case\", "
                       "\"Swap This Phrase\"); the accent is one or two words copied exactly from the hook.\n\n" + json.dumps(
                           {"old": sw["old"], "new": sw["new"]}, ensure_ascii=False), lambda c: common_errors(c, ["hook", "accent"], src), use_llm) \
                or {"sociology": {"hook": "Change This One Line", "accent": "One Line"}, "gs": {"hook": "Swap This Phrase", "accent": "Swap"},
                    "essay": {"hook": "Never Open Like This", "accent": "Open"}}[desk]
        mode = "cards" if len(sw["old"]) <= 10 and len(sw["new"]) <= 10 else "lines"
        return {"old": sw["old"], "neu": sw["new"], "mode": mode, "hook": hook["hook"], "accent": hook["accent"]}
    return None


def portrait_for(name):
    """remotion/public/portraits/<slug>.jpg when the portrait library (release thinker-portraits) has the thinker"""
    slug = re.sub(r"[^a-z]+", "-", surname(name).lower()).strip("-")
    rel = f"portraits/{slug}.jpg"
    return rel if slug and os.path.exists(os.path.join(HERE, "remotion", "public", rel)) else None


# ------------------------------------------------------------------ the day
def classify(desk, video, f, d, use_llm):
    key = (desk, video if desk == "gs" else "")
    types = TYPES[key]
    if desk == "sociology":
        mat = {"title": d.get("video_title"), "stories": [{"event": b["event"], "concept": b.get("concept"),
                                                             "thinker": (b.get("thinker") or {}).get("name")} for b in f["blocks"]]}
    elif desk == "gs":
        mat = {"title": d.get("video_title"), "headline": f["cold"].get("headline"), "question": f.get("question"), "sections": f.get("sections")}
    else:
        mat = {"title": d.get("video_title"), "topic": f.get("topic"), "theme": f.get("theme")}
    c = ask(VOICE.format(desk_name=DESK_NAME[desk]), "Which one content type fits this video best? Choose from:\n" +
            "\n".join(f"- {t}: {TYPE_NOTES[t]}" for t in types) + "\nReply {\"content_type\": \"...\"}.\n\n" + json.dumps(mat, ensure_ascii=False),
            lambda c: [] if c.get("content_type") in types else [f"content_type must be one of {types}"], use_llm)
    return c["content_type"] if c else DEFAULT[key]


def make(desk, d, video="", history=(), plate=None, use_llm=True, force=None):
    desk = "sociology" if desk in ("soc", "sociology") else desk
    f = facts_for(desk, d, video)
    have = fillable(desk, f)
    ctype = classify(desk, video, f, d, use_llm)
    tries = [force] if force else order(ctype, have, list(history))
    log(f"content type {ctype}; the day can fill {sorted(have)}; history {list(history)[-5:]}; trying {tries}")
    for fm in tries:
        if fm not in have and not force: continue
        try:
            fields = write(fm, desk, ctype, f, d, use_llm)
        except Exception as e:                       # noqa: BLE001  one format failing passes to the next
            log(f"{fm} failed: {e}"); fields = None
        if not fields:
            log(f"{fm}: not filled today"); continue
        pill = {"sociology": soc_paper(f.get("lead")) if fm != "F6" else "Concept", "gs": f.get("pill", "GS"), "essay": f.get("pill", "Essay Paper")}[desk]
        props = {"desk": desk, "f": fm, "v": "", "header": "HC", "pill": pill, "issue": "", "date": "", "plate": plate if fm in ("F1", "F4") else None,
                 "kicker": "", "hook": "", "accent": "", "thinker": "", "name": "", "portrait": None, "left": None, "right": None,
                 "cards": None, "pick": 0, "steps": None, "number": "", "label": "", "caption": "", "gauge": None, "before": 0,
                 "after": 0, "outOf": 0, "note": "", "sheet": "", "big": "", "sub": "", "line": "", "upper": False, "old": "", "neu": "", "mode": ""}
        props.update(fields)
        if ctype in DATED:
            props.update({"issue": issue_of(d) if desk == "sociology" else str(d.get("issue_no", "")).strip(), "date": nice_date(d.get("date", ""))})
        props["_ctype"], props["_kind"] = ctype, video
        return props
    return None


def run(desk, d, video="", plate=None, use_llm=True, state_in=None, state_out=None):
    """For the desk's prep code: the v3 props, or None for the T1 to T6 fallback. The history is read
    from state_in (default $THUMB_V3_STATE) and this run's state, today's format added ("T" for the
    fallback), is written to state_out (default $THUMB_V3_STATE_OUT). THUMB_V3=off turns v3 off."""
    state_in = state_in or os.environ.get("THUMB_V3_STATE")
    state_out = state_out or os.environ.get("THUMB_V3_STATE_OUT")
    if os.environ.get("THUMB_V3", "").lower() in ("off", "0", "false"):
        log("THUMB_V3=off: the T1 to T6 designs"); return None
    hist = []
    if state_in and os.path.exists(state_in):
        try: hist = json.load(open(state_in)).get("formats", [])
        except Exception: hist = []                      # noqa: E722
    try:
        p = make(desk, d, video, hist, plate, use_llm)
    except Exception as e:                               # noqa: BLE001  never the day's thumbnail
        log(f"failed: {e}"); p = None
    if state_out:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(state_out)), exist_ok=True)
            json.dump({"formats": (hist + [p["f"] if p else "T"])[-8:], "issue": str(d.get("issue_no", "")).strip(),
                       "content_type": p["_ctype"] if p else "", "kind": video}, open(state_out, "w"))
        except Exception as e:                           # noqa: BLE001
            log(f"state not written: {e}")
    if p: log(f"{p['f']} ({p['_ctype']}): {p.get('hook') or p.get('big')!r}")
    return {k: v for k, v in p.items() if not k.startswith("_")} if p else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("desk", choices=["sociology", "soc", "gs", "essay"])
    ap.add_argument("script")
    ap.add_argument("--video", default="")
    ap.add_argument("--history", help="the last run's state (JSON with \"formats\"), when there is one")
    ap.add_argument("--out", default="thumb_v3_props.json")
    ap.add_argument("--state-out", help="write this run's state: the history with today's format added")
    ap.add_argument("--plate")
    ap.add_argument("--format", choices=["F1", "F2", "F3", "F4", "F5", "F6", "F7"])
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    try:
        d = json.load(open(a.script))
        hist = []
        if a.history and os.path.exists(a.history):
            try: hist = json.load(open(a.history)).get("formats", [])
            except Exception: hist = []                  # noqa: E722  a bad state file is no history
        video = a.video or (d.get("video", "") if a.desk == "gs" else "")
        p = make(a.desk, d, video, hist, a.plate, not a.no_llm, a.format)
    except Exception as e:                               # noqa: BLE001  the caller falls back to T1..T6
        log(f"failed: {e}"); p = None
    if not p:
        log("no format fits today: the T1 to T6 fallback")
        if a.state_out:                                  # the fallback counts as a turn in the rotation
            json.dump({"formats": (hist + ["T"])[-8:], "issue": issue_of(d), "content_type": ""}, open(a.state_out, "w"))
        return 3
    json.dump({k: v for k, v in p.items() if not k.startswith("_")}, open(a.out, "w"), ensure_ascii=False, indent=1)
    if a.state_out:
        json.dump({"formats": (hist + [p["f"]])[-8:], "issue": issue_of(d), "content_type": p["_ctype"]}, open(a.state_out, "w"))
    log(f"{p['f']} ({p['_ctype']}): {p.get('hook') or p.get('big')!r}")
    print(p["f"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
