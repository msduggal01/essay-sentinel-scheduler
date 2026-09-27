#!/usr/bin/env python3
"""
reel_props.py - the words for the day's Reel, from the day's own script.

  python3 ops/reel_props.py sociology video_script.json reel_props.json
  python3 ops/reel_props.py essay     video_script.json reel_props.json

One Claude call writes the few on-screen lines the Reel needs (remotion/src/DeskShort.tsx);
code decides everything that is a rule, and checks every line before it is used:

  sociology  the news, concept and thinker; the question as set; an average opening of
             three short lines with a margin note each; the three lines that replace them.
             The mark always opens at 7, 8 or 9 of 20 by issue and reaches 17 to 19.
  essay      the topic verbatim; the literal reading and the real one; the lenses; a flat
             opening of three lines with notes; the three lines of an opening that works.

A written answer is an answer (an essay on the Essay desk), never a script; the person
writing it is an aspirant. No em or en dashes, no exclamation marks. A reply that breaks a
check is sent back with the reasons, four tries at most; after that the script exits 1 and
the day falls back to the old Short.
"""
import json, os, re, sys, urllib.request

MODEL = os.environ.get("REEL_MODEL", "claude-sonnet-5")
DIRECTIVES = ["Critically examine", "Critically analyse", "Critically evaluate", "Compare and contrast", "Discuss",
              "Examine", "Analyse", "Evaluate", "Comment", "Elucidate", "Explain", "Assess"]


def spoken_text(d):
    """the day's slides as plain text for the model: type, heading, bullets, narration"""
    out = []
    for s in d.get("slides", []):
        if s.get("type") in ("intro", "outro", "recap"):
            continue
        nar = re.sub(r"\[(breath|exhales)\]", "", s.get("narration", "")).strip()
        extra = " ".join(f"{k}: {s[k]}" for k in ("thinker", "concept") if s.get(k))
        out.append(f"[{s.get('type')}] {s.get('heading', '')}\n  bullets: {'; '.join(s.get('bullets') or [])}\n  {extra}\n  narration: {nar}")
    return "\n".join(out)


def first(d, typ):
    return next((s for s in d.get("slides", []) if s.get("type") == typ), {})


def paper_of(d):
    txt = json.dumps(d.get("slides", [])[:8])
    m = re.search(r"\bPaper\s*(1|2|I{1,2}|one|two)\b", txt, re.I)
    if not m:
        return "1"
    return {"i": "1", "ii": "2", "one": "1", "two": "2"}.get(m.group(1).lower(), m.group(1))


def band(issue):
    i = int(re.sub(r"\D", "", str(issue)) or 0)
    return [7, 8, 9][i % 3], [18, 19, 17][i % 3]


SOC_SCHEMA = """{
 "headline": "Gig workers strike for a minimum wage.",
 "news": {"title": "Bengaluru, August 2026", "sub": "Delivery riders stop work across the city"},
 "concept": {"title": "The precariat", "sub": "Work without security or a ladder"},
 "thinker": {"title": "Guy Standing", "sub": "The Precariat, 2011"},
 "question": "Is the gig worker a new class? Answer with reference to platform work in India.",
 "directive": "Discuss",
 "average": [
  {"text": "Gig workers face many issues", "note": "no concept"},
  {"text": "like low pay in Bengaluru.", "note": "only describes"},
  {"text": "Laws must protect them.", "note": "no thinker"}
 ],
 "better": [
  "Standing calls them a class in the making.",
  "The Bengaluru strike is that class finding its voice.",
  "Yet no shared workplace makes solidarity fragile."
 ]
}
(That is an example from another day, to show the shape and the length of every field; write
today's. Limits in characters: headline 50, news.title 30, news.sub 50, concept.title 28,
concept.sub 46, thinker.title 28, thinker.sub 40, question 190, average text 30 and note 16,
better 52. average and better have exactly three items. directive is one of: DIRECTIVES.)"""

