#!/usr/bin/env python3
"""brief_build.py: build the UPSC Desk daily brief (v2 design) from a content file.

    python3 brief_build.py content.json out.pdf          check, then build
    python3 brief_build.py content.json --check          check only

The content file is described in SCHEMA.md. The builder checks the content first: word
counts against the limit, every note number against its highlighted phrase, note length,
notes per paragraph, a margin column never longer than its paragraph, dashes, emojis,
"script" and "candidate", and the brief-voice words and phrases. If anything fails it prints
a numbered list of problems and exits with code 1 without writing the PDF: fix the content
and run it again. Exit code 0 means the PDF was built.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from briefkit import (CW, F, NOTE_COLOURS, THEMES, Pills, Pipeline, HubSpoke, band, box, can_draw, column_heights,  # noqa: E402
                      grid, hub_fit, make_doc, mark, numbered_margin, pills_width, pipeline_fit, styles)
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import CondPageBreak, KeepTogether, PageBreak, Paragraph, Spacer  # noqa: E402
from reportlab.platypus.doctemplate import NextPageTemplate  # noqa: E402

TAGS = list(NOTE_COLOURS)
NOTE_MAX_WORDS, NOTES_PER_PARA = 25, 2
ESSAY_MIN, ESSAY_MAX = 1000, 1200
LIMITS = {10: 150, 15: 250, 20: 250}

# ------------------------------------------------------------------ the voice check
# BRIEF_VOICE (ops/agent_patches/brief_voice.md) and the desks' own banned phrases
BANNED_PHRASES = [
    "in today's world", "in an era of", "in the ever-evolving", "picture this", "let's dive in", "let us dive in",
    "here's the thing", "it is important to note", "it is worth mentioning", "it is worth noting", "in many ways",
    "arguably", "at its core", "ultimately", "a stark reminder", "double-edged sword", "the need of the hour",
    "clarion call", "needless to say", "since time immemorial", "in today's fast-paced world", "in conclusion",
    "unprecedented", "game-changer", "game changer",
]
BANNED_WORDS = [  # regular expressions, matched as whole words, any case
    r"delv(e|es|ed|ing)", r"tapestr(y|ies)", r"landscapes?", r"navigat\w*", r"pivotal", r"crucial(ly)?", r"robust(ly|ness)?",
    r"holistic(ally)?", r"multi-?faceted", r"nuanced", r"underscor\w*", r"testament", r"realms?", r"embark\w*",
    r"unlock\w*", r"harness(es|ed|ing)?", r"leverag\w*", r"paradigms?", r"synerg\w*", r"seamless(ly)?",
    r"intricate(ly)?", r"intricac(y|ies)", r"myriad",
]
DESK_WORDS = [(r"scripts?", 'write "answer" (or "essay"), never "script"'),
              (r"candidates?", 'write "aspirant", never "candidate"')]
EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF⬀-⯿️‍←-⇿]")
DASHES = re.compile("[‒–—―⸺⸻]")
QUOTED = re.compile(r"“[^”]*”|\"[^\"]*\"")
NOT_BUT = [re.compile(r"\bnot (just|only|merely|simply)\b[^.;:]*?\bbut\b", re.I),
           re.compile(r"\bnot\b[^.;,]{1,60}[;,] but\b", re.I),
           re.compile(r"\b(it|this|that) is not\b[^.;]{1,60}; (it|this|that) is\b", re.I)]
COLON_REVEAL = re.compile(r"\bThe (answer|result|truth|lesson|catch|problem|point|reason|verdict|takeaway|secret):", re.I)


def plain(text):
    """the words as the reader sees them: markup removed"""
    t = re.sub(r"\[\[(.+?)\|\s*\d+\s*\]\]", r"\1", text)
    return t.replace("**", "").replace("*", "")


def words(text):
    return len(plain(text).split())


def to_html(text, th=None, marks=True):
    """content markup to ReportLab markup: [[phrase|n]] a numbered highlight, **bold**, *italic*"""
    t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if marks and th is not None:
        t = re.sub(r"\[\[(.+?)\|\s*(\d+)\s*\]\]", lambda m: mark(m.group(1), int(m.group(2)), th), t)
    else:
        t = re.sub(r"\[\[(.+?)\|\s*\d+\s*\]\]", r"\1", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"\*(.+?)\*", r"<i>\1</i>", t)
    return t


def voice_problems(texts):
    """[(where, problem)] for every text field: [(where, text, kind)] with kind 'prose' or 'label'"""
    out, not_but = [], []
    for where, text, kind in texts:
        t = plain(text)
        if DASHES.search(t):
            out.append((where, f"a dash ({DASHES.search(t).group()!r}): use a comma, a full stop or 'to'"))
        if "--" in t:
            out.append((where, "a double hyphen: use a comma or a full stop"))
        if re.search(r"\s-\s", t):
            out.append((where, "a hyphen used as a dash (' - '): use a comma or a full stop"))
        if EMOJI.search(t):
            out.append((where, "an emoji or symbol: remove it"))
        if "!" in t:
            out.append((where, "an exclamation mark: remove it"))
        bare = QUOTED.sub(" ", t)          # a phrase quoted to warn against it is allowed
        low = bare.lower().replace("’", "'")
        for p in BANNED_PHRASES:
            if re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", low):
                out.append((where, f"the phrase \"{p}\": say it plainly"))
        for w in BANNED_WORDS:
            m = re.search(r"\b" + w + r"\b", bare, re.I)
            if m:
                out.append((where, f"the word \"{m.group()}\": use a plain word"))
        for w, why in DESK_WORDS:
            m = re.search(r"\b" + w + r"\b", bare, re.I)
            if m:
                out.append((where, f"the word \"{m.group()}\": {why}"))
        if re.search(r"(^|[.?]\s+)(Imagine|Picture)\b", bare):
            out.append((where, "an 'Imagine' or 'Picture' opener: start with the point"))
        if COLON_REVEAL.search(bare):
            out.append((where, f"a colon reveal (\"{COLON_REVEAL.search(bare).group()}\"): state the point in a full sentence"))
        if kind == "prose":
            for s in re.split(r"(?<=[.?])\s+", bare.strip()):
                ws = s.rstrip(".?").split()
                if 0 < len(ws) <= 2 and all(w.isalpha() and len(w) > 2 for w in ws) and s.endswith("."):
                    out.append((where, f"a clipped sentence for effect (\"{s}\"): join it to the next sentence"))
        seen = []
        for rx in NOT_BUT:
            for m in rx.finditer(bare):
                if not any(a <= m.start() < b or m.start() <= a < m.end() for a, b in seen):
                    seen.append((m.start(), m.end())); not_but.append((where, m.group()))
    if len(not_but) > 1:          # allowed once in a whole brief
        for where, s in not_but:
            out.append((where, f"the 'not X, but Y' turn (\"{s[:60]}\"): allowed once per brief, used {len(not_but)} times"))
    return out


# ------------------------------------------------------------------ checks
class Problems(list):
    def add(self, where, what): self.append(f"{where}: {what}")


def need(p, obj, key, where, kind=str, empty_ok=False):
    v = obj.get(key) if isinstance(obj, dict) else None
    if v is None:
        p.add(where, f"'{key}' is missing"); return None
    if kind is str and not isinstance(v, str):
        p.add(where, f"'{key}' must be text"); return None
    if kind is list and not isinstance(v, list):
        p.add(where, f"'{key}' must be a list"); return None
    if kind is dict and not isinstance(v, dict):
        p.add(where, f"'{key}' must be an object"); return None
    if kind is int and not isinstance(v, int):
        p.add(where, f"'{key}' must be a whole number"); return None
    if not empty_ok and kind in (str, list) and not v:
        p.add(where, f"'{key}' is empty"); return None
    return v


def check_answer(p, paras, where, th, st, texts):
    """the model answer or essay: marks against notes, note length, notes per paragraph, column heights"""
    marked, noted, order = {}, {}, []
    for i, para in enumerate(paras, 1):
        pw = f"{where} paragraph {i}"
        if not isinstance(para, dict):
            p.add(pw, "must be an object with 'text' and 'notes'"); continue
        text = need(p, para, "text", pw)
        notes = para.get("notes", [])
        if not isinstance(notes, list):
            p.add(pw, "'notes' must be a list"); notes = []
        if text is None:
            continue
        texts.append((pw, text, "prose"))
        if re.search(r"\[\[[^\]]*$|\[\[[^\]|]*\]\]", text):
            p.add(pw, "a broken highlight: write [[the phrase|number]]")
        here = []
        for m in re.finditer(r"\[\[(.+?)\|\s*(\d+)\s*\]\]", text):
            n = int(m.group(2)); here.append(n); order.append(n)
            if n in marked:
                p.add(pw, f"note number {n} is marked on two phrases; each number marks exactly one phrase")
            marked[n] = i
            if len(m.group(1).split()) > 14:
                p.add(pw, f"the highlighted phrase for note {n} is {len(m.group(1).split())} words; highlight at most 14")
        if len(notes) > NOTES_PER_PARA:
            p.add(pw, f"{len(notes)} margin notes; at most {NOTES_PER_PARA} per paragraph (drop one or move it to a paragraph that has none)")
        clean = []
        for k, nt in enumerate(notes, 1):
            nw = f"{pw} note {nt.get('n', k) if isinstance(nt, dict) else k}"
            if not isinstance(nt, dict):
                p.add(nw, "must be an object with 'n', 'tag' and 'text'"); continue
            n, tag, ntext = nt.get("n"), nt.get("tag"), nt.get("text")
            if not isinstance(n, int):
                p.add(nw, "'n' must be the note's number"); continue
            if tag not in TAGS:
                p.add(nw, f"'tag' must be one of {', '.join(TAGS)}"); tag = "ADD"
            if not isinstance(ntext, str) or not ntext.strip():
                p.add(nw, "'text' is empty"); continue
            texts.append((nw, ntext, "prose"))
            if words(ntext) > NOTE_MAX_WORDS:
                p.add(nw, f"{words(ntext)} words; a margin note is at most {NOTE_MAX_WORDS} words")
            if n in noted:
                p.add(nw, f"note number {n} is used twice")
            noted[n] = i
            if n not in here:
                p.add(nw, f"note {n} has no highlighted phrase in this paragraph; mark it as [[phrase|{n}]] in the paragraph it sits beside")
            clean.append((n, tag, to_html(ntext, marks=False)))
        bh, nh = column_heights(to_html(text, th), clean, th, st)
        if nh > bh + 1:
            p.add(pw, f"the margin notes ({nh:.0f}pt) run longer than the paragraph ({bh:.0f}pt); shorten the notes or move one to another paragraph")
    for n, i in sorted(marked.items()):
        if n not in noted:
            p.add(f"{where} paragraph {i}", f"the highlight numbered {n} has no note; add note {n} beside this paragraph or remove the highlight")
    if order and order != list(range(1, len(order) + 1)):
        p.add(where, f"note numbers must run 1, 2, 3 in reading order; they run {', '.join(map(str, order))}")
    return sum(words(x["text"]) for x in paras if isinstance(x, dict) and isinstance(x.get("text"), str))


def check_pipeline(p, nodes, where, width, texts):
    if not isinstance(nodes, list) or not 3 <= len(nodes) <= 5:
        p.add(where, "must list 3 to 5 boxes"); return None
    out = []
    for i, nd in enumerate(nodes, 1):
        if not isinstance(nd, dict) or not all(isinstance(nd.get(k), str) and nd.get(k).strip() for k in ("label", "title", "text")):
            p.add(f"{where} box {i}", "needs 'label', 'title' and 'text'"); return None
        out.append((nd["label"].upper(), plain(nd["title"]), plain(nd["text"])))
        texts += [(f"{where} box {i}", nd["title"], "label"), (f"{where} box {i}", nd["text"], "label"), (f"{where} box {i}", nd["label"], "label")]
    for i, what, n in pipeline_fit(out, width):
        p.add(f"{where} box {i + 1}", f"the {what} is cut off (it has room for {n} line{'s' if n > 1 else ''}); shorten it")
    return out


def check_common(p, e, where, texts, desk):
    sk = need(p, e, "skeleton", where, list)
    if sk is not None:
        if not 3 <= len(sk) <= 7:
            p.add(f"{where} skeleton", "3 to 7 lines")
        for i, row in enumerate(sk, 1):
            if not (isinstance(row, list) and len(row) == 2 and all(isinstance(x, str) and x.strip() for x in row)):
                p.add(f"{where} skeleton line {i}", "must be [label, text]")
            else:
                texts += [(f"{where} skeleton line {i}", row[0], "label"), (f"{where} skeleton line {i}", row[1], "label")]
    sa = need(p, e, "sets_apart", where)
    if sa:
        texts.append((f"{where} sets_apart", sa, "prose"))
        if sa.lower().startswith("what sets"):
            p.add(f"{where} sets_apart", "leave out 'What sets the top ... apart:'; the builder prints it")
    am = need(p, e, "ammunition", where, list)
    if am is not None:
        if not 3 <= len(am) <= 10:
            p.add(f"{where} ammunition", "3 to 10 lines")
        for i, a in enumerate(am, 1):
            if not (isinstance(a, dict) and isinstance(a.get("source"), str) and isinstance(a.get("line"), str) and a["source"].strip() and a["line"].strip()):
                p.add(f"{where} ammunition {i}", "needs 'source' and 'line'")
            else:
                texts += [(f"{where} ammunition {i}", a["source"], "label"), (f"{where} ammunition {i}", a["line"], "prose")]
    if e.get("pill") is not None:
        if not isinstance(e["pill"], str):
            p.add(where, "'pill' must be text")
        else:
            texts.append((f"{where} pill", e["pill"], "label"))
    if e.get("practice") is not None:
        if not isinstance(e["practice"], str) or not e["practice"].strip():
            p.add(where, "'practice' must be text")
        else:
            texts.append((f"{where} practice", e["practice"], "prose"))


def validate(d):
    """(problems, report lines, theme) for a content dict"""
    p, texts, report = Problems(), [], []
    desk = d.get("desk")
    if desk not in THEMES:
        p.add("desk", "must be 'sociology' or 'essay'"); return p, report, None
    th = THEMES[desk]; st = styles(th)
    for k in ("issue", "date", "motivation"):
        if not isinstance(d.get(k), (str, int)) or not str(d.get(k)).strip():
            p.add("top level", f"'{k}' is missing")
    if isinstance(d.get("date"), str) and not re.fullmatch(r"\d{1,2} [A-Z][a-z]+ \d{4}", d["date"].strip()):
        p.add("date", "write it as DD Month YYYY, for example 27 September 2026")
    if isinstance(d.get("motivation"), str):
        texts.append(("motivation", d["motivation"], "prose"))
    if d.get("contents") is not None:
        if not (isinstance(d["contents"], list) and all(isinstance(r, list) and len(r) == 4 for r in d["contents"])):
            p.add("contents", "leave it out (the builder makes the table); if given, rows of four cells")
    key = "events" if desk == "sociology" else "topics"
    items = d.get(key)
    if not isinstance(items, list) or not items:
        p.add("top level", f"'{key}' must list at least one {key[:-1]}"); return p, report, th
    for idx, e in enumerate(items, 1):
        where = f"{key[:-1]} {idx}"
        if not isinstance(e, dict):
            p.add(where, "must be an object"); continue
        check_common(p, e, where, texts, desk)
        if desk == "sociology":
            paper = e.get("paper")
            if paper not in (1, 2):
                p.add(where, "'paper' must be 1 or 2")
            for k in ("syllabus", "title", "question", "question_summary"):
                v = need(p, e, k, where)
                if v: texts.append((f"{where} {k}", v, "label" if k != "question" else "prose"))
            marks = e.get("marks")
            if marks not in LIMITS:
                p.add(where, "'marks' must be 10, 15 or 20"); marks = 20
            limit = LIMITS[marks]
            ans = need(p, e, "answer", where, list)
            ch = check_pipeline(p, e.get("chain"), f"{where} chain", CW - 20, texts)
            t = need(p, e, "thinker", where, dict)
            if t is not None:
                for k in ("name", "text"):
                    v = need(p, t, k, f"{where} thinker")
                    if v: texts.append((f"{where} thinker {k}", v, "prose" if k == "text" else "label"))
                if t.get("dates") is not None:
                    if isinstance(t["dates"], str): texts.append((f"{where} thinker dates", t["dates"], "label"))
                    else: p.add(f"{where} thinker", "'dates' must be text, for example 1891 to 1956")
            if not isinstance(e.get("practice"), str):
                p.add(where, "'practice' is missing (the closing line: write this answer tonight ...)")
            pill_texts = [f"PAPER {paper}", f"{marks} MARKS · {limit} WORDS"] + ([e["pill"].upper()] if isinstance(e.get("pill"), str) and e["pill"] else [])
            if ans is not None:
                n = check_answer(p, ans, f"{where} model answer", th, st, texts)
                lo = -(-limit * 95 // 100)
                ok = lo <= n <= limit
                report.append(f"{where} model answer: {n} words (limit {limit}, allowed {lo} to {limit}){'' if ok else '  <-- outside the limit'}")
                if not ok:
                    p.add(f"{where} model answer", f"{n} words; it must be {lo} to {limit} words for {marks} marks (count with len(text.split()))")
        else:
            if e.get("section") not in ("A", "B"):
                p.add(where, "'section' must be 'A' or 'B'")
            for k in ("archetype", "theme", "topic", "asks", "lifted"):
                v = need(p, e, k, where)
                if v: texts.append((f"{where} {k}", v, "prose" if k in ("lifted",) else "label"))
            if isinstance(e.get("band_sub"), str): texts.append((f"{where} band_sub", e["band_sub"], "label"))
            if isinstance(e.get("lifted"), str) and e["lifted"].lower().startswith("what lifted"):
                p.add(f"{where} lifted", "leave out 'What lifted this essay:'; the builder prints it")
            check_pipeline(p, e.get("architecture"), f"{where} architecture", CW - 20, texts)
            ln = need(p, e, "lenses", where, dict)
            if ln is not None:
                hub, sp = ln.get("hub"), ln.get("spokes")
                if not isinstance(hub, str) or not hub.strip():
                    p.add(f"{where} lenses", "'hub' is missing")
                elif not isinstance(sp, list) or not 4 <= len(sp) <= 9 or not all(isinstance(s, list) and len(s) == 2 and all(isinstance(x, str) and x.strip() for x in s) for s in sp):
                    p.add(f"{where} lenses", "'spokes' must list 4 to 9 [lens, few words] pairs, in the order the essay uses them")
                else:
                    texts.append((f"{where} lenses hub", hub, "label"))
                    for i, s in enumerate(sp, 1): texts += [(f"{where} lens {i}", s[0], "label"), (f"{where} lens {i}", s[1], "label")]
                    for what, n in hub_fit(plain(hub), [(plain(a), plain(b)) for a, b in sp]):
                        p.add(f"{where} lenses {what}", f"is cut off (room for {n} line{'s' if n > 1 else ''}); shorten it")
            pill_texts = [str(e.get("archetype", "")).upper(), "125 MARKS · 1,000 TO 1,200 WORDS"] + ([e["pill"].upper()] if isinstance(e.get("pill"), str) and e["pill"] else [])
            es = need(p, e, "essay", where, list)
            if es is not None:
                n = check_answer(p, es, f"{where} model essay", th, st, texts)
                ok = ESSAY_MIN <= n <= ESSAY_MAX
                report.append(f"{where} model essay: {n:,} words (allowed {ESSAY_MIN:,} to {ESSAY_MAX:,}){'' if ok else '  <-- outside the limit'}")
                if not ok:
                    p.add(f"{where} model essay", f"{n:,} words; it must be {ESSAY_MIN:,} to {ESSAY_MAX:,} words")
        if pills_width(pill_texts) > CW - 22:
            p.add(f"{where} pill", "the tags under the question run off the box; shorten 'pill'")
    # every character must be drawable in the fonts this machine has
    allt = EMOJI.sub("", "".join(plain(t) for _, t, _ in texts))     # emojis are reported by the voice check
    for fnt in (F["sans"], F["sansB"]):
        bad = can_draw(allt, fnt)
        if bad:
            p.add("characters", f"{' '.join(repr(c) for c in bad)} cannot be drawn in {F['sans_src']}; write them in words (for example 'Rs' or 'rupees')")
            break
    vp = voice_problems(texts)
    for where, what in vp:
        p.add(where, what)
    report.append(f"Voice check: {len(vp)} problems")
    return p, report, th


# ------------------------------------------------------------------ the brief
def legend_block(st, what):
    legend = " &nbsp; ".join(f"<font color='{c}'><b>{k}</b></font>" for k, c in NOTE_COLOURS.items())
    return [Paragraph("HOW TO READ THE MARGIN", st["labelA"]), Spacer(1, 3), Paragraph(legend, st["small"]), Spacer(1, 3),
            Paragraph(f"A highlighted phrase in the model {what} carries a small red number. The note with the same number sits in the margin beside that paragraph.", st["small"]),
            Spacer(1, 10)]


def skeleton_rows(rows, st):
    return [Paragraph(f"<b>{to_html(k)}.</b> {to_html(v)}", st["bodyL"]) for k, v in rows]


def ammo_box(ammo, th, st, gap):
    am = [Paragraph("AMMUNITION", st["labelA"]), Spacer(1, 3)]
    for a in ammo:
        am.append(Paragraph(f"<b>{to_html(a['source'].rstrip('.'))}.</b> {to_html(a['line'])}", st["small"])); am.append(Spacer(1, gap))
    return box(am, th, fill=th["pale"], pad=9)


def motive(text, th, st):
    return box([Paragraph(to_html(text), st["motive"])], th, fill=th["deep"], pad=12)


def answer_rows(paras, th):
    return [(to_html(x["text"], th), [(n["n"], n["tag"], to_html(n["text"], marks=False)) for n in x.get("notes", [])]) for x in paras]


def sociology_story(d, th, st):
    ev = d["events"]
    rows = d.get("contents") or [[str(i), f"Paper {e['paper']}", f"<b>{to_html(e['title'])}</b>", to_html(e["question_summary"])] for i, e in enumerate(ev, 1)]
    s = [NextPageTemplate("page"), Spacer(1, 10), Paragraph("TODAY IN THIS ISSUE", st["labelA"]), Spacer(1, 4),
         grid([["#", "Paper", "The event", "The probable question"]] + rows, [8 * mm, 18 * mm, 62 * mm, CW - 88 * mm], th), Spacer(1, 10)]
    s += legend_block(st, "answer")
    s.append(motive(d["motivation"], th, st))
    for i, e in enumerate(ev, 1):
        limit = LIMITS[e["marks"]]
        s.append(PageBreak())
        s.append(band(f"EVENT {i}  ·  PAPER {e['paper']}  ·  {to_html(e['syllabus']).upper()}", th, sub=to_html(e["title"]))); s.append(Spacer(1, 8))
        s.append(Paragraph("THE PROBABLE QUESTION", st["labelA"])); s.append(Spacer(1, 3))
        pills = [(f"PAPER {e['paper']}", th["primary"], colors.white), (f"{e['marks']} MARKS · {limit} WORDS", th["accent"], th["deep"])]
        if e.get("pill"): pills.append((plain(e["pill"]).upper(), th["tint"], th["primary"]))
        s.append(box([Paragraph("“" + to_html(e["question"]) + "”", st["q"]), Spacer(1, 5), Pills(pills)], th, fill=th["pale"], rule=th["accent"], pad=9))
        s.append(Spacer(1, 9))
        sk = [Paragraph(f"THE SKELETON ({limit} words)", st["h3"]), Spacer(1, 3)] + skeleton_rows(e["skeleton"], st)
        sk += [Spacer(1, 4), Paragraph(f"<i>What sets the top answers apart: {to_html(e['sets_apart'])}</i>", st["apart"]),
               Spacer(1, 6), Paragraph("THE CHAIN", st["label"]), Spacer(1, 3),
               Pipeline(th, [(n["label"].upper(), plain(n["title"]), plain(n["text"])) for n in e["chain"]], width=CW - 20, h=28 * mm)]
        s.append(box(sk, th, fill=colors.white, border=th["support"], pad=10)); s.append(Spacer(1, 10))
        n = sum(len(plain(x["text"]).split()) for x in e["answer"])
        s.append(CondPageBreak(95 * mm))
        s.append(box([Paragraph(f"THE MODEL ANSWER, WITH THE EXAMINER'S NOTES  ·  {n} words (limit {limit})", st["count"])], th, fill=th["pale"], border=th["accent"], pad=6))
        s.append(Spacer(1, 6))
        s.append(numbered_margin(answer_rows(e["answer"], th), th, st)); s.append(Spacer(1, 8))
        s.append(ammo_box(e["ammunition"], th, st, 3)); s.append(Spacer(1, 9))
        t = e["thinker"]
        head = f"<b>{to_html(t['name'])}</b>" + (f" ({to_html(t['dates'])})" if t.get("dates") else "")
        s.append(KeepTogether([Paragraph("THINKER OF THE DAY", st["labelA"]), Spacer(1, 3),
                               box([Paragraph(head, st["h3"]), Paragraph(to_html(t["text"]), st["small"])], th, fill=th["soft"], rule=th["primary"], pad=9)]))
        s.append(Spacer(1, 10))
        s.append(motive(e["practice"], th, st))
    return s


def essay_story(d, th, st):
    tp = d["topics"]
    rows = d.get("contents") or [[str(i), f"{e['section']} · {to_html(e['archetype'])}", f"<b>{to_html(e['topic'])}</b>", to_html(e["asks"])] for i, e in enumerate(tp, 1)]
    s = [NextPageTemplate("page"), Spacer(1, 10), Paragraph("TODAY IN THIS ISSUE", st["labelA"]), Spacer(1, 4),
         grid([["#", "Section", "The topic, as set", "What it asks"]] + rows, [8 * mm, 26 * mm, 76 * mm, CW - 110 * mm], th), Spacer(1, 10)]
    s += legend_block(st, "essay")
    s.append(motive(d["motivation"], th, st))
    for i, e in enumerate(tp, 1):
        s.append(PageBreak())
        s.append(band(f"TOPIC {i}  ·  SECTION {e['section']}  ·  {to_html(e['theme']).upper()}", th, sub=to_html(e["band_sub"]) if e.get("band_sub") else None))
        s.append(Spacer(1, 8))
        s.append(Paragraph("THE TOPIC, AS SET", st["labelA"])); s.append(Spacer(1, 3))
        pills = [(plain(e["archetype"]).upper(), th["primary"], colors.white), ("125 MARKS · 1,000 TO 1,200 WORDS", th["accent"], colors.white)]
        if e.get("pill"): pills.append((plain(e["pill"]).upper(), th["tint"], th["primary"]))
        s.append(box([Paragraph(to_html(e["topic"]), st["topic"]), Spacer(1, 5), Pills(pills)], th, fill=th["pale"], rule=th["accent"], pad=10))
        s.append(Spacer(1, 9))
        sk = [Paragraph("THE SKELETON", st["h3"]), Spacer(1, 3)] + skeleton_rows(e["skeleton"], st)
        sk += [Spacer(1, 4), Paragraph(f"<i>What sets the top essays apart: {to_html(e['sets_apart'])}</i>", st["apart"]),
               Spacer(1, 6), Paragraph("THE ARCHITECTURE", st["label"]), Spacer(1, 3),
               Pipeline(th, [(n["label"].upper(), plain(n["title"]), plain(n["text"])) for n in e["architecture"]], width=CW - 20, h=25 * mm)]
        s.append(box(sk, th, fill=colors.white, border=th["support"], pad=10)); s.append(Spacer(1, 8))
        ln = e["lenses"]
        s.append(KeepTogether([Paragraph("THE LENSES, IN THE ORDER TO USE THEM (CLOCKWISE FROM THE TOP)", st["label"]), Spacer(1, 2),
                               HubSpoke(th, plain(ln["hub"]), [(plain(a), plain(b)) for a, b in ln["spokes"]], h=74 * mm)]))
        s.append(PageBreak())
        n = sum(len(plain(x["text"]).split()) for x in e["essay"])
        s.append(box([Paragraph(f"THE MODEL ESSAY, WITH THE EXAMINER'S NOTES  ·  {n:,} words (limit 1,000 to 1,200)", st["count"])], th, fill=th["pale"], border=th["accent"], pad=6))
        s.append(Spacer(1, 6))
        s.append(numbered_margin(answer_rows(e["essay"], th), th, st)); s.append(Spacer(1, 8))
        s.append(box([Paragraph(f"<b>What lifted this essay:</b> {to_html(e['lifted'])}", st["lifted"])], th, fill=th["pale"], border=th["accent"], pad=8))
        s.append(Spacer(1, 9))
        s.append(ammo_box(e["ammunition"], th, st, 2))
        if e.get("practice"):
            s.append(Spacer(1, 10)); s.append(motive(e["practice"], th, st))
    return s


def build(d, out):
    th = THEMES[d["desk"]]; st = styles(th)
    issue = str(d["issue"]).strip().lstrip("#")
    issue = issue.zfill(3) if issue.isdigit() else issue
    doc = make_doc(out, th, issue, d["date"].strip())
    doc.build(sociology_story(d, th, st) if d["desk"] == "sociology" else essay_story(d, th, st))
    return doc.page


def main(argv):
    if len(argv) < 3 or argv[2].startswith("-") and argv[2] != "--check":
        print(__doc__); return 2
    try:
        d = json.load(open(argv[1], encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"PROBLEMS (1):\n 1. the content file cannot be read as JSON: {e}"); return 1
    problems, report, th = validate(d if isinstance(d, dict) else {})
    print(f"Fonts: {F['sans_src']} and {F['serif_src']}")
    for line in report:
        print(line)
    if problems:
        print(f"\nPROBLEMS ({len(problems)}): fix the content and run again. The PDF was not built.")
        for i, x in enumerate(problems, 1):
            print(f"{i:>2}. {x}")
        return 1
    if argv[2] == "--check":
        print("\nAll checks passed (check only; no PDF built)."); return 0
    pages = build(d, argv[2])
    print(f"\nAll checks passed. Built {argv[2]}: {pages} pages, {os.path.getsize(argv[2]) // 1024} KB.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
