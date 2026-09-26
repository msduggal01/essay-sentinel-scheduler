#!/usr/bin/env python3
"""
humanize.py - rewrite a video script's narration so it sounds like a teacher, not a generator.

  python3 humanize.py prelims_script.json                # rewrites in place
  python3 humanize.py prelims_script.json --out x.json --diff

The agent writes correct scripts in a recognisably generated voice: comma-chained
lists, triads ("one word, three legal lives, one still open"), antithesis flourishes
("end on implementation, not on the judgment"), clipped fragments ("It has not."),
and spoken Title Case. This pass rewrites ONLY the spoken narration, one call for the
whole script, under guardrails checked in code, slide by slide:

  - every on-screen element gets a timing cue that is really spoken in the new narration
    (the rewrite picks new cues from its own sentences, so stiff cue phrases can go)
  - every number in the original is still there (dates, marks, counts, Act years)
  - no dashes; length stays within 70 to 135 percent of the original
  - a cold open still begins with its headline sentence

A slide that fails any check keeps its original narration. If the rewritten script
validates worse than the original, the whole rewrite is dropped. It can make the voice
better; it cannot cost the day's video.
"""
import json, os, re, sys, time, urllib.error, urllib.request

try:
    import validate_script as vs           # the GS desk ships a full validator
except ImportError:                        # other desks have their own envelopes
    import script_text as vs

MODEL = os.environ.get("HUMANIZE_MODEL", "claude-sonnet-5")

VOICE = """You rewrite the spoken narration of a UPSC current-affairs video so that it sounds like an
experienced teacher talking to one serious student across a desk. The facts are already right.
Your only job is the voice.

How the teacher sounds:
- Full, connected sentences with ordinary verbs. Some short, most medium, the odd long one.
- Plain words. Contractions are fine (it's, hasn't, you'll). Calm, never selling.
- Uses a colon or a full stop where a list begins, never a chain of commas.
- Talks about the question and the answer, not about "moves", "levers" or "dimensions".

Never write these (they are what makes it sound generated):
- Triads and rhythmic lists used for effect: "one word, three legal lives, one still open",
  "the chronology, the federal edge, and the implementation gap" as a closing flourish.
- Antithesis flourishes: "end on implementation, not on the judgment", "not X but Y",
  "it is not A, it is B".
- Clipped dramatic fragments: "It has not." "Time." "One live case, four syllabus neighbours."
- Aphorisms and slogans as sentence closers, and rhetorical questions.
- Title Case in speech ("The Forest Case Is Not Over Yet" is spoken as an ordinary sentence).
- Meta-labels like "Two moves matter most", "Three lines carry real marks", "X is doing two jobs".
- Em dashes, en dashes, double hyphens, emojis, exclamation marks.
- Sentences that start with a bare verb and no subject ("Named the case. Corrected the error.").
  Give every sentence a subject. Do not keep the original's sentence shapes; say it the way you
  would say it aloud to a student.

Before and after (a different topic on purpose; never reuse these sentences):
BEFORE: "Three dimensions carry the answer, the mandate, the transmission lag, and the credibility gap."
AFTER:  "A good answer covers three things: what the RBI is legally required to target, why rate cuts take months to reach borrowers, and why markets doubted the signal this time."
BEFORE: "Walk the branches of the 1934 Act, then the 2016 amendment brought in the target, then the MPC arrived, and now the band is under review. One mandate, three lives, one still open."
AFTER:  "Follow the branches from the 1934 Act. The 2016 amendment brought in the inflation target, the Monetary Policy Committee followed, and the band itself is now under review."

Timing cues. Each slide lists "cues": on-screen elements that appear when a phrase is spoken.
For every cue, return a NEW cue phrase of two to six consecutive words copied exactly from YOUR
narration, at the moment that element should appear (where you start talking about it).

Hard rules. Breaking any of them means your rewrite of that slide is thrown away:
1. Keep every fact, name, number and date exactly, and write numbers the way the original does
   (digits stay digits). Add nothing new; drop nothing factual.
2. Return a cue phrase for every cue path, each one appearing word for word in your narration.
3. If must_start is given, the narration must begin with that sentence (capitalisation may change).
4. Keep roughly the same length (between 80 and 120 percent of the original words).
5. Keep "[breath]" tags only where a real pause belongs; one or two per slide at most.

Return ONLY a JSON array, one object per slide:
[{"id": <slide id>, "narration": "<rewritten narration>", "cues": {"<cue path>": "<phrase from your narration>"}}]"""


def _cues(slide):
    """{path: phrase} for the anchors this slide's on-screen elements fire on today."""
    out = []
    lay = slide.get("layout")
    vs.walk_anchors(slide.get("content") or {}, out)
    return {path: a for path, a in out
            if not (lay in ("prelims_question", "prelims_answer") and path.startswith(".statements"))}


