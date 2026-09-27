#!/usr/bin/env python3
"""
extract.py - pull the day's video script out of the agent's session, and if it is not
there, ask the agent for it again rather than failing the day.

  python3 ops/extract.py <session_id> video_script.json

The Essay pipeline failed on 3, 5 and 6 September with "No valid video-script JSON among
1 sentinel span(s)": the agent had run, but what it emitted between the sentinels would not
parse. One-shot extraction makes any such slip fatal for the whole day. The GS desk solved
this by sending the error back to the same session and letting the agent correct itself,
which fixed 27 of 62 broken anchors in a single round when it was first run there.

The same round trip enforces the desk's words, which the prompt alone did not hold (the
27 September script said a slide "lifts a script into the top band"). Anything the aspirant
sees or hears is checked: the essay is never a "script" and the aspirant never a
"candidate"; no em or en dashes; no emojis outside the Telegram hook. Those go back to the
agent as reasons. "student" is only reported. If the agent has still not fixed them when the
rounds run out, the script is used anyway (the dashes turned into commas) with a warning:
the day's video matters more than one word.

Every message sent back says to send the JSON only, because the session has already done
the day's work: re-running a step on a brief day would email every subscriber twice.
"""
import json, os, re, sys, time, urllib.request

API = "https://api.anthropic.com/v1/sessions"
H = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
     "anthropic-beta": "managed-agents-2026-04-01", "content-type": "application/json"}
ROUNDS = 2
AGAIN_ONLY = (" Send the JSON again only; do not re-run any step, do not send any email again, "
              "and do not archive anything again.")
BANNED = re.compile(r"\b(scripts?|candidates?)\b", re.I)
WARN = re.compile(r"\bstudents?\b", re.I)
DASH = re.compile(r"[\u2014\u2013]|(?<!-)--(?!-)")
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")


def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers=H)
    return json.loads(urllib.request.urlopen(req, timeout=120).read() or "{}")


def texts(data):
    out = []
    def walk(x):
        if isinstance(x, str): out.append(x)
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(data)
    return "\n".join(out)


def seen_text(script):
    """(where, text) for every field an aspirant sees or hears"""
    out = [(k, script.get(k)) for k in ("video_title", "video_description", "thumbnail_text", "telegram_hook")]
    out += [(f"thumbnail.{k}", v) for k, v in (script.get("thumbnail") or {}).items()]
    out += [(f"chapters[{i}]", c.get("title")) for i, c in enumerate(script.get("chapters") or []) if isinstance(c, dict)]
    for s in script.get("slides") or []:
        sid = s.get("id")
        out += [(f"slide {sid} {k}", s.get(k)) for k in ("heading", "narration", "thinker", "concept")]
        out += [(f"slide {sid} bullet {j + 1}", b) for j, b in enumerate(s.get("bullets") or [])]
    return [(w, t) for w, t in out if isinstance(t, str) and t]


def word_check(script):
    """(errors to send back, warnings to report)"""
    errs, warns = [], []
    for where, t in seen_text(script):
        for w in sorted({m.lower() for m in BANNED.findall(t)}):
            errs.append(f'{where} says "{w}"; on this desk it is the essay and the aspirant')
        if DASH.search(t): errs.append(f"{where} has an em or en dash; use a comma or a full stop")
        if EMOJI.search(t) and where != "telegram_hook": errs.append(f"{where} has an emoji")
        if WARN.search(t): warns.append(f'{where} says "student"')
    return errs, warns


def undash(script):
    """the last resort once the rounds are spent: every dash becomes a comma (or 'to' in a range)"""
    def fix(t):
        t = re.sub(r"(\d)\s*[\u2014\u2013]\s*(\d)", r"\1 to \2", t)
        return re.sub(r"\s*(?:[\u2014\u2013]|(?<!-)--(?!-))\s*", ", ", t)
    def walk(x):
        if isinstance(x, str): return fix(x)
        if isinstance(x, list): return [walk(v) for v in x]
        if isinstance(x, dict): return {k: walk(v) for k, v in x.items()}
        return x
    return walk(script)


