#!/usr/bin/env python3
"""
carousel_props.py - the day's Instagram and Facebook carousel, built from the day's own content.

  python3 ops/carousel_props.py decide --desk gs --date 2026-09-21 [--force] [--format A|C|D]
  python3 ops/carousel_props.py fetch  --desk gs --date 2026-09-21 --out content [--from-run ID]
  python3 ops/carousel_props.py build  --desk gs --date 2026-09-21 --format A --content content \
                                       --archive carousel/archive --out carousel_out
  python3 ops/carousel_props.py pinned carousel/pinned/pin1_what.json --out carousel_out

The same file in every desk's repository (GS, Essay, Sociology): the desk is an argument.
remotion/src/DeskCarousel.tsx draws the slides; this file only chooses and places the words.

One carousel a day across the shared account, on an IST calendar:
  Monday, Thursday     GS         Monday: format A, News to Syllabus, from the Mains script
                                  Thursday: format D, the day's best Prelims question, square
  Tuesday, Friday      Sociology
  Wednesday, Saturday  Essay      format A for the Essay, from the day's Reel words
  Sunday               format C, a revision deck from the week's saved facts, for one desk
                       by ISO week number: week % 3 == 0 GS, 1 Sociology, 2 Essay

The words. Every word on a slide comes from the day's content, which has already passed the
desk's wording checks and the humaniser; nothing here asks a model for prose. The only words
of this file's own are the fixed labels of the approved mockups (kickers, slide labels, the
last slide's evaluation and Telegram lines). Every string on every slide and in the caption is
checked in code (no "script", no "candidate", no dashes or " - " asides, no emojis, no
exclamation marks, no "link in bio", "aspirant" and not "student" unless the news is about
students). It fails closed: a failing optional field is dropped, a failing slide is left out,
and when a slide the carousel cannot do without fails, or a field it needs is missing, the day
is skipped with a ::warning:: and nothing is written. Half a carousel is never built.

The archive. Every day the day's revision facts (and the carousel's props, when one was built)
are written to carousel/archive/YYYY-MM-DD.json; the workflow commits it, and Sunday's deck is
built from the Monday to Saturday files of that ISO week.
"""
import argparse, datetime as dt, glob, io, json, os, re, subprocess, sys, zipfile

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
EVALUATE = "evaluate.upscdesk.com"
DESKS = {
    "gs":        {"name": "GS DESK", "telegram": "t.me/upscdesk_gs", "days": {1: "A", 4: "D"}},
    "sociology": {"name": "SOCIOLOGY DESK", "telegram": "t.me/upscdesk_sociology", "days": {2: "B", 5: "B"}},
    "essay":     {"name": "ESSAY DESK", "telegram": "t.me/upscdesk_essay", "days": {3: "A", 6: "A"}},
}
SUNDAY_DESK = {0: "gs", 1: "sociology", 2: "essay"}            # ISO week number % 3
# the formats this file can build for each desk (the Sociology desk joins when its builders do)
BUILDS = {"gs": {"A", "D", "C"}, "essay": {"A", "C"}, "sociology": set()}
NUM = "zero one two three four five six seven eight nine ten eleven twelve".split()
MINUTES = {10: "seven", 15: "eleven"}                          # GS writing time at the paper's pace
DIRECTIVES = ["Critically examine", "Critically analyse", "Critically evaluate", "Compare and contrast", "Discuss",
              "Examine", "Analyse", "Evaluate", "Comment", "Elucidate", "Explain", "Assess", "Justify", "Illustrate"]


def warn(msg):
    """a warning on the run's page, and a line in the run's summary"""
    print(f"::warning::{msg}")
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as f: f.write(f"- {msg}\n")
        except OSError:
            pass


class Skip(Exception):
    """the day is skipped: a slide the carousel needs failed, or a field it needs is missing"""


# ------------------------------------------------------------------ the wording checks
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")
BAD = [(re.compile(r"(?i)\bscripts?\b"), "says 'script'"),
       (re.compile(r"(?i)\bcandidates?\b"), "says 'candidate'"),
       (re.compile("[–—‒―]"), "has an em or en dash"),
       (re.compile(r"\s-+\s"), "has a ' - ' aside"),
       (re.compile(r"(?i)link\s+in\s+(the\s+)?bio"), "says 'link in bio'"),
       (re.compile(r"!"), "has an exclamation mark"),
       (EMOJI, "has an emoji")]
STUDENT = re.compile(r"(?i)\bstudents?\b")


def problems(text, allow_student=False):
    t = str(text or "")
    out = [why for rx, why in BAD if rx.search(t)]
    if not allow_student and STUDENT.search(t):
        out.append("says 'student' (write 'aspirant')")
    return out


def strings(x):
    if isinstance(x, str): yield x
    elif isinstance(x, dict):
        for v in x.values(): yield from strings(v)
    elif isinstance(x, list):
        for v in x: yield from strings(v)


def plain(t):
    """content text as it goes on a slide: one line, and without the characters the slide
    reads as markup (*bold*, _highlight_)"""
    return re.sub(r"\s+", " ", str(t or "").replace("*", "").replace("_", " ")).strip()


def fit(t, limit):
    t = plain(t)
    return t if t and len(t) <= limit else ""


def sentence(t):
    t = plain(t).rstrip(" .")
    return (t[:1].upper() + t[1:] + ".") if t else ""


def need(v, what):
    if v in (None, "", [], {}):
        raise Skip(f"{what} is missing")
    return v


