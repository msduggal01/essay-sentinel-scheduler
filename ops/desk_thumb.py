#!/usr/bin/env python3
"""
desk_thumb.py - the long video's YouTube thumbnail in the UPSC Desk design system.

  python3 ops/desk_thumb.py video_script.json            # writes build/issue_N/thumb.png
  python3 ops/desk_thumb.py video_script.json --out x.png --variant T4 --no-llm

render_video.py has already drawn its PIL thumbnail at build/issue_N/thumb.png. This replaces
it with a Remotion still of remotion/src/DeskThumb.tsx (1280 x 720, header H2, one of the six
layouts T1 to T6). If anything here fails, the PIL thumbnail stays where it is, a ::warning::
says so, and the script still exits 0: a thumbnail is never a reason to lose the day's upload.

  hook     at most six words from the essay topic (its key phrase), a statement or a question,
           from one small Claude call (claude-sonnet-5, as ops/reel_props.py); checked in code
           (six words, no "script" or "candidate", no dashes, emojis or "!", not a label), three
           tries; failing that, the key phrase cut to six words at a word boundary
  accent   the hook's key words, a substring of it, in gold
  word     the topic's key word (at most 12 letters, e.g. "Ballot"), for T2 (giant word) and
           T5 (stamp); none means T2 and T5 are skipped that day
  layout   pseudo-random from a hash of the issue number, never the previous issue's
  plate    assets/thumb/plate.jpg (the Sociology art library's social.jpg); without it a plain
           claret gradient. T4 and T6 use no art.

The rules are in docs/THUMBNAILS.md.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import yt_meta   # noqa: E402  the real topic (thumbnail.topic, a heading that is not a label, the spoken line)

MODEL = os.environ.get("THUMB_MODEL", "claude-sonnet-5")
LAYOUTS = ["T1", "T2", "T3", "T4", "T5", "T6"]
NEEDS_WORD = {"T2", "T5"}
NO_WORD = ["T1", "T3", "T4", "T6"]
STOP = {"a", "an", "the", "of", "to", "in", "on", "and", "or", "but", "for", "with", "at", "by", "from",
        "its", "his", "her", "their", "our", "your", "is", "are", "be", "can", "must", "still", "that", "this"}
REMOTION = os.path.join(ROOT, "remotion")
PLATE_SRC = os.path.join(ROOT, "assets", "thumb", "plate.jpg")
PLATE = "thumb_plate.jpg"            # its name in remotion/public (git-ignored, copied in at render time)
YT_MAX_BYTES = 2 * 1024 * 1024       # YouTube refuses a custom thumbnail over 2 MB


def warn(msg):
    print(f"::warning::{msg}")


# ---------------------------------------------------------------------------------------------
# the layout: one of T1..T6 per issue, never the previous issue's
# ---------------------------------------------------------------------------------------------
def _h(n, salt):
    return int(hashlib.sha256(f"essay-thumb-{salt}-{n}".encode()).hexdigest(), 16)


def layout_for(issue, has_word):
    """v(n) = v(n-1) + 1 + h(n) % 5 (mod 6) never repeats v(n-1). When v(n) is T2 or T5 and the
    day has no key word, the stand-in sub(n) is one of T1, T3, T4, T6 that is neither v(n-1),
    sub(n-1) nor v(n+1). Whichever of v or sub each day actually used, two days in a row never
    match, and no state is kept: it is a pure function of the issue number."""
    n = max(1, int(re.sub(r"\D", "", str(issue)) or 1))
    v = {0: 0}
    for k in range(1, n + 2):
        v[k] = (v[k - 1] + 1 + _h(k, "v") % 5) % 6
    sub = {0: "T1"}
    for k in range(1, n + 1):
        avoid = {LAYOUTS[v[k - 1]], sub[k - 1], LAYOUTS[v[k + 1]]}
        left = [t for t in NO_WORD if t not in avoid]
        sub[k] = left[_h(k, "sub") % len(left)]
    main = LAYOUTS[v[n]]
    if main in NEEDS_WORD and not has_word:
        return sub[n]
    return main


# ---------------------------------------------------------------------------------------------
# the words: hook, accent, key word
# ---------------------------------------------------------------------------------------------
SYSTEM = """You write the words on one YouTube thumbnail for the Essay Desk, a daily UPSC Essay
masterclass. Serious, exam-wise and anonymous: no hype, no emojis, no exclamation marks, no em
or en dashes or hyphens between words, British spelling. A written answer is an "essay", never
a "script"; the person writing it is an "aspirant", never a "candidate".

Return ONLY a JSON object:
{"hook": "When the Ballot Outpaces the Home", "accent": "Outpaces the Home", "word": "Ballot"}

