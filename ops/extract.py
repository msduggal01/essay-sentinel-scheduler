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
"""
import json, os, re, sys, time, urllib.request

API = "https://api.anthropic.com/v1/sessions"
H = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
     "anthropic-beta": "managed-agents-2026-04-01", "content-type": "application/json"}
ROUNDS = 2


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
        "The video script could not be read from your last message. " + why +
        " Send the complete video script JSON again, as one object between "
        "VIDEO_SCRIPT_JSON_BEGIN=== and ===VIDEO_SCRIPT_JSON_END, with nothing before or "
        "after those markers and no commentary inside them. Do not shorten it."}]}]})


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


if __name__ == "__main__":
    sid, out = sys.argv[1], sys.argv[2]
    for attempt in range(ROUNDS + 1):
        script, why = find(sid)
        if script:
            json.dump(script, open(out, "w"), ensure_ascii=False, indent=1)
            print(f"video script recovered on attempt {attempt + 1}: issue {script.get('issue_no')}")
            sys.exit(0)
        if attempt == ROUNDS:
            break
        print(f"attempt {attempt + 1}: {why}\nasking the agent to send it again")
        ask_again(sid, why)
        settle(sid)
    raise SystemExit(f"the video script could not be recovered after {ROUNDS + 1} attempts: {why}")