class Deck:
    """slides in order; each checked as it is added. optional=True: a slide that fails is left
    out; otherwise the day is skipped. drop: fields that are left out when they fail."""
    def __init__(self, allow_student):
        self.slides, self.allow = [], allow_student

    def add(self, slide, optional=False, drop=()):
        for k in drop:
            if k in slide and any(problems(s, self.allow) for s in strings(slide[k])):
                print(f"carousel: {slide['kind']}: '{k}' left out ({'; '.join(p for s in strings(slide[k]) for p in problems(s, self.allow))})")
                slide.pop(k)
        bad = [f"{s[:60]!r} {p}" for s in strings(slide) for p in problems(s, self.allow)]
        if bad:
            if optional:
                print(f"carousel: the {slide['kind']} slide is left out: {bad[0]}")
                return False
            raise Skip(f"the {slide['kind']} slide fails the wording check: {bad[0]}")
        if optional: slide["optional"] = True
        self.slides.append(slide)
        return True


def check_caption(caption, allow_student):
    bad = problems(caption, allow_student)
    if bad:
        raise Skip(f"the caption {', '.join(bad)}")
    tags = re.findall(r"#\w+", caption)
    if not 8 <= len(tags) <= 12:
        raise Skip(f"the caption has {len(tags)} hashtags, not 8 to 12")
    return caption


def hashtags(base, extra):
    seen, out = set(), []
    for t in base + extra:
        t = "#" + re.sub(r"[^0-9A-Za-z]", "", t.lstrip("#"))
        if len(t) > 2 and t.lower() not in seen:
            seen.add(t.lower()); out.append(t)
    return out[:12]


def camel(phrase):
    words = re.findall(r"[A-Za-z0-9]+", phrase)
    return "".join(w if w.isupper() else w.capitalize() for w in words) if 0 < len(words) <= 3 else ""


def closing_lines(desk, work="answer"):
    tg = DESKS[desk]["telegram"]
    return ["Save this for revision.",
            f"Write the {work} yourself and get it evaluated at {EVALUATE}, five free evaluations every month.",
            f"The full brief goes to subscribers. Subscribe from the link on our Telegram channel: {tg}"]


def practice_lines(desk, first):
    tg = DESKS[desk]["telegram"]
    return [first, f"The full brief goes to subscribers. Subscribe from the link on our Telegram channel, *{tg}*."]


# ------------------------------------------------------------------ small readers
def day_str(d):
    return f"{d.day} {d:%B %Y}"


def parse_day(s):
    try:
        return dt.datetime.strptime(re.sub(r"\s+", " ", str(s or "")).strip(), "%d %B %Y").date()
    except ValueError:
        return None


def layouts(script):
    """the first slide of each layout, by layout name"""
    out = {}
    for s in script.get("slides", []):
        out.setdefault(s.get("layout"), s.get("content") or {})
    return out


def unquote(q):
    """the question without its wrapping quotation marks (the slide adds its own)"""
    q = plain(q)
    return re.sub(r"[“”]", "", re.sub(r"(^|\s)‘(.+?)’(?=[\s.,;:]|$)", r"\1\2", q)).strip()


def sentence_case(headline, corpus):
    """a Title Case headline in sentence case: a capitalised word stays capitalised only when the
    day's own text writes it that way mid-sentence more often than in lower case"""
    words = plain(headline).split(" ")
    out = [words[0]]
    for w in words[1:]:
        core = re.sub(r"'s$", "", re.sub(r"[^\w']", "", w))
        if not core or not core[0].isupper() or core.isupper() and len(core) > 1:
            out.append(w); continue
        low = len(re.findall(rf"\b{re.escape(core.lower())}\b", corpus))
        cap = len(re.findall(rf"(?<![.?:]\s)(?<!^)\b{re.escape(core)}\b", corpus))
        out.append(w if cap > low else w[:1].lower() + w[1:])
    return " ".join(out)


def gold_run(text, gold):
    """the last run of gold words, in *asterisks* (one accent per title)"""
    words, g = text.split(" "), {re.sub(r"[^\w']", "", x).lower() for x in gold or []}
    flags = [re.sub(r"[^\w']", "", w).lower() in g for w in words]
    end = max((i for i, f in enumerate(flags) if f), default=-1)
    if end < 0:
        return text
    start = end
    while start > 0 and flags[start - 1]: start -= 1
    lead, run = " ".join(words[:start]), " ".join(words[start:end + 1])
    tail = " ".join(words[end + 1:])
    m = re.match(r"(.*?)([.,;:?]*)$", run)
    return " ".join(x for x in (lead, f"*{m.group(1)}*{m.group(2)}", tail) if x)


def highlight(text, key, mark="_"):
    text, key = plain(text), plain(key)
    if key and key in text:
        return text.replace(key, f"{mark}{key}{mark}", 1)
    return text


def headline_size(t):
    n = len(t.replace("*", ""))
    return 92 if n <= 38 else 80 if n <= 56 else 74 if n <= 80 else 0


# ------------------------------------------------------------------ GS, format A (Monday)
def gs_topic(sub):
    """'GS Paper III, environment and federal governance.' -> ('GS Paper III', 'environment and
    federal governance')"""
    sub = plain(sub).rstrip(".")
    paper, _, topic = sub.partition(",")
    topic = re.sub(r"(?i)\s+question$", "", re.sub(r"^(the)\s+", "", topic.strip()))
    return paper.strip(), topic