hook    at most SIX words, the essay topic's key phrase as a statement or a question, in title
        case, read in a glance on a phone. It names the topic's own idea (never "Today's topic",
        never the exam, never the desk). No full stop at the end; a question ends with "?".
accent  the hook's key words, two or three words copied exactly from the hook (a substring of it).
word    the topic's one key word, a single word of at most 12 letters taken from the topic or
        the hook (e.g. "Ballot", "Wisdom", "Library"); "" if no single word carries the topic."""


def call(user):
    body = {"model": MODEL, "max_tokens": 8000, "system": SYSTEM, "output_config": {"effort": os.environ.get("THUMB_EFFORT", "low")},
            "messages": [{"role": "user", "content": user}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                 headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    text = "".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
    print(f"desk_thumb: {MODEL}: stop {r.get('stop_reason')}, {len(text)} chars of text")
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


_EMOJI = re.compile(r"[\U0001F000-\U0001FFFF☀-➿⬀-⯿️]")


def check(c, topic):
    """the reasons a reply cannot be used ([] when it can), and the cleaned reply"""
    errs = []
    hook = re.sub(r"\s+", " ", str(c.get("hook") or "")).strip().rstrip(".")
    accent = re.sub(r"\s+", " ", str(c.get("accent") or "")).strip()
    word = str(c.get("word") or "").strip()
    if not hook:
        errs.append("hook: missing")
    if len(hook.split()) > 6:
        errs.append(f"hook: {len(hook.split())} words, at most six")
    if len(hook) > 44:
        errs.append(f"hook: {len(hook)} characters, keep it under 45")
    for k, v in (("hook", hook), ("accent", accent)):
        if re.search(r"[—–!]|--|\s-\s|\w-\w", v): errs.append(f"{k}: dash, hyphen or exclamation mark")
        if _EMOJI.search(v): errs.append(f"{k}: emoji")
        if re.search(r"\bscripts?\b", v, re.I): errs.append(f"{k}: says 'script'; it is an essay")
        if re.search(r"\bcandidates?\b", v, re.I): errs.append(f"{k}: says 'candidate'; the writer is an aspirant")
    if re.search(r"today'?s\s+(upsc\s+)?(essay\s+)?topic", hook, re.I) or yt_meta._LABEL.match(hook) or re.search(r"\bupsc\b|essay desk", hook, re.I):
        errs.append("hook: a label, not the topic's own idea")
    if not accent or accent not in hook:
        errs.append("accent: must be copied exactly from the hook (a substring of it)")
    elif accent == hook:
        errs.append("accent: the key words only, not the whole hook")
    # the key word is a bonus: a bad one is dropped (T2 and T5 are then skipped), never retried for
    if word and not (re.fullmatch(r"[A-Za-z]{3,12}", word) and re.search(rf"\b{re.escape(word)}", f"{hook} {topic}", re.I)):
        print(f"desk_thumb: key word {word!r} dropped (one word of 3 to 12 letters from the topic or hook)")
        word = ""
    return errs, {"hook": hook, "accent": accent, "word": word}


def fallback(data, topic):
    """the key phrase (the video title's middle, or the agent's thumbnail text when that is
    shorter and the title's is over six words), cut to six words at a word boundary; the accent
    its longest word; no key word"""
    def usable(s):
        return s and not yt_meta._LABEL.match(s) and not re.search(r"today'?s\s+topic", s, re.I)
    key = yt_meta.key_phrase(data)
    tt = yt_meta.clean(data.get("thumbnail_text"))
    if not usable(key):
        key = tt if usable(tt) else topic
    elif len(key.split()) > 6 and usable(tt) and 2 <= len(tt.split()) <= 6:
        key = tt
    key = re.sub(r"[—–!]|--|\s-\s", " ", key)
    key = re.sub(r"[^\w\s'’?,]", " ", key)
    words = key.split()[:6]
    while len(words) > 2 and words[-1].lower().strip(",") in STOP:
        words.pop()
    hook = " ".join(words).strip(" ,;:")
    accent = max(hook.split(), key=len).strip("?,") if hook else ""
    return {"hook": hook or "The Essay, Decoded", "accent": accent or "Decoded", "word": ""}


def words_for(data, use_llm=True):
    topic = yt_meta.essay_topic(data).strip()
    key = yt_meta.key_phrase(data)
    if use_llm and os.environ.get("ANTHROPIC_API_KEY"):
        user = (f"The essay topic, as set: \"{topic}\"\nThe desk's own short name for it: \"{key}\"\n"
                f"Theme: {yt_meta.theme_of(data)}\nWrite the thumbnail's hook, accent and word.")
        note = ""
        for attempt in range(1, 4):
            try:
                c = call(user + note)
            except Exception as ex:  # noqa: BLE001  a network or API error is one failed try
                print(f"desk_thumb: try {attempt}: {str(ex)[:160]}")
                continue
            errs, out = check(c, topic)
            if not errs:
                print(f"desk_thumb: try {attempt}: {out}")
                return out, "claude"
            print(f"desk_thumb: try {attempt} sent back: {errs}")
            note = "\n\nYour last reply was sent back:\n- " + "\n- ".join(errs) + f"\nIt was: {json.dumps(c)}"
        warn("the thumbnail hook could not be written in three tries; it is the key phrase cut to six words")
    elif use_llm:
        warn("no ANTHROPIC_API_KEY; the thumbnail hook is the key phrase cut to six words")
    out = fallback(data, topic)
    errs, out2 = check(out, topic)
    return (out2 if not [e for e in errs if e.startswith("hook")] else out), "fallback"


# ---------------------------------------------------------------------------------------------
def date_of(data):
    """'06 October 2026' -> '6 October 2026'"""
    return re.sub(r"^0(\d)\b", r"\1", str(data.get("date", "")).strip())


def props_for(data, use_llm=True, variant=None):
    w, src = words_for(data, use_llm)
    issue = str(data.get("issue_no", ""))
    v = variant or layout_for(issue, bool(w["word"]))
    plate = ""
    if v not in ("T4", "T6") and os.path.exists(PLATE_SRC):
        os.makedirs(os.path.join(REMOTION, "public"), exist_ok=True)
        shutil.copyfile(PLATE_SRC, os.path.join(REMOTION, "public", PLATE))
        plate = PLATE
    return {"desk": "essay", "header": "H2", "v": v, "hook": w["hook"], "accent": w["accent"], "thinker": w["word"],
            "issue": issue, "date": date_of(data), "plate": plate, "_source": src}


def render(props, out):
    """npx remotion still DeskThumb -> out (PNG, 1280 x 720, at most 2 MB); raises on any failure"""
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        pj = os.path.join(td, "props.json")
        json.dump({k: v for k, v in props.items() if not k.startswith("_")}, open(pj, "w"))
        tmp = os.path.join(td, "thumb.png")
        cmd = ["npx", "remotion", "still", "src/index.ts", "DeskThumb", tmp, f"--props={pj}", "--log=warn"]
        r = subprocess.run(cmd, cwd=REMOTION, capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not os.path.exists(tmp):
            raise RuntimeError(f"remotion still exited {r.returncode}: {(r.stderr or r.stdout)[-600:]}")
        im = Image.open(tmp)
        if im.size != (1280, 720):
            raise RuntimeError(f"the still is {im.size}, not 1280 x 720")
        if os.path.getsize(tmp) > YT_MAX_BYTES * 0.95:
            im.convert("RGB").save(tmp, optimize=True)
        if os.path.getsize(tmp) > YT_MAX_BYTES * 0.95:
            im.convert("RGB").quantize(256, dither=Image.Dither.NONE).save(tmp, optimize=True)
        if os.path.getsize(tmp) > YT_MAX_BYTES * 0.95:
            raise RuntimeError(f"the still is {os.path.getsize(tmp)} bytes, over YouTube's 2 MB")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        shutil.move(tmp, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", help="default build/issue_N/thumb.png")
    ap.add_argument("--variant", choices=LAYOUTS)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--props", help="use these props (JSON file) as they are")
    a = ap.parse_args()

    data = json.load(open(a.script))
    issue = data.get("issue_no")
    out = a.out or os.path.join("build", f"issue_{issue}", "thumb.png")
    try:
        props = json.load(open(a.props)) if a.props else props_for(data, not a.no_llm, a.variant)
        print("desk_thumb: props", json.dumps(props, ensure_ascii=False))
        keep = None
        if os.path.exists(out) and not a.out:
            keep = os.path.join(os.path.dirname(out), "thumb_pil.png")
            shutil.copyfile(out, keep)
        render(props, out)
        json.dump(props, open(os.path.splitext(out)[0] + "_props.json", "w"), indent=1, ensure_ascii=False)
        print(f"desk_thumb: {props['v']} written to {out} ({os.path.getsize(out)} bytes)" + (f"; the PIL one kept as {keep}" if keep else ""))
    except Exception as ex:  # noqa: BLE001  the PIL thumbnail stays
        warn(f"The Remotion thumbnail failed ({str(ex)[:300]}); the YouTube thumbnail is render_video.py's PIL one today")
    return 0


if __name__ == "__main__":
    sys.exit(main())