ESSAY_SCHEMA = """{
 "topic": "A ladder is also a list of the people it leaves below.",
 "literal": "An essay about ambition and success.",
 "decode": "Every rise ranks someone lower. Who designs the ladder?",
 "hub": "Mobility and its costs",
 "lenses": [
  {"title": "Social", "sub": "caste, class and the first rung"},
  {"title": "Economic", "sub": "credentials as gatekeepers"},
  {"title": "Political", "sub": "reservation and its critics"},
  {"title": "Ethical", "sub": "merit and luck"},
  {"title": "Psychological", "sub": "the fear of falling"}
 ],
 "average": [
  {"text": "Ambition is important in life", "note": "restates topic"},
  {"text": "and helps people succeed.", "note": "no tension"},
  {"text": "Hard work is the key.", "note": "no thesis"}
 ],
 "better": [
  "Every coaching hall has a back row.",
  "Some climbed there; some were placed.",
  "A ladder measures the wall it leans on."
 ]
}
(That is an example from another day, to show the shape and the length of every field; write
today's, for today's topic. Limits in characters: literal 46, decode 72, hub 30, lens title 14,
lens sub 34, average text 30 and note 16, better 46. Four to six lenses; average and better have
exactly three items. topic is today's topic exactly as set.)"""

RULES = """You write the on-screen lines for one UPSC Desk Reel, from the day's {desk} script below.
The Reel is shown on a phone for about forty seconds; every line is read in a glance, so length
limits are hard limits. Serious, exam-wise and anonymous: no hype, no emojis, no exclamation
marks, no em dashes or en dashes (use a comma or a full stop), British spelling. A written answer
is an "{work}", never a "script"; the person writing it is an "aspirant". Use only facts, names,
works and years that appear in the script; never invent a figure, a quotation or a year.
{extra}
Return ONLY a JSON object of exactly this shape:
{schema}"""

SOC_EXTRA = """The chain is always news, then concept, then thinker. The average opening is a believable
average: it describes the news, names no concept and cites no thinker, and its notes say so in
two or three words each ("no concept", "only describes", "no thinker" or the like). The better
lines open with the thinker or the concept, use the news as evidence, and read as sociology."""

ESSAY_EXTRA = """The lenses are the dimensions the script itself names, in its order. The flat opening
restates the topic, has no tension and no thesis; the notes say so. The opening that works begins
with an image or a claim and holds the topic's tension; its three lines read as one opening."""