def gs_tag(source):
    rules = [(r"\bv\.?\s|\bversus\b|\bcase\b", "CASE"), (r"\bAct\b|\bBill\b|\bCode\b", "ACT"),
             (r"\bArticles?\b|\bEntry\b|\bSchedule\b|\bList\b", "CONSTITUTION"), (r"\bRules?\b|\bRegulations?\b", "RULES"),
             (r"\bReport\b|\bSurvey\b|\bIndex\b|\bCommission\b|\bCommittee\b", "REPORT"), (r"\bScheme\b|\bMission\b|\bYojana\b", "SCHEME")]
    for rx, tag in rules:
        if re.search(rx, source):
            return tag
    return None


def body_text(script):
    """the running text of a script's slides (not its titles, which are in Title Case)"""
    keys = ("text", "body", "line", "question", "why", "note", "close", "explanation", "stem", "sub")
    out = []
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, str) and k in keys: out.append(v)
                elif not isinstance(v, str): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk([s.get("content") for s in script.get("slides", [])])
    return "\n".join(out)


def gs_mains_facts(m):
    L = layouts(m)
    c, led = L.get("cold_open", {}), L.get("ledger", {})
    corpus = body_text(m)
    rows = [{"head": fit(r.get("source"), 70), "text": fit(r.get("line"), 120)} for r in led.get("rows", [])]
    rows = [r for r in rows if r["head"] and r["text"]]
    if not rows:
        return []
    return [{"kind": "mains", "label": plain(c.get("sub")).rstrip("."), "title": sentence_case(c.get("headline", ""), corpus), "items": rows}]


def gs_prelims_facts(p):
    out = []
    for s in p.get("slides", []):
        if s.get("layout") != "mind_map": continue
        c = s.get("content") or {}
        items = [{"head": fit(n.get("title"), 40), "text": fit(n.get("sub"), 110)} for n in c.get("nodes", [])]
        items = [x for x in items if x["head"] and x["text"]]
        sec = plain(c.get("section"))
        if len(items) >= 3 and c.get("title"):
            out.append({"kind": "prelims", "label": sec if len(sec) <= 3 else sec.title(), "title": plain(c["title"]), "items": items[:4]})
    return out


