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


# key-like values and private endpoints that must never leave the runner
SECRET_PATTERNS = [
    (r"re_[A-Za-z0-9_]{16,}", "re_[MASKED]"),                          # Resend
    (r"sk-[A-Za-z0-9_\-]{20,}", "sk-[MASKED]"),                        # Anthropic, OpenAI
    (r"(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}", "gh_[MASKED]"),
    (r"EAA[A-Za-z0-9]{40,}", "EAA[MASKED]"),                            # Meta
    (r"AIza[0-9A-Za-z_\-]{30,}", "AIza[MASKED]"),                      # Google API key
    (r"xox[abprs]-[A-Za-z0-9\-]{10,}", "xox-[MASKED]"),                # Slack
    (r"https://script\.google\.com/macros/s/[A-Za-z0-9_\-]+", "https://script.google.com/macros/s/[MASKED]"),
    (r"(?i)((?:api[_ ]?key|token|secret|password)[\"']?\s*[=:]\s*\\?[\"']?)([A-Za-z0-9_\-\.]{16,})", r"\1[MASKED]"),
]


def redact(text):
    for p, r in SECRET_PATTERNS:
        text = re.sub(p, r, text)
    return text


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
    # the backup is uploaded as a workflow artifact, so it must never carry the prompt's live
    # keys or private URLs: they are masked here, and nothing is written if any survive
    safe = redact(json.dumps(agent, ensure_ascii=False, indent=1))
    if any(re.search(p, safe) for p, _ in SECRET_PATTERNS):
        raise SystemExit("backup still carries a key-like value after masking; not written")
    open("agent_backup.json", "w").write(safe)
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
