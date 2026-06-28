#!/usr/bin/env python3
"""
Find a DISTINCT Essay Desk voice in the ElevenLabs Voice Library: Indian-accented,
reflective / warm / storyteller / audiobook narrators (any gender), with IDs +
preview URLs. Audition a few, then set ESSAY_VOICE_ID or pass --voice to render_video.py.

USAGE
  export ELEVENLABS_API_KEY="your_key"
  python3 find_voices.py
"""
import os, sys, json, urllib.request, urllib.error

api_key = os.environ.get("ELEVENLABS_API_KEY")
if not api_key:
    print("Set ELEVENLABS_API_KEY first.")
    sys.exit(1)

def fetch(params):
    url = "https://api.elevenlabs.io/v1/shared-voices?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"xi-api-key": api_key})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

import urllib.parse

# pull a broad set (both genders, literary/narrator descriptors), filter Indian client-side
seen = {}
for query in [
    {"language": "en", "page_size": 100, "search": "indian"},
    {"page_size": 100, "search": "indian storyteller"},
    {"page_size": 100, "search": "audiobook narrator"},
    {"page_size": 100, "search": "calm reflective"},
    {"gender": "female", "page_size": 100, "search": "indian"},
    {"gender": "male", "page_size": 100, "search": "indian narrator"},
]:
    try:
        data = fetch(query)
    except urllib.error.HTTPError as e:
        print("API error:", e.code, e.read().decode("utf-8"))
        continue
    for v in data.get("voices", []):
        blob = " ".join(str(v.get(k, "")) for k in
                        ("accent", "description", "language", "descriptive", "name")).lower()
        if "india" in blob or "hindi" in blob:
            seen[v["voice_id"]] = v

if not seen:
    print("No Indian voices matched. Try browsing the Voice Library on the website instead.")
    sys.exit(0)

print(f"\nFound {len(seen)} candidate Essay Desk voices (Indian-accented):\n" + "=" * 70)
for v in seen.values():
    print(f"\nNAME      : {v.get('name')}")
    print(f"VOICE ID  : {v.get('voice_id')}")
    print(f"ACCENT    : {v.get('accent')}   AGE: {v.get('age')}   DESC: {v.get('descriptive','')}")
    desc = (v.get('description') or '').strip().replace('\n', ' ')
    if desc:
        print(f"ABOUT     : {desc[:160]}")
    print(f"PREVIEW   : {v.get('preview_url')}")
print("\n" + "=" * 70)
print("To audition: paste a PREVIEW url into your browser.")
print("To use one : export ESSAY_VOICE_ID=<VOICE ID>   (or pass --voice <VOICE ID>)")