def gs_A(m, date):
    L = layouts(m)
    cold, qc, led, wb = (need(L.get(k), f"the Mains {k} slide") for k in ("cold_open", "question_card", "ledger", "word_budget"))
    corpus = body_text(m)
    q = need(unquote(qc.get("question")), "the question")
    allow = bool(STUDENT.search(q + " " + json.dumps(m.get("archive_items", []), ensure_ascii=False)))
    deck = Deck(allow)
    paper, topic = gs_topic(cold.get("sub"))
    tag1 = plain(qc.get("tag1")) or paper.upper()
    tag2 = re.sub(r"\s*·\s*", " · ", plain(qc.get("tag2")))
    marks = int((re.search(r"(\d+)\s*MARKS", tag2) or [0, 0])[1] or 0)
    words = int((re.search(r"(\d+)\s*WORDS", tag2) or [0, 0])[1] or 0)
    pill3 = re.sub(r"\s+question$", "", re.split(r",| and ", topic)[0].strip(), flags=re.I).upper()
    headline = gold_run(sentence_case(need(cold.get("headline"), "the headline"), corpus), cold.get("gold_words"))
    size = headline_size(headline) or None
    need(size, "a headline short enough for the cover")

    # the takeaway: the thesis line with its key phrase highlighted, else the gold card, else the item's thesis
    th = (L.get("thesis", {}).get("sentences") or [{}])[0]
    gold_card = next((x for x in (L.get("statement_cards", {}).get("cards") or []) if x.get("gold")), {})
    choices = [highlight(th.get("text"), th.get("key")), plain(gold_card.get("body")),
               plain((m.get("archive_items") or [{}])[0].get("thesis"))]
    take = next((t for t in choices if t and len(t) <= 190 and not problems(t, allow)), "")
    deck.add({"kind": "cover", "kicker": "NEWS TO SYLLABUS", "headline": headline, "size": size,
              "pills": [tag1, tag2, pill3] if pill3 else [tag1, tag2], "takeaway": need(take, "a one-line takeaway")})

    # the chain: the news, the syllabus, the case or anchor, the answer
    item = (m.get("archive_items") or [{}])[0]
    when = parse_day(re.sub(r"(\d{4})-(\d\d)-(\d\d)", lambda x: dt.date(*map(int, x.groups())).strftime("%d %B %Y"), str(item.get("source_date") or "")))
    lines = [plain(x.get("text")) for x in L.get("statement_cards", {}).get("lines", [])]
    maps = next((l for l in lines if l.lower().startswith("maps to")), "")
    first = (led.get("rows") or [{}])[0]
    ftag = gs_tag(plain(first.get("source")))
    moves = wb.get("moves") or []
    steps = [{"k": "THE NEWS", "head": day_str(when) if when else fit(item.get("headline"), 60), "body": fit(item.get("headline"), 120)},
             {"k": "THE SYLLABUS", "head": fit(f"{paper}: {topic}", 60), "body": fit(maps, 110)},
             {"k": "THE CASE" if ftag == "CASE" else "THE ANCHOR", "head": fit(first.get("source"), 60), "body": fit(first.get("line"), 110)},
             {"k": "THE ANSWER", "head": fit(moves[-1].get("head") if moves else "", 60), "body": fit(moves[-1].get("body") if moves else "", 110)}]
    for st in steps:
        if st["body"] == st["head"] or problems(st["body"], allow): st["body"] = ""
        if not st["body"]: st.pop("body")
    steps = [s for s in steps if s["head"] and not problems(s["head"], allow)]
    if len(steps) >= 3:
        deck.add({"kind": "pipeline", "label": "The chain", "title": "From the news to your answer", "steps": steps}, optional=True)

    # the question: the directive underlined, one key phrase highlighted, the trap from its close
    directive = next((d for d in DIRECTIVES if re.search(rf"(?i)\b{d}\b", q)), "")
    qm = [x for x in qc.get("marks", []) if plain(x.get("text")) and plain(x.get("text")) in q]
    dmark = next((x for x in qm if directive and directive.lower() in plain(x["text"]).lower()), None)
    other = next((x for x in qm if x is not dmark), None)
    qmarks = ([{"text": plain(dmark["text"]), "kind": "ul"}] if dmark else
              [{"text": re.search(rf"(?i)\b{directive}\b", q)[0], "kind": "ul"}] if directive else [])
    if other: qmarks.append({"text": plain(other["text"]), "kind": "hl"})
    n = len(q)
    trap = fit(qc.get("close"), 170)
    trap = highlight(trap, next((x for x in re.findall(r"\b(closed case|not yet|yet to rule|never|few will)\b", trap)), ""), "*") if trap else ""
    slide = {"kind": "question", "qsize": 42 if n <= 220 else 40 if n <= 290 else 36 if n <= 360 else 34 if n <= 460 else 0,
             "question": q, "marks": qmarks, "pills": [tag1, tag2] + ([directive.upper()] if directive else []), "trap": trap}
    need(slide["qsize"], "a question short enough for one slide")
    if not trap: slide.pop("trap")
    deck.add(slide, drop=("trap",))

    # the three lines that score
    rows = []
    for r in (led.get("rows") or [])[:3]:
        src, line, why = fit(r.get("source"), 64), fit(r.get("line"), 130), fit(r.get("why"), 80)
        if not (src and line): continue
        row = {"source": src, "line": line}
        if gs_tag(src): row["tag"] = gs_tag(src)
        if why and not problems(why, allow): row["why"] = why
        rows.append(row)
    if len(rows) == 3:
        sub = fit(led.get("sub"), 50).rstrip(".")
        deck.add({"kind": "anchors", "label": "Three lines that score", "title": sub or "Write these, with their sources", "rows": rows}, optional=True)

    # the word budget
    seg = [{"label": fit(s.get("label"), 34), "n": int(s.get("n") or 0)} for s in wb.get("segments", [])]
    seg = [s for s in seg if s["label"] and s["n"] > 0]
    if 3 <= len(seg) <= 6:
        deck.add({"kind": "budget", "label": "Word budget", "title": f"Where the {sum(s['n'] for s in seg)} words go", "segments": seg}, optional=True)

    # the common mistake: the struck claim of the marked answer, else its first weak phrase
    sheet = next((s.get("content") for s in m.get("slides", []) if s.get("layout") == "answer_sheet" and (s.get("content") or {}).get("marks")), {}) or {}
    strike = next((x for x in sheet.get("marks", []) if x.get("kind") == "strike"), None)
    swaps = (L.get("word_swaps") or {}).get("pairs") or []
    cut = next((c for c in (L.get("coached") or {}).get("coach", []) if c.get("tag") == "CUT"), None)
    mk = None
    if strike and fit(strike.get("text"), 110):
        paras = [sentence(strike.get("note")), plain(cut.get("body")) if cut else ""]
        mk = {"kind": "mistake", "title": f"Writing “{plain(strike['text'])}”", "paras": [p for p in paras if p and len(p) <= 170 and not problems(p, allow)]}
    elif swaps and fit(swaps[0].get("a"), 90) and fit(swaps[0].get("b"), 110):
        mk = {"kind": "mistake", "title": f"Writing “{plain(swaps[0]['a'])}”", "paras": [f"Write *{plain(swaps[0]['b'])}* instead."]}
    if mk and mk["paras"]:
        deck.add(mk, optional=True)

    mins = MINUTES.get(marks)
    deck.add({"kind": "practice", "title": f"Write this answer in *{mins} minutes*" if mins else "Write this answer *tonight*",
              "lines": practice_lines("gs", f"Then send it for evaluation at *{EVALUATE}*, five free evaluations every month."),
              "pill": "SAVE THIS FOR REVISION"})
    if len(deck.slides) < 5:
        raise Skip(f"only {len(deck.slides)} slides passed; a News to Syllabus carousel needs at least five")

    # the caption: search-first line, two or three plain lines, then the fixed close
    heads = "; ".join(r["source"] for r in rows) if rows else ""
    head_plain = headline.replace("*", "")
    line1 = f"UPSC Mains {paper}, {topic}: {head_plain}."
    if heads: line1 += f" {heads}."
    body = [f"The probable question, {marks} marks: {directive.lower() or 'answer'} it in {words} words." if marks and words else "",
            trap.replace("*", "") if trap and not problems(trap, allow) else "",
            take.replace("_", "").replace("*", "")]
    body = [b for b in body if b][:3]
    tags = hashtags(["UPSC", "UPSCMains", "GSPaper" + str({"I": 1, "II": 2, "III": 3, "IV": 4}.get(paper.split()[-1], "")), "IAS",
                     "CivilServices", "AnswerWriting", "UPSCPreparation", "CurrentAffairs"],
                    [camel(t) for t in re.split(r",| and ", topic) if camel(t)][:3])
    caption = "\n".join([line1, "", *body, "", *closing_lines("gs"), "", " ".join(tags)])
    return {"desk": "gs", "format": "A", "issue": str(m.get("issue_no") or ""), "date": day_str(date), "square": False,
            "slides": deck.slides}, check_caption(caption, allow)