def call(system, user):
    """One request. Thinking is always on and counts against max_tokens, so the ceiling is
    generous and the effort low: the reply itself is a few hundred tokens."""
    body = {"model": MODEL, "max_tokens": 16000, "system": system, "output_config": {"effort": os.environ.get("REEL_EFFORT", "low")},
            "messages": [{"role": "user", "content": user}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                 headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    text = "".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
    print(f"reel_props: {MODEL}: stop {r.get('stop_reason')}, {(r.get('usage') or {}).get('output_tokens')} output tokens, {len(text)} chars of text")
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def clean_words(v, where, errs):
    if isinstance(v, dict):
        for k, x in v.items(): clean_words(x, f"{where}.{k}", errs)
    elif isinstance(v, list):
        for i, x in enumerate(v): clean_words(x, f"{where}[{i}]", errs)
    elif isinstance(v, str):
        if re.search(r"[—–!]|--", v): errs.append(f"{where}: dash or exclamation mark")
        if re.search(r"\bscripts?\b", v, re.I): errs.append(f"{where}: says 'script'")
        # the person writing the answer is an aspirant; a student in the news is a student
        if where.startswith(("reply.average", "reply.better")) and re.search(r"\b(students?|candidates?)\b", v, re.I):
            errs.append(f"{where}: say aspirant")


def cap(v, n, where, errs):
    if not isinstance(v, str) or not v.strip(): errs.append(f"{where}: missing"); return
    if len(v) > n: errs.append(f"{where}: {len(v)} characters, at most {n}")


def check_soc(c, d):
    errs = []
    clean_words(c, "reply", errs)
    cap(c.get("headline"), 50, "headline", errs)
    for k, a, b in (("news", 30, 50), ("concept", 28, 46), ("thinker", 28, 40)):
        x = c.get(k) or {}
        cap(x.get("title"), a, f"{k}.title", errs); cap(x.get("sub"), b, f"{k}.sub", errs)
    names = " ".join(s.get("thinker", "") + " " + s.get("heading", "") for s in d.get("slides", []) if s.get("type") == "thinker")
    t = (c.get("thinker") or {}).get("title", "")
    if t and t.split()[-1].lower() not in names.lower(): errs.append(f"thinker.title: {t!r} is not a thinker in the script")
    cap(c.get("question"), 190, "question", errs)
    if c.get("directive") not in DIRECTIVES: errs.append(f"directive: must be one of {DIRECTIVES}")
    av, bt = c.get("average") or [], c.get("better") or []
    if len(av) != 3: errs.append("average: exactly three lines")
    for i, l in enumerate(av):
        cap((l or {}).get("text"), 30, f"average[{i}].text", errs); cap((l or {}).get("note"), 16, f"average[{i}].note", errs)
    if len(bt) != 3: errs.append("better: exactly three lines")
    for i, l in enumerate(bt): cap(l, 52, f"better[{i}]", errs)
    return errs


def check_essay(c, d):
    errs = []
    clean_words(c, "reply", errs)
    topic = (first(d, "topic_title").get("heading") or "").strip()
    cap(c.get("topic"), 130, "topic", errs)
    if topic and c.get("topic") and re.sub(r"\W+", " ", c["topic"]).strip().lower() != re.sub(r"\W+", " ", topic).strip().lower():
        errs.append(f"topic: must be the topic exactly as set: {topic!r}")
    cap(c.get("literal"), 46, "literal", errs); cap(c.get("decode"), 72, "decode", errs); cap(c.get("hub"), 30, "hub", errs)
    ls = c.get("lenses") or []
    if not 4 <= len(ls) <= 6: errs.append("lenses: four to six")
    for i, l in enumerate(ls):
        cap((l or {}).get("title"), 14, f"lenses[{i}].title", errs); cap((l or {}).get("sub"), 34, f"lenses[{i}].sub", errs)
    av, bt = c.get("average") or [], c.get("better") or []
    if len(av) != 3: errs.append("average: exactly three lines")
    for i, l in enumerate(av):
        cap((l or {}).get("text"), 30, f"average[{i}].text", errs); cap((l or {}).get("note"), 16, f"average[{i}].note", errs)
    if len(bt) != 3: errs.append("better: exactly three lines")
    for i, l in enumerate(bt): cap(l, 46, f"better[{i}]", errs)
    return errs


def main():
    desk, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
    d = json.load(open(src))
    issue = str(d.get("issue_no", "0"))
    if desk == "sociology":
        system = RULES.format(desk="Sociology Optional", work="answer", extra=SOC_EXTRA,
                              schema=SOC_SCHEMA.replace("DIRECTIVES", ", ".join(DIRECTIVES)))
        check = check_soc
    else:
        topic = (first(d, "topic_title").get("heading") or "").strip()
        system = RULES.format(desk="Essay", work="essay", extra=ESSAY_EXTRA + f"\nThe topic as set is: {topic}", schema=ESSAY_SCHEMA)
        check = check_essay
    user = spoken_text(d)
    c, errs = {}, ["no reply"]
    for attempt in (1, 2, 3, 4):
        try:
            c = call(system, user)
        except Exception as e:
            print(f"reel_props: attempt {attempt} failed: {e}"); continue
        errs = check(c, d)
        if not errs:
            break
        print(f"reel_props: attempt {attempt} rejected (keys: {sorted(c) if isinstance(c, dict) else type(c).__name__}):\n  " + "\n  ".join(errs[:20]))
        user = spoken_text(d) + "\n\nYour previous reply was rejected for these reasons. Fix every one and return the whole object again:\n- " + \
            "\n- ".join(errs[:25]) + "\n\nYour previous reply:\n" + json.dumps(c, ensure_ascii=False)
    if errs:
        sys.exit("reel_props: no usable lines after four attempts; the old Short makes today's Reel")

    if desk == "sociology":
        p = paper_of(d)
        lo, hi = band(issue)
        data = {"desk": "sociology", "eyebrow": f"Sociology Optional · Paper {p}", "hook2": "Is this Sociology?",
                "tag": f"PAPER {p} · 20 MARKS · 250 WORDS", "from": lo, "to": hi, "out": 20,
                "cta_line": "Write this answer, then get it evaluated", "paper": p, **c}
    else:
        data = {"desk": "essay", "eyebrow": "UPSC Essay · 125 Marks", "hook2": "Could you write this essay?",
                "cta_line": "Write this essay, then get it evaluated", **c}
    data["issue"] = issue
    json.dump({"data": data}, open(out, "w"), ensure_ascii=False, indent=1)
    print(f"reel_props: {desk} issue {issue}: " + (data.get("headline") or data.get("topic", "")))


if __name__ == "__main__":
    main()