def find(sid):
    """The last sentinel span that is non-empty and parses to a script. Returns
    (script, why-it-failed) so the reason can be handed back to the agent."""
    blob = texts(call(f"{API}/{sid}/events"))
    spans = re.findall(r"VIDEO_SCRIPT_JSON_BEGIN===(.*?)===VIDEO_SCRIPT_JSON_END", blob, re.S)
    if not spans:
        return None, "No VIDEO_SCRIPT_JSON_BEGIN/END block appeared in the session at all."
    why = f"{len(spans)} sentinel block(s) were present but none parsed."
    for raw in reversed(spans):
        raw = raw.strip()
        if not raw:
            why = "The sentinel block was empty."
            continue
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
        try:
            cand = json.loads(cleaned, strict=False)
        except json.JSONDecodeError as e:
            why = f"The JSON would not parse: {e}"
            continue
        if not isinstance(cand, dict) or not cand.get("issue_no"):
            why = "The JSON parsed but carried no issue_no, so it is not the video script."
            continue
        return cand, None
    return None, why


def ask_again(sid, why):
    call(f"{API}/{sid}/events", {"events": [{"type": "user.message", "content": [{"type": "text", "text":
        "The video script could not be read from your last message. " + why + AGAIN_ONLY +
        " Send the complete video script JSON again, as one object between "
        "VIDEO_SCRIPT_JSON_BEGIN=== and ===VIDEO_SCRIPT_JSON_END, with nothing before or "
        "after those markers and no commentary inside them. Do not shorten it."}]}]})


def ask_words(sid, errs):
    call(f"{API}/{sid}/events", {"events": [{"type": "user.message", "content": [{"type": "text", "text":
        "The video script JSON parsed, but it breaks the desk's word rules in these places:\n- " +
        "\n- ".join(errs[:30]) + "\n\nFix only these words (the essay is an essay, never a script; the "
        "reader is an aspirant, never a candidate or a student; no em or en dashes; no emojis) and "
        "change nothing else." + AGAIN_ONLY + " Emit the complete corrected JSON between "
        "VIDEO_SCRIPT_JSON_BEGIN=== and ===VIDEO_SCRIPT_JSON_END, with nothing before or after "
        "those markers. Do not shorten it."}]}]})


def settle(sid, minutes=12):
    """Wait for the session to go idle and stay there."""
    stable, last, deadline = 0, -1, time.time() + minutes * 60
    while time.time() < deadline:
        time.sleep(20)
        try:
            n = len(call(f"{API}/{sid}/events").get("data", []))
            status = call(f"{API}/{sid}").get("status", "unknown")
        except Exception:
            continue
        if status in ("error", "failed"):
            return False
        stable = stable + 1 if (status == "idle" and n == last) else 0
        last = n
        if stable >= 3:
            return True
    return False


def save(script, out, attempt):
    json.dump(script, open(out, "w"), ensure_ascii=False, indent=1)
    print(f"video script recovered on attempt {attempt + 1}: issue {script.get('issue_no')}")


if __name__ == "__main__":
    sid, out = sys.argv[1], sys.argv[2]
    best = None
    for attempt in range(ROUNDS + 1):
        script, why = find(sid)
        if script:
            errs, warns = word_check(script)
            for w in warns:
                print(f"::warning::{w} (the desk says aspirant)")
            if not errs:
                save(script, out, attempt)
                sys.exit(0)
            best = script
            print(f"attempt {attempt + 1}: the script breaks the word rules:\n  " + "\n  ".join(errs[:30]))
            if attempt == ROUNDS:
                break
            print("asking the agent to correct those words")
            ask_words(sid, errs)
            settle(sid)
            continue
        if attempt == ROUNDS:
            break
        print(f"attempt {attempt + 1}: {why}\nasking the agent to send it again")
        ask_again(sid, why)
        settle(sid)
    if best:
        best = undash(best)
        errs, _ = word_check(best)
        for e in errs:
            print(f"::warning::still in today's script after {ROUNDS} corrections: {e}")
        save(best, out, ROUNDS)
        sys.exit(0)
    raise SystemExit(f"the video script could not be recovered after {ROUNDS + 1} attempts: {why}")