# ------------------------------------------------------------------ GS, format D (Thursday)
def gs_pick_prelims(p):
    """the best Prelims question for a square card: a plain statements question first, then any
    question with statements, whose words fit the card and pass the checks"""
    cands = [s.get("content") or {} for s in p.get("slides", []) if s.get("layout") == "prelims_answer"]
    def fits(c):
        opts = [plain(o.get("v")) for o in c.get("options", [])]
        sts = [plain(x.get("text")) for x in c.get("statements", [])]
        return (len(opts) == 4 and all(0 < len(o) <= 34 for o in opts) and 2 <= len(sts) <= 3 and all(len(s) <= 130 for s in sts)
                and 0 < len(plain(c.get("stem"))) <= 130 and 0 < len(plain(c.get("explanation"))) <= 230
                and re.match(r"^\(?[a-d]\)?$", str(c.get("answer") or "").strip())
                and not any(problems(s) for s in strings(c)))
    for rank in ("statements", None):
        for c in cands:
            if (rank is None or c.get("pattern") == rank) and fits(c):
                return c
    return None


def gs_D(p, date):
    c = gs_pick_prelims(p)
    if not c:
        raise Skip("no Prelims question fits the square card and passes the checks")
    sec = plain(c.get("section")).upper()
    opts = [plain(o.get("v")) for o in c["options"]]
    ans = "abcd".index(re.sub(r"[()\s]", "", c["answer"]))
    stem = plain(c["stem"])
    deck = Deck(False)
    deck.add({"kind": "mcq", "label": "Prelims, today", "tag": sec, "stem": stem,
              "statements": [re.sub(r"^\s*\d+[.)]\s*", "", plain(s.get("text"))) for s in c["statements"]],
              "ask": plain(c.get("question_line")), "options": opts})
    deck.add({"kind": "mcq", "label": "The answer", "tag": sec, "stem": f"Answer ({'abcd'[ans]}): {opts[ans]}.", "statements": [], "ask": "",
              "options": opts, "answer": ans, "explanation": plain(c["explanation"])})
    deck.add({"kind": "practice", "title": "Five evaluations *free every month*",
              "lines": practice_lines("gs", f"Write any Mains answer from this week and send it to *{EVALUATE}*."),
              "pill": "SAVE FOR REVISION"})
    subj = re.sub(r"(?i)^(consider the following (two )?(statements|pairs)( (about|on|regarding|in the context of|with reference to))?|with reference to|how many of the following statements (about|on|regarding))\s+", "", stem)
    subj = re.sub(r"(?i),?\s*(consider the following.*|are correct\??)$", "", subj).rstrip(" .:")
    secname = sec if len(sec) <= 3 else sec.title()
    line1 = f"UPSC Prelims practice, {secname}: {subj}."
    body = ["One question from today's news, in the exam's own pattern. Answer it before you swipe.",
            "The answer and the explanation are on the next slide."]
    tags = hashtags(["UPSC", "UPSCPrelims", "PrelimsPractice", "IAS", "CivilServices", "UPSCPreparation", "CurrentAffairs", "GSDesk"],
                    [camel(secname) or secname])
    caption = "\n".join([line1, "", *body, "", *closing_lines("gs"), "", " ".join(tags)])
    return {"desk": "gs", "format": "D", "issue": str(p.get("issue_no") or ""), "date": day_str(date), "square": True,
            "slides": deck.slides}, check_caption(caption, False)


# ------------------------------------------------------------------ Essay, format A
def essay_facts(props):
    d = props.get("data") or props
    if not d.get("topic"):
        return []
    return [{"kind": "essay", "topic": plain(d["topic"]), "decode": plain(d.get("decode")), "hub": plain(d.get("hub")),
             "items": [{"head": plain(l.get("title")), "text": plain(l.get("sub"))} for l in d.get("lenses", [])]}]


