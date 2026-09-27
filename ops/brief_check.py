#!/usr/bin/env python3
"""
brief_check.py - read-only: did the agent really email the brief in this session?

  python3 ops/brief_check.py sesn_...            exit 1 with ::error:: when no send is found
  python3 ops/brief_check.py sesn_... --describe also list the session's event types and tools

On brief days the agent sends the PDF itself, inside its session, one Resend call per
recipient (Step 7 of its prompt), and nothing outside the session looked at whether that
happened: a day whose email failed still showed green. This reads the session's events and
looks for the send as the prompt defines it: a tool call that posts to api.resend.com/emails,
and its result, which prints "Sent <address> <message id>" per recipient and ends with
"Attempts N Successes M of N". A result with at least one message id or M > 0 is a
confirmed send.

It runs after everything else and blocks nothing. The repository is public and so are its
logs, so this prints counts only: never an address, a message id or any of the payload.
"""
import collections, json, os, re, sys, time, urllib.request

API = "https://api.anthropic.com/v1/sessions"
H = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
     "anthropic-beta": "managed-agents-2026-04-01"}
SENT = re.compile(r"\bSent \S+@\S+ [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
TALLY = re.compile(r"Attempts (\d+) Successes (\d+)(?: of (\d+))?")


def get(url):
    for i in range(4):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60).read())
        except Exception as e:
            if i == 3: raise
            print(f"retrying after {type(e).__name__}"); time.sleep(10 * (i + 1))


def events(sid):
    evs, page = [], None
    while True:
        d = get(f"{API}/{sid}/events?limit=500" + (f"&page={page}" if page else ""))
        evs += d.get("data", []); page = d.get("next_page")
        if not page: return evs


def text(x):
    out = []
    def walk(v):
        if isinstance(v, str): out.append(v)
        elif isinstance(v, dict): [walk(w) for w in v.values()]
        elif isinstance(v, list): [walk(w) for w in v]
    walk(x)
    return "\n".join(out)


def check(evs):
    """(calls to Resend, recipients confirmed with a message id, best 'Successes' tally)"""
    uses = {e.get("id"): e for e in evs if "tool_use" in str(e.get("type", ""))}
    resend_ids = {i for i, e in uses.items() if "api.resend.com/emails" in text(e.get("input"))}
    sent, best = 0, (0, 0, 0)
    for e in evs:
        if "tool_result" not in str(e.get("type", "")):
            continue
        t = text(e.get("content", e))
        # the send can be a script the agent wrote to a file and then ran, so a result that
        # carries the tally counts even when its call did not name Resend itself
        if e.get("tool_use_id") not in resend_ids and not TALLY.search(t):
            continue
        sent += len(SENT.findall(t))
        for m in TALLY.finditer(t):
            a, s, n = int(m.group(1)), int(m.group(2)), int(m.group(3) or m.group(1))
            best = max(best, (s, a, n))
    return len(resend_ids), sent, best


if __name__ == "__main__":
    sid = sys.argv[1]
    evs = events(sid)
    calls, sent, (ok, attempts, total) = check(evs)
    if "--describe" in sys.argv:
        print("event types:", dict(collections.Counter(e.get("type") for e in evs).most_common()))
        print("tools:", dict(collections.Counter(e.get("name") for e in evs if "tool_use" in str(e.get("type", ""))).most_common()))
    print(f"brief email: {len(evs)} events, {calls} call(s) to Resend, {sent} recipient(s) with a message id, "
          f"tally {ok} of {total} sent ({attempts} attempts)")
    if sent == 0 and ok == 0:
        print("::error::Brief email not confirmed: no Resend send with a message id in the agent session")
        sys.exit(1)
    if total and ok < total:
        print(f"::warning::Brief email reached {ok} of {total} recipients")
    print("brief email confirmed")
