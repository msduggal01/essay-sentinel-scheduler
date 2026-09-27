#!/usr/bin/env python3
"""
agent_patch.py - add or replace a marked section in the live Essay agent's system prompt.

  python3 ops/agent_patch.py ops/agent_patches/austerity.md --name AUSTERITY [--apply]

Patches the agent in ESSAY_AGENT_ID, or the one in AGENT_ID when that is set.

Follows the standing rule: GET the live agent and write it to agent_backup.json first,
then (only with --apply) update it with the version as an optimistic lock, so a concurrent
change fails with 409 instead of being overwritten. The section sits between
<<NAME v>> markers, so running again replaces it instead of duplicating it. Prints sizes
and the section position only; the prompt itself carries a live key and is never printed.
"""
import json, os, re, sys, urllib.error, urllib.request

API = "https://api.anthropic.com/v1/agents/"
H = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
     "anthropic-beta": "managed-agents-2026-04-01", "Content-Type": "application/json"}


def call(method, url, body=None):
    req = urllib.request.Request(url, headers=H, method=method, data=json.dumps(body).encode() if body is not None else None)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} HTTP {e.code}: {e.read()[:400]!r}")


def main():
    patch, name = sys.argv[1], sys.argv[sys.argv.index("--name") + 1]
    apply = "--apply" in sys.argv
    # AGENT_ID lets the same patch be applied to another desk's agent; an agent id is an
    # identifier, not a credential, so it can be passed in plainly
    aid = os.environ.get("AGENT_ID") or os.environ["ESSAY_AGENT_ID"]
    agent = call("GET", API + aid)
    json.dump(agent, open("agent_backup.json", "w"), ensure_ascii=False, indent=1)
    sysp = agent.get("system") or ""
    print(f"live agent version {agent.get('version')}, system prompt {len(sysp)} chars; backup written")
    body = open(patch, encoding="utf-8").read().strip()
    start, end = f"<<{name}>>", f"<</{name}>>"
    block = f"{start}\n{body}\n{end}"
    if start in sysp:
        new = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda m: block, sysp, flags=re.S)
        where = "replaced the existing section"
    else:
        # before the first workflow step, so it is read before any work begins
        m = re.search(r"^## Step 1", sysp, flags=re.M)
        new = sysp[:m.start()] + block + "\n\n" + sysp[m.start():] if m else sysp + "\n\n" + block
        where = "inserted before '## Step 1'" if m else "appended at the end"
    print(f"patch: {where}; prompt {len(sysp)} -> {len(new)} chars")
    if new == sysp:
        print("no change"); return
    if not apply:
        print("dry run: not applied"); return
    r = None
    for method in ("POST", "PATCH"):
        try:
            r = call(method, API + aid, {"system": new, "version": agent["version"]}); break
        except SystemExit as e:
            if "HTTP 405" in str(e) or "HTTP 404" in str(e): continue
            raise
    print(f"applied: agent now version {r.get('version')}, system prompt {len(r.get('system') or '')} chars")


if __name__ == "__main__":
    main()