def essay_A(props, script, date):
    d = props.get("data") or props
    topic = need(fit(d.get("topic"), 130), "the essay topic")
    allow = bool(STUDENT.search(topic))
    deck = Deck(allow)
    # the turn of the topic in the accent: from its "but" or "yet", or after its semicolon
    m = re.search(r",\s+(?=(?:but|yet)\s)|;\s+", topic)
    head = f"{topic[:m.start() + 1]} *{topic[m.end():].strip()}*" if m else topic
    size = need(headline_size(head), "a topic short enough for the cover")
    decode = need(fit(d.get("decode"), 150), "the decode")
    deck.add({"kind": "cover", "kicker": "ESSAY OF THE DAY", "headline": head, "size": size,
              "pills": ["ESSAY PAPER", "125 MARKS", "1,000 TO 1,200 WORDS"], "takeaway": decode})

    # the decode: what it says, what it means, what it asks, your thesis
    slides = (script or {}).get("slides", [])
    dec = next((s for s in slides if re.search(r"(?i)decode", str(s.get("heading")))), {})
    bullets = [plain(b) for b in dec.get("bullets") or []]
    thesis_b = next((re.sub(r"(?i)^thesis:\s*", "", b) for b in bullets if b.lower().startswith("thesis")), "")
    other_b = [b for b in bullets if not b.lower().startswith("thesis")]
    parts = [p.strip() for p in re.split(r"(?<=[.?])\s+", decode) if p.strip()]
    steps = [{"k": "WHAT IT SAYS", "head": fit(d.get("literal"), 60), "body": fit(other_b[0] if other_b else "", 90)},
             {"k": "WHAT IT MEANS", "head": fit(parts[0] if parts else "", 80), "body": fit(other_b[1] if len(other_b) > 1 else "", 90)}]
    if len(parts) > 1:
        steps.append({"k": "WHAT IT ASKS", "head": fit(" ".join(parts[1:]), 80)})
    hub = fit(d.get("hub"), 40)
    steps.append({"k": "YOUR THESIS", "head": fit(sentence(thesis_b).rstrip("."), 60) if thesis_b else hub, "body": hub if thesis_b else ""})
    for st in steps:
        if not st.get("body") or problems(st["body"], allow): st.pop("body", None)
    steps = [s for s in steps if s["head"] and not problems(s["head"], allow)]
    if len(steps) >= 3:
        deck.add({"kind": "pipeline", "label": "The decode", "title": "What it says, and what it asks", "steps": steps}, optional=True)

    lenses = [{"title": fit(l.get("title"), 16), "sub": fit(l.get("sub"), 38)} for l in d.get("lenses", [])]
    lenses = [l for l in lenses if l["title"] and l["sub"]][:6]
    if len(lenses) >= 4 and hub:
        deck.add({"kind": "lens", "label": "Hub and spokes", "title": f"{NUM[len(lenses)].capitalize()} lenses to sweep, clockwise", "hub": hub, "lenses": lenses}, optional=True)

    avg = [x for x in d.get("average", []) if plain(x.get("text"))]
    better = [plain(b) for b in d.get("better", []) if plain(b)]
    if len(avg) == 3 and len(better) == 3:
        notes = [plain(x.get("note")) for x in avg if plain(x.get("note"))]
        opening = next((b for s in slides for b in (s.get("bullets") or []) if re.match(r"(?i)^open\b", plain(b)) and len(plain(b)) <= 40), "")
        sl = {"kind": "opening", "title": plain(opening) or "An opening that works", "flat": " ".join(plain(x["text"]) for x in avg),
              "why": sentence(", ".join(notes)) if notes else "", "working": " ".join(better)}
        if not sl["why"]: sl.pop("why")
        deck.add(sl, optional=True, drop=("why",))

    n = len(lenses) if len(lenses) >= 4 else 0
    seg = [("Opening scene", 120), ("Decode and thesis", 130), (f"{NUM[n].capitalize()} lenses" if n else "The dimensions", 600),
           ("Counter-view, answered", 150), ("Way forward", 100), ("Closing image", 50)]
    deck.add({"kind": "budget", "label": "Word budget", "title": "Where the 1,150 words go", "segments": [{"label": a, "n": b} for a, b in seg]}, optional=True)
    deck.add({"kind": "practice", "title": "Write the first page *tonight*",
              "lines": ["The opening and one lens are enough to start."] + practice_lines("essay", f"Get it evaluated at *{EVALUATE}*, five free evaluations every month."),
              "pill": "SAVE THIS TOPIC"})
    if len(deck.slides) < 4:
        raise Skip(f"only {len(deck.slides)} slides passed; an Essay carousel needs at least four")

    line1 = f"UPSC Essay topic: “{topic}”"
    if lenses: line1 += f" Lenses: {', '.join(l['title'] for l in lenses)}."
    body = [f"What it asks: {decode}", "Swipe for the decode, the lenses, a stronger opening and the word budget."]
    tags = hashtags(["UPSC", "UPSCEssay", "EssayWriting", "EssayPaper", "UPSCMains", "IAS", "CivilServices", "UPSCPreparation"],
                    [camel(hub.split(",")[0])] if hub and camel(hub.split(",")[0]) else [])
    caption = "\n".join([line1, "", *body, "", *closing_lines("essay", "essay"), "", " ".join(tags)])
    return {"desk": "essay", "format": "A", "issue": str(d.get("issue") or ""), "date": day_str(date), "square": False,
            "slides": deck.slides}, check_caption(caption, allow)


# ------------------------------------------------------------------ format C (Sunday revision)
def week_days(date):
    mon = date - dt.timedelta(days=date.isoweekday() - 1)
    return [mon + dt.timedelta(days=k) for k in range(6)]