def _set(obj, path, value):
    """Set content[path] where path looks like '.nodes[2].anchor' or '.strip.remember_anchor'."""
    keys = re.findall(r"\.([A-Za-z_][\w]*)|\[(\d+)\]", path)
    cur = obj
    for i, (k, idx) in enumerate(keys):
        key = k if k else int(idx)
        if i == len(keys) - 1:
            cur[key] = value
        else:
            cur = cur[key]


def _numbers(t):
    return sorted(re.findall(r"\d+(?:\.\d+)?", t))


def _parse(text):
    """First JSON array of slide objects in the reply. A greedy regex is not enough: the
    narration itself contains [breath] tags, which look like arrays."""
    dec = json.JSONDecoder(); i = 0
    while True:
        i = text.find("[", i)
        if i < 0: return []
        try:
            obj, _ = dec.raw_decode(text, i)
            if isinstance(obj, list) and obj and isinstance(obj[0], dict) and "id" in obj[0]:
                return obj
        except json.JSONDecodeError:
            pass
        i += 1


def _call(payload):
    key = os.environ["ANTHROPIC_API_KEY"]
    body = json.dumps({"model": MODEL, "max_tokens": 16000, "system": VOICE,
                       "messages": [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    for attempt in range(1, 4):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=300).read())
            got = _parse("".join(b.get("text", "") for b in d.get("content", [])))
            if got: return got
            print(f"humanize: attempt {attempt}: no slide array in the reply (stop_reason {d.get('stop_reason')})")
        except urllib.error.HTTPError as e:
            print(f"humanize: HTTP {e.code} {e.read()[:200]!r}")
            if e.code < 500 and e.code != 429: raise
        except (TimeoutError, OSError, json.JSONDecodeError) as e:
            print(f"humanize: attempt {attempt} failed: {e}")
        time.sleep(15 * attempt)
    raise RuntimeError("humanize: model call failed three times")


def check(slide, new, cues):
    """Reasons this rewrite must be rejected; empty means accept."""
    old = slide.get("narration", "")
    why = []
    nn = vs.norm(re.sub(r"\[(breath|exhales)\]", " ", new))
    for path in _cues(slide):
        c = str((cues or {}).get(path, ""))
        if not c or vs.norm(c) not in nn: why.append(f"cue {path} missing from the new narration")
        elif not 1 <= len(c.split()) <= 16: why.append(f"cue {path} is {len(c.split())} words")
    if _numbers(old) != _numbers(new): why.append(f"numbers changed {_numbers(old)} -> {_numbers(new)}")
    if re.search(r"[\u2014\u2013]|--", new): why.append("dash")
    r = len(new.split()) / max(1, len(old.split()))
    if not 0.70 <= r <= 1.35: why.append(f"length ratio {r:.2f}")
    if slide.get("layout") == "cold_open":
        head = (slide.get("content") or {}).get("headline", "")
        if head and not nn.startswith(vs.norm(head)): why.append("cold open no longer starts with the headline")
    return why


BATCH = 8


def humanize(d, rewrite=_call):
    slides = [s for s in (d.get("slides") or []) if s.get("narration")]
    got = {}
    for i in range(0, len(slides), BATCH):
        payload = [{"id": s["id"], "layout": s.get("layout"), "narration": s["narration"], "cues": _cues(s),
                    **({"must_start": (s.get("content") or {}).get("headline", "")} if s.get("layout") == "cold_open" else {})}
                   for s in slides[i:i + BATCH]]
        for x in rewrite(payload):
            try: got[int(x["id"])] = x
            except (KeyError, TypeError, ValueError): pass
    out = json.loads(json.dumps(d)); taken = kept = 0
    for s in out["slides"]:
        x = got.get(s["id"])
        new = str((x or {}).get("narration", "")).strip()
        if not new: kept += 1; continue
        why = check(s, new, x.get("cues"))
        if why:
            kept += 1; print(f"humanize: slide {s['id']} kept original ({'; '.join(why)})"); continue
        s["narration"] = new
        for path, c in (x.get("cues") or {}).items():
            if path in _cues(s): _set(s["content"], path, c)
        taken += 1
    before = len(vs.validate(d)[0]); after = len(vs.validate(out)[0])
    if after > before:
        print(f"humanize: rewrite validates worse ({before} -> {after} errors); keeping the original script")
        return d, 0
    print(f"humanize: {taken} slides rewritten, {kept} kept as written")
    return out, taken


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = args[0]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else src
    d = json.load(open(src))
    new, n = humanize(d)
    if "--diff" in sys.argv:
        for a, b in zip(d["slides"], new["slides"]):
            if a.get("narration") != b.get("narration"):
                print(f"\n[{a['id']} {a.get('layout')}]\n  BEFORE: {a['narration']}\n  AFTER:  {b['narration']}")
    json.dump(new, open(out, "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
