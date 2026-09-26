#!/usr/bin/env python3
"""
script_text.py - the two helpers humanize.py needs, without a desk's own validator.

The GS desk has validate_script.py, which knows its envelope. The Sociology and Essay
desks have different envelopes, so humanize.py falls back to this: the same text
normaliser and anchor walk, and a validate() that reports nothing.

That makes the humanizer's last safety net a no-op on those desks: it can no longer
compare "did the rewrite validate worse than the original" and drop the whole pass. Every
per-slide guardrail still applies, and a slide that fails any of them keeps its original
narration, so the worst case is a script that reads exactly as it did before.
"""
import re


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", str(s).lower()).split())


def walk_anchors(obj, out, path=""):
    """Every anchor in the slide's content, with the path that identifies it."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if (k == "anchor" or k.endswith("_anchor")) and isinstance(v, str) and v.strip():
                out.append((path + "." + k, v))
            walk_anchors(v, out, path + "." + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_anchors(v, out, f"{path}[{i}]")


def validate(d):
    """No envelope rules here, so nothing to report: (errors, warnings)."""
    return [], []