def revision_C(desk, date, archive):
    days = week_days(date)
    saved = []
    for d in days:
        f = os.path.join(archive, f"{d.isoformat()}.json")
        if os.path.isfile(f):
            a = json.load(open(f, encoding="utf-8"))
            if a.get("desk") == desk:
                saved.append((d, a.get("facts") or []))
    deck, groups = Deck(False), []
    ok = lambda it: it["head"] and it["text"] and not problems(it["head"]) and not problems(it["text"])
    if desk == "gs":
        mains = [g for _, fs in reversed(saved) for g in fs if g.get("kind") == "mains"]
        pre = [g for _, fs in reversed(saved) for g in fs if g.get("kind") == "prelims"]
        # a Prelims map on a different subject from the Mains lines, so the two slides do not repeat
        seen = set(re.findall(r"[a-z]{5,}", json.dumps(mains[:1]).lower()))
        picks = mains[:1] + [g for g in pre if not seen & set(re.findall(r"[a-z]{5,}", json.dumps(g.get("items")).lower() + " " + g.get("title", "").lower()))][:2 - len(mains[:1])]
        for g in picks:
            items = [it for it in g.get("items", []) if ok(it)][:4]
            if len(items) >= 2 and not problems(g.get("title")) and not problems(g.get("label")):
                groups.append({"label": fit(g.get("label"), 48) or "This week", "title": fit(g.get("title"), 48), "items": items})
        pills, kicker_pills = ["GS DESK", "PRELIMS AND MAINS"], "GS"
    elif desk == "essay":
        items = []
        for _, fs in saved:
            for g in fs:
                if g.get("kind") == "essay":
                    it = {"head": fit(g.get("topic"), 110), "text": fit(g.get("decode"), 110), "italic": True}
                    if ok(it): items.append(it)
        for k in range(0, min(len(items), 8), 4):
            groups.append({"label": "This week's topics", "title": "Decoded" if k == 0 else "Decoded, continued", "items": items[k:k + 4]})
        pills = ["ESSAY DESK", "ESSAY PAPER"]
    else:
        raise Skip(f"no Sunday builder for the {desk} desk yet")
    total = sum(len(g["items"]) for g in groups)
    if total < 5:
        raise Skip(f"the week's archive has {total} usable revision items; a Sunday deck needs five")
    while total > 8:
        groups[-1]["items"].pop(); total -= 1
        if not groups[-1]["items"]: groups.pop()
    span = f"{days[0].day} to {date.day} {date:%B %Y}" if days[0].month == date.month else f"{day_str(days[0])} to {day_str(date)}"
    deck.add({"kind": "cover", "kicker": "SUNDAY REVISION", "headline": f"The week in *{NUM[total]} lines*", "pills": pills,
              "takeaway": "Save it now. Read it again on _Wednesday_ with the right side covered."})
    n = 0
    for g in groups:
        items = []
        for it in g["items"]:
            n += 1; items.append({**it, "n": n})
        deck.add({"kind": "glossary", "label": g["label"], "title": g["title"], "items": items}, optional=True)
    if not any(s["kind"] == "glossary" for s in deck.slides):
        raise Skip("no revision slide passed the checks")
    work = "essay" if desk == "essay" else "answer"
    deck.add({"kind": "practice", "title": "Test yourself on *Wednesday*",
              "lines": ["Cover the right side and say each line aloud."] + practice_lines(desk, f"Then write one {work} and get it evaluated at *{EVALUATE}*, five free evaluations every month."),
              "pill": "SAVE FOR REVISION"})
    heads = "; ".join(g["title"] for g in groups)
    name = {"gs": "GS", "essay": "Essay"}[desk]
    line1 = f"UPSC {name} revision, {span}: {heads}."
    body = [f"{NUM[total].capitalize()} lines from this week's {name} Desk, to save and revise.", "Cover the right side and test yourself on Wednesday."]
    base = {"gs": ["UPSC", "UPSCMains", "UPSCPrelims", "IAS", "CivilServices", "UPSCPreparation", "CurrentAffairs", "Revision", "SundayRevision"],
            "essay": ["UPSC", "UPSCEssay", "EssayWriting", "EssayPaper", "UPSCMains", "IAS", "CivilServices", "Revision", "SundayRevision"]}[desk]
    caption = "\n".join([line1, "", *body, "", *closing_lines(desk, work), "", " ".join(hashtags(base, []))])
    return {"desk": desk, "format": "C", "issue": "", "date": span, "square": False, "slides": deck.slides}, check_caption(caption, False)


# ------------------------------------------------------------------ the day, the content, the archive
def decide(desk, date, force=False, fmt=""):
    """(format, reason): format is '' when today is not this desk's day"""
    wd = date.isoweekday()
    if fmt and fmt != "auto":
        f = fmt
    elif wd == 7:
        owner = SUNDAY_DESK[date.isocalendar()[1] % 3]
        f = "C" if owner == desk or force else ""
        if not f:
            return "", f"Sunday of ISO week {date.isocalendar()[1]} is the {owner} desk's revision deck"
    elif wd in DESKS[desk]["days"]:
        f = DESKS[desk]["days"][wd]
    elif force:
        f = {"gs": "A" if wd in (1, 3, 5) else "D"}.get(desk, next(iter(DESKS[desk]["days"].values())))
    else:
        return "", f"{date:%A} is not a {desk} day"
    if f not in BUILDS.get(desk, set()):
        return "", f"format {f} is not built for the {desk} desk"
    return f, ("forced" if force or (fmt and fmt != "auto") else "the rotation")


def gh_json(path):
    return json.loads(subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True).stdout)


def gh_zip(repo, aid):
    blob = subprocess.run(["gh", "api", f"repos/{repo}/actions/artifacts/{aid}/zip"], check=True, capture_output=True).stdout
    return zipfile.ZipFile(io.BytesIO(blob))


def fetch(desk, date, out, from_run=""):
    """the day's content from this repository's daily run artifacts: the newest artifact whose own
    date is the day (or everything a given run kept). Writes the files into out/."""
    repo = os.environ.get("GITHUB_REPOSITORY") or subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                                                                 check=True, capture_output=True, text=True).stdout.strip()
    os.makedirs(out, exist_ok=True)
    names = {"gs": ["scripts"], "essay": ["script", "reel"], "sociology": ["script", "reel"]}[desk]
    if from_run:
        arts = gh_json(f"repos/{repo}/actions/runs/{from_run}/artifacts?per_page=100")["artifacts"]
        arts = [a for a in arts if not a["expired"] and (a["name"] in names or a["name"] == "reel-test")]
    else:
        arts = []
        for n in names:
            arts += [a for a in gh_json(f"repos/{repo}/actions/artifacts?name={n}&per_page=50")["artifacts"] if not a["expired"]]
        lo, hi = date - dt.timedelta(days=1), date + dt.timedelta(days=2)
        arts = [a for a in arts if lo <= dt.date.fromisoformat(a["created_at"][:10]) <= hi]
    arts.sort(key=lambda a: a["created_at"], reverse=True)
    got, runs = {}, set()
    for a in arts:
        z = gh_zip(repo, a["id"])
        for member in z.namelist():
            base = os.path.basename(member)
            if not base.endswith(".json") or base in got: continue
            data = json.loads(z.read(member))
            day = parse_day(data.get("date")) if isinstance(data, dict) else None
            if base.endswith("_script.json") or base == "video_script.json":
                if not from_run and day != date: continue
            elif base == "reel_props.json":
                # the Reel's words carry no date: they belong to the run whose script is the day's,
                # or, with no script kept, to an artifact made on the day itself (IST)
                made = dt.datetime.fromisoformat(a["created_at"].replace("Z", "+00:00")).astimezone(IST).date()
                if not from_run and not (a["workflow_run"]["id"] in runs or made == date): continue
            else:
                continue
            got[base] = a["id"]
            runs.add(a["workflow_run"]["id"])
            json.dump(data, open(os.path.join(out, base), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"carousel: {base} from artifact {a['name']} ({a['id']}, run {a['workflow_run']['id']})")
    if not got:
        warn(f"carousel: no {desk} content for {date} in this repository's artifacts")
    return got


def load(path):
    return json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else None


def build(desk, date, fmt, content, archive, out):
    """the day's facts into the archive (always, when there is content), then the carousel's props
    and caption into out/ (only when every required slide passed). Returns True when built."""
    os.makedirs(out, exist_ok=True)
    for f in ("props.json", "caption.txt"):
        if os.path.exists(os.path.join(out, f)): os.remove(os.path.join(out, f))
    facts, built = [], None
    if desk == "gs":
        m, p = load(os.path.join(content, "mains_script.json")), load(os.path.join(content, "prelims_script.json"))
        facts = (gs_mains_facts(m) if m else []) + (gs_prelims_facts(p) if p else [])
    elif desk == "essay":
        r, s = load(os.path.join(content, "reel_props.json")), load(os.path.join(content, "video_script.json"))
        facts = essay_facts(r) if r else []
    try:
        if fmt == "C":
            built = revision_C(desk, date, archive)
        elif desk == "gs" and fmt == "A":
            built = gs_A(need(m, "the day's Mains script (mains_script.json)"), date)
        elif desk == "gs" and fmt == "D":
            built = gs_D(need(p, "the day's Prelims script (prelims_script.json)"), date)
        elif desk == "essay" and fmt == "A":
            built = essay_A(need(r, "the day's Reel words (reel_props.json)"), s, date)
        elif fmt:
            raise Skip(f"format {fmt} is not built for the {desk} desk")
    except Skip as e:
        warn(f"carousel: no {desk} carousel for {date} ({e}); nothing will be posted")
        built = None
    if facts or built:
        os.makedirs(archive, exist_ok=True)
        rec = {"desk": desk, "date": date.isoformat(), "facts": facts}
        if built: rec["carousel"] = built[0]
        json.dump(rec, open(os.path.join(archive, f"{date.isoformat()}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not built:
        return False
    props, caption = built
    json.dump(props, open(os.path.join(out, "props.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(out, "caption.txt"), "w", encoding="utf-8").write(caption + "\n")
    print(f"carousel: {desk} format {props['format']}, {len(props['slides'])} slides: {', '.join(s['kind'] for s in props['slides'])}")
    return True


def pinned(path, out):
    """an approved pinned post (carousel/pinned/*.json): checked like any day's carousel"""
    spec = json.load(open(path, encoding="utf-8"))
    deck = Deck(False)
    for s in spec["slides"]:
        deck.add(dict(s))
    caption = check_caption(spec.get("caption", ""), False)
    os.makedirs(out, exist_ok=True)
    props = {k: spec.get(k, "") for k in ("desk", "issue", "date")}
    props.update({"format": "pinned", "square": bool(spec.get("square")), "slides": deck.slides})
    json.dump(props, open(os.path.join(out, "props.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(out, "caption.txt"), "w", encoding="utf-8").write(caption + "\n")
    print(f"carousel: pinned post {os.path.basename(path)}, {len(deck.slides)} slides")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["decide", "fetch", "build", "pinned"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--desk", choices=sorted(DESKS))
    ap.add_argument("--date", default="", help="YYYY-MM-DD; blank = today in IST")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--format", default="")
    ap.add_argument("--from-run", default="")
    ap.add_argument("--content", default="content")
    ap.add_argument("--archive", default="carousel/archive")
    ap.add_argument("--out", default="carousel_out")
    a = ap.parse_args()
    date = dt.date.fromisoformat(a.date) if a.date.strip() else dt.datetime.now(IST).date()
    if a.cmd == "pinned":
        return 0 if pinned(a.file, a.out) else 1
    if a.cmd == "decide":
        f, why = decide(a.desk, date, a.force, a.format)
        print(json.dumps({"format": f, "reason": why, "date": date.isoformat()}))
        return 0
    if a.cmd == "fetch":
        fetch(a.desk, date, a.content, a.from_run)
        return 0
    return 0 if build(a.desk, date, a.format, a.content, a.archive, a.out) else 0


if __name__ == "__main__":
    sys.exit(main())
