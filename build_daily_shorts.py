#!/usr/bin/env python3
"""
Daily Shorts orchestrator - builds and schedules the day's 10 Shorts.

From ONE day's video_script.json it produces a 10-slot lineup of distinct Shorts
(different angles on the same 2 events), 4 voiced + 6 silent-with-music, and
uploads each scheduled to publish staggered across the day (so they trickle out,
not dump). It drives make_short.py (render) and upload_short.py (upload) per slot,
each in its own build dir so nothing collides. Every slot is best-effort: one
failure never stops the rest, and this whole script is additive/non-blocking to
the main brief-video-telegram run.

USAGE
  # production (runs in the daily workflow, keys present):
  python3 build_daily_shorts.py video_script.json

  # local preview (no keys): render all 10 as silent+music, do not upload:
  python3 build_daily_shorts.py video_script.json --preview --no-upload
  python3 build_daily_shorts.py video_script.json --preview --no-upload --limit 2

Slot times and the voiced/silent split are config constants below - easy to tune.
The SAME engine serves Essay Desk via --desk essay (see DESKS).
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

import make_short as ms   # reuse extract_events / generate_script / template / styles

HERE = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------
# Per-desk config (Sociology now; Essay mirrors this in Phase 4)
# ----------------------------------------------------------------------------
DESKS = {
    "sociology": {
        "playlist": "Sociology Desk - Shorts",
        "handle": "@upscdesk_sociology",
    },
    "essay": {
        "playlist": "Essay Desk - Shorts",
        "handle": "@upscdesk_essay",
    },
}

IST_OFFSET = datetime.timedelta(hours=5, minutes=30)
# Publish window (IST). The day's Shorts are spread evenly across it, so a small
# --limit still trickles out across the day instead of clumping in the morning.
DAY_START_IST = (9, 0)
DAY_END_IST = (21, 0)


def slot_times(n):
    """n publish times (HH:MM IST) spread evenly across the window."""
    if n <= 1:
        return ["12:00"]
    s = DAY_START_IST[0] * 60 + DAY_START_IST[1]
    e = DAY_END_IST[0] * 60 + DAY_END_IST[1]
    out = []
    for i in range(n):
        m = round(s + (e - s) * i / (n - 1))
        out.append(f"{m // 60:02d}:{m % 60:02d}")
    return out


# The lineup: (type, voiced, source). source: "today" or "evergreen".
# ORDERED BY VALUE so a --limit keeps the best ones and a voiced+music mix:
#   --limit 2 -> flagship (voice) + concept (music)
#   --limit 4 -> + deep (voice) + thinker (music)
#   full 10   -> 4 voiced + 6 silent-with-music
LINEUP = [
    ("flagship", True,  "today"),       # marquee 2-event Short (voiced)
    ("concept",  False, "today"),       # concept-in-30s (music)
    ("deep",     True,  "today"),       # event 1 deep-dive (voiced)
    ("thinker",  False, "evergreen"),   # thinker of the day (music)
    ("upgrade",  True,  "today"),       # 14 -> 19 (voiced)
    ("pyq",      False, "evergreen"),   # PYQ autopsy (music)
    ("deep2",    True,  "today"),       # event 2 deep-dive (voiced)
    ("paper",    False, "today"),       # Paper 1 or 2? (music)
    ("concept2", False, "evergreen"),   # concept of the day (music)
    ("quote",    False, "evergreen"),   # one quote, one answer (music)
]


# ----------------------------------------------------------------------------
# Parse a day's script into rich events (concept, thinkers, bridge, question)
# ----------------------------------------------------------------------------
def parse_day(data):
    slides = data["slides"]
    n = len(slides)
    events = []
    for i, s in enumerate(slides):
        if s.get("type") != "topic_title":
            continue
        seg = list(s.get("bullets", [])) + [s.get("heading", "")]
        ev = {"event": s.get("heading", ""), "paper": "", "concept": "",
              "thinkers": [], "thinker": "", "thinker_tag": "",
              "bridge": [], "question": ""}
        for j in range(i + 1, n):
            t = slides[j].get("type")
            if t == "topic_title":
                break
            seg += list(slides[j].get("bullets", [])) + [slides[j].get("heading", "")]
            if t == "concept" and not ev["concept"]:
                ev["concept"] = slides[j].get("heading", "")
            if t == "thinker":
                h = slides[j].get("heading", "")
                parts = re.split(r'\s[-–]\s', h, maxsplit=1)
                nm = parts[0].strip()
                tg = parts[1].strip() if len(parts) > 1 else ""
                ev["thinkers"].append({"name": nm, "tag": tg,
                                       "tradition": ms.tradition(nm)})
            if t == "answer_bridge" and not ev["bridge"]:
                ev["bridge"] = [b for b in slides[j].get("bullets", []) if b]
            if t == "question" and not ev["question"]:
                ev["question"] = slides[j].get("heading", "") or \
                    (slides[j].get("bullets", [""]) or [""])[0]
        ev["paper"] = ms.detect_paper(seg)
        if ev["thinkers"]:
            ev["thinker"] = ev["thinkers"][0]["name"]
            ev["thinker_tag"] = ev["thinkers"][0]["tag"]
        events.append(ev)
    return events


def anchors_phrase(ev):
    names = [t["name"] for t in ev.get("thinkers", [])][:2]
    return " and ".join(names) if names else ev.get("thinker", "the key thinker")


def ev_for_frame(ev, chip):
    """Trim an event dict down to what make_short's event chrome needs, + a chip."""
    return {"event": ev["event"], "paper": ev.get("paper", ""),
            "concept": ev.get("concept", ""), "thinkers": ev.get("thinkers", []),
            "thinker": ev.get("thinker", ""), "thinker_tag": ev.get("thinker_tag", ""),
            "chip": chip, "line": ""}


# ----------------------------------------------------------------------------
# Script builders (each returns a make_short short_script dict)
# ----------------------------------------------------------------------------
def _wrap(style, hook, events, payoff, cta):
    return {"style": style["name"], "style_label": style["label"],
            "hook": hook, "events": events, "payoff": payoff, "cta": cta}


def sc_flagship(data, events, style):
    ev = ms.extract_events(data["slides"], 2)
    scr = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        scr = ms.generate_script(ev, style, data["issue_no"])
    if not scr:
        scr = ms.template_script(ev, style)
    return scr


def sc_deep(data, events, style, idx=0):
    ev = events[idx]
    e = ev_for_frame(ev, "DEEP DIVE")
    e["line"] = (f"{ev['event']}. To everyone else, current affairs. To you, "
                 f"{ev['paper'] or 'the syllabus'}: {ev['concept'].lower()}. "
                 f"Anchor it to {anchors_phrase(ev)}, and you are already writing a 19.")
    return _wrap(style,
                 f"One event, decoded like a topper would. {ev['event']}.",
                 [e],
                 "That is how you turn a headline into a sociology answer.",
                 "Full model answer, free on Telegram.")


def sc_upgrade(data, events, style, idx=0):
    ev = events[idx]
    bridge = ev.get("bridge", [])
    b14 = next((b for b in bridge if b.strip().startswith(("14", "1 4"))), "")
    b19 = next((b for b in bridge if b.strip().startswith(("19", "1 9"))), "")
    b14 = re.sub(r'^\s*14[:\s]*', '', b14).strip()
    b19 = re.sub(r'^\s*19[:\s]*', '', b19).strip()
    e = ev_for_frame(ev, "14 -> 19")
    e["line"] = (f"On {ev['event']}, a 14 just {b14 or 'describes the event'}. "
                 f"A 19 {b19 or 'adds the thinker and the concept'}. "
                 f"That single move, {anchors_phrase(ev)}, is the difference.")
    return _wrap(style,
                 f"Why your answer scores a 14, not a 19. {ev['event']}.",
                 [e],
                 "Same event. Five extra marks. Every single day.",
                 "The full 19-mark script is on Telegram.")


def sc_concept(data, events, style, idx=0):
    ev = events[idx]
    e = ev_for_frame(ev, "CONCEPT IN 30s")
    e["line"] = (f"{ev['concept']}. In {ev['paper'] or 'the syllabus'}. "
                 f"Seen today in {ev['event']}. Anchor: {anchors_phrase(ev)}.")
    return _wrap(style,
                 f"One concept, 30 seconds. {ev['concept']}.",
                 [e],
                 "One concept a day. That is how the syllabus gets small.",
                 "Full notes on Telegram.")


def sc_paper(data, events, style):
    evs = []
    for i, ev in enumerate(events[:2]):
        e = ev_for_frame(ev, "PAPER 1 OR 2?")
        e["line"] = (f"{ev['event']}. Paper 1 or Paper 2? Answer: "
                     f"{ev['paper'] or 'both'}. Because {ev['concept'].lower()}.")
        evs.append(e)
    return _wrap(style,
                 "Paper 1 or Paper 2? Most aspirants guess. You will know.",
                 evs,
                 "Place the event in the right paper. Then the marks follow.",
                 "Full mapping on Telegram.")


def sc_thinker(data, events, style, idx=0):
    ev = events[idx]
    th = (ev.get("thinkers") or [{"name": ev.get("thinker", "the thinker"),
                                  "tag": ev.get("thinker_tag", ""),
                                  "tradition": ""}])[0]
    e = {"event": th["name"], "paper": ev.get("paper", ""),
         "concept": th.get("tag") or ev.get("concept", ""),
         "thinkers": [th], "thinker": th["name"], "thinker_tag": "",
         "chip": "THINKER", "line": ""}
    trad = th.get("tradition", "")
    e["line"] = (f"{th['name']}, {('the ' + trad + ' anchor') if trad else 'your anchor'}. "
                 f"{th.get('tag') or ev.get('concept','')}. "
                 f"Deploy it on {ev['event']}, and the examiner notices.")
    return _wrap(style,
                 f"Know this thinker, score higher. {th['name']}.",
                 [e],
                 "One thinker a day. Your quotation arsenal, growing.",
                 "Full thinker notes on Telegram.")


def sc_pyq(data, events, style, idx=0):
    ev = events[idx]
    q = ev.get("question") or f"Examine the sociology of {ev['event']}."
    e = ev_for_frame(ev, "PROBABLE QUESTION")
    e["line"] = (f"Your Mains 2026 question. {q} Open with {ev['concept'].lower()}, "
                 f"anchor {anchors_phrase(ev)}, close with a way forward.")
    return _wrap(style,
                 "This could be your Mains 2026 question.",
                 [e],
                 "Predict the question. Pre-write the structure. Walk in calm.",
                 "Full model answer on Telegram.")


def sc_quote(data, events, style, idx=0):
    ev = events[idx]
    e = ev_for_frame(ev, "ONE QUOTE, ONE ANSWER")
    e["line"] = (f"When you write on {ev['concept'].lower()}, do not summarise. "
                 f"Deploy {anchors_phrase(ev)}. One precise line, and the paragraph lifts.")
    return _wrap(style,
                 "One quote can lift a whole answer.",
                 [e],
                 "Collect lines, not just facts. That is a topper's notebook.",
                 "The full arsenal is on Telegram.")


BUILDERS = {
    "flagship": lambda d, e, s: sc_flagship(d, e, s),
    "deep":     lambda d, e, s: sc_deep(d, e, s, 0),
    "deep2":    lambda d, e, s: sc_deep(d, e, s, 1 if len(e) > 1 else 0),
    "upgrade":  lambda d, e, s: sc_upgrade(d, e, s, 0),
    "concept":  lambda d, e, s: sc_concept(d, e, s, 0),
    "concept2": lambda d, e, s: sc_concept(d, e, s, 1 if len(e) > 1 else 0),
    "paper":    lambda d, e, s: sc_paper(d, e, s),
    "thinker":  lambda d, e, s: sc_thinker(d, e, s, 0),
    "pyq":      lambda d, e, s: sc_pyq(d, e, s, 0),
    "quote":    lambda d, e, s: sc_quote(d, e, s, 1 if len(e) > 1 else 0),
}


# ============================================================================
# ESSAY DESK - same engine, one-topic content model (Claret & Gold theme).
# Essay video reuses the slide tokens with essay meanings: topic_title = the
# topic; concept = DECODE/DIMENSIONS; thinker = ANCHOR; answer_bridge = CRAFT;
# question = MODEL LINE. So an Essay Short teaches: this one-line topic is a full
# essay - here is the decode, a dimension, the anchor, the craft move.
# ============================================================================
def parse_essay(data):
    slides = data["slides"]
    ess = {"topic": "", "decode": "", "dimensions": [], "anchors": [],
           "craft": [], "model": ""}
    for s in slides:
        t = s.get("type")
        h = s.get("heading", "")
        bl = [b for b in s.get("bullets", []) if b]
        if t == "topic_title" and not ess["topic"]:
            ess["topic"] = h
        elif t == "concept":
            if not ess["decode"]:
                ess["decode"] = h            # first concept slide = the DECODE
            else:
                ess["dimensions"].append(h)  # later concept slides = DIMENSIONS
        elif t == "thinker":
            ess["anchors"].append(re.split(r'\s[-–]\s', h, maxsplit=1)[0].strip())
        elif t == "answer_bridge" and not ess["craft"]:
            ess["craft"] = bl
        elif t == "question" and not ess["model"]:
            ess["model"] = h or (bl[0] if bl else "")
    return ess


def usable_essay(e):
    return bool(e and e.get("topic"))


def e_scene(topic, chip, strip_label, concept, anchor_names, line):
    return {"event": topic, "chip": chip, "strip_label": strip_label,
            "concept": concept, "paper": "",
            "thinkers": [{"name": n} for n in anchor_names if n],
            "thinker": (anchor_names[0] if anchor_names else ""),
            "thinker_tag": "", "line": line}


def _wrap_e(style, hook, ev, payoff, cta):
    return {"style": style["name"], "style_label": style["label"],
            "hook": hook, "events": [ev], "payoff": payoff, "cta": cta}


def es_flagship(data, ess, style):
    topic, decode = ess["topic"], ess["decode"] or "what it truly asks"
    a0 = ess["anchors"][0] if ess["anchors"] else "a sourced anchor"
    dim = ess["dimensions"][0] if ess["dimensions"] else "many lenses"
    line = (f"{topic}. This is not a slogan. It is a full essay. Decode it: {decode}. "
            f"Build the dimensions, deploy {a0}, hold one thesis to the very end.")
    ev = e_scene(topic, "DECODE THIS TOPIC", "THE THESIS", decode, [a0], line)
    return _wrap_e(style, "You read a one-line topic. A topper reads a full essay.",
                   ev, "Decode, argue one thesis, build the dimensions, close with a vision.",
                   "Two full model essays, free on Telegram.")


def es_dimensions(data, ess, style):
    dims = ess["dimensions"][:3] or ["social", "ethical", "philosophical"]
    line = (f"On {ess['topic']}, do not stay one-dimensional. Move through "
            f"{', '.join(dims)}. Each lens answers what the last one raised.")
    ev = e_scene(ess["topic"], "THE DIMENSIONS", "BUILD THESE LENSES",
                 " / ".join(dims), ess["anchors"][:1], line)
    return _wrap_e(style, "An average essay has one lens. A top essay has six.",
                   ev, "Multidimensional, not a data dump. That is the difference.",
                   "The full dimension map is on Telegram.")


def es_craft(data, ess, style):
    craft = ess["craft"]
    tip = craft[0] if craft else "engage the counter view before you resolve it"
    line = (f"The one craft move on {ess['topic']}: {tip}. "
            f"That single turn is what separates a 60 from a 75.")
    ev = e_scene(ess["topic"], "THE CRAFT MOVE", "HOW IT SCORES",
                 tip, ess["anchors"][:1], line)
    return _wrap_e(style, "Knowledge does not score this paper. Craft does.",
                   ev, "Decode, balance, resolve. Craft is the whole game.",
                   "The full craft guide is on Telegram.")


def es_anchor(data, ess, style):
    a0 = ess["anchors"][0] if ess["anchors"] else "one vivid, sourced example"
    line = (f"When you write on {ess['topic']}, do not stay abstract. "
            f"Deploy {a0} as evidence, then interpret it. Vivid beats vague.")
    ev = e_scene(ess["topic"], "THE ANCHOR", "DEPLOY THIS", a0, [a0], line)
    return _wrap_e(style, "A vague essay states. A vivid essay shows.",
                   ev, "Anchors are evidence, not decoration. Interpret every one.",
                   "The full anchor bank is on Telegram.")


def es_modelline(data, ess, style):
    ml = ess["model"] or f"Open {ess['topic']} with an image, not a definition."
    line = (f"A model opening for {ess['topic']}. {ml} "
            f"Never open with a dictionary definition.")
    ev = e_scene(ess["topic"], "MODEL LINE", "OPEN LIKE THIS", ml,
                 ess["anchors"][:1], line)
    return _wrap_e(style, "The first line decides if the examiner leans in.",
                   ev, "A magnetic opening, a held thesis, a resolving close.",
                   "Full model intros on Telegram.")


def es_counter(data, ess, style):
    line = (f"The trap on {ess['topic']} is a one-sided essay. Engage the strongest "
            f"counter view honestly, then resolve it. Balance is not weakness, it is maturity.")
    ev = e_scene(ess["topic"], "THE COUNTERPOINT", "ENGAGE THE OTHER SIDE",
                 "Balance, then resolve", ess["anchors"][:1], line)
    return _wrap_e(style, "A one-sided essay caps your marks. Balance breaks the ceiling.",
                   ev, "Thesis, antithesis, synthesis. That is a mature essay.",
                   "Full balance drills on Telegram.")


ESSAY_LINEUP = [
    ("flagship",  True,  "today"),      # decode the topic (voiced)
    ("dimensions", False, "today"),     # the lenses (music)
    ("craft",     True,  "today"),      # the craft move (voiced)
    ("anchor",    False, "today"),      # the anchor (music)
    ("modelline", True,  "today"),      # model opening (voiced)
    ("hook",      False, "today"),      # opening options (music)
    ("counter",   True,  "today"),      # the counterpoint (voiced)
    ("anchor2",   False, "evergreen"),  # anchor of the day (music)
    ("dim2",      False, "evergreen"),  # dimension of the day (music)
    ("quote",     False, "evergreen"),  # one line, one essay (music)
]

ESSAY_BUILDERS = {
    "flagship":   es_flagship, "dimensions": es_dimensions, "craft": es_craft,
    "anchor":     es_anchor,   "modelline":  es_modelline,  "hook": es_modelline,
    "counter":    es_counter,  "anchor2":    es_anchor,     "dim2": es_dimensions,
    "quote":      es_anchor,
}

# Per-desk plan: how to parse a day, the lineup, the builders, and usability test.
DESK_PLAN = {
    "sociology": {"parse": parse_day, "lineup": LINEUP, "builders": BUILDERS,
                  "usable": lambda p: bool(p)},
    "essay":     {"parse": parse_essay, "lineup": ESSAY_LINEUP, "builders": ESSAY_BUILDERS,
                  "usable": usable_essay},
}


# ----------------------------------------------------------------------------
# Evergreen source (optional): a folder of past video_script JSONs. If absent,
# evergreen slots fall back to today's material (a different angle), so the day
# still yields 10 Shorts without an archive committed yet.
# ----------------------------------------------------------------------------
def evergreen_data(today_data, slot_i):
    arch = os.path.join(HERE, "archive")
    if os.path.isdir(arch):
        files = sorted(f for f in os.listdir(arch) if f.endswith(".json"))
        if files:
            pick = files[slot_i % len(files)]
            try:
                return json.load(open(os.path.join(arch, pick)))
            except Exception:
                pass
    return today_data   # graceful fallback


# ----------------------------------------------------------------------------
# Scheduling
# ----------------------------------------------------------------------------
def publish_at_utc(run_dt_utc, ist_hhmm):
    hh, mm = (int(x) for x in ist_hhmm.split(":"))
    ist_now = run_dt_utc + IST_OFFSET
    slot_ist = ist_now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    slot_utc = slot_ist - IST_OFFSET
    # if that time already passed today, publish immediately (return None)
    if slot_utc <= run_dt_utc + datetime.timedelta(minutes=5):
        return None
    return slot_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("--desk", default="sociology", choices=list(DESKS))
    ap.add_argument("--preview", action="store_true",
                    help="render voiced slots as silent+music too (local, no keys)")
    ap.add_argument("--no-upload", action="store_true", help="build only, do not upload")
    ap.add_argument("--limit", type=int, help="only the first N slots (testing)")
    ap.add_argument("--work", default="shorts_work")
    args = ap.parse_args()

    cfg = DESKS[args.desk]
    plan = DESK_PLAN[args.desk]
    data = json.load(open(args.json_path))
    issue = f"{int(data['issue_no']):03d}"
    parsed = plan["parse"](data)
    if not plan["usable"](parsed):
        print("Today's script has nothing to build from; skipping.")
        return 0
    run_dt = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)
    lineup = plan["lineup"][:args.limit] if args.limit else plan["lineup"]
    times = slot_times(len(lineup))
    print(f"[{args.desk}] issue {issue}: building {len(lineup)} Shorts (run {run_dt}Z)")


    built = uploaded = 0
    for i, (stype, voiced, source) in enumerate(lineup):
        ist = times[i]
        style = ms.STYLES[(int(data["issue_no"]) + i) % len(ms.STYLES)]
        src_data = data if source == "today" else evergreen_data(data, i)
        src_parsed = parsed if source == "today" else plan["parse"](src_data)
        if not plan["usable"](src_parsed):
            src_data, src_parsed = data, parsed
        try:
            script = plan["builders"][stype](src_data, src_parsed, style)
        except Exception as ex:
            print(f"  slot {i+1:02d} {stype}: script build failed ({ex}); skipping")
            continue

        slotdir = os.path.join(args.work, f"slot_{i:02d}_{stype}")
        os.makedirs(slotdir, exist_ok=True)
        sf = os.path.join(slotdir, "script.json")
        json.dump(script, open(sf, "w"), ensure_ascii=False, indent=2)

        # write the source json where make_short can find it (issue-based build dir)
        src_json = os.path.join(slotdir, "src.json")
        json.dump(src_data, open(src_json, "w"), ensure_ascii=False)

        cmd = [sys.executable, os.path.join(HERE, "make_short.py"), src_json,
               "--script-file", sf, "--build-dir", slotdir, "--slot", str(i),
               "--desk", args.desk]
        if voiced and not args.preview:
            cmd.append("--synced")          # production voiced: same-voice TTS
        else:
            cmd.append("--silent")          # silent + music bed
        print(f"  slot {i+1:02d} {stype:9s} {'VOICE' if voiced else 'music'} "
              f"@ {ist} IST -> render")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"     render failed: {r.stderr.strip()[-300:]}")
            continue
        si = f"{int(src_data['issue_no']):03d}"
        mp4 = os.path.join(slotdir, f"issue_{si}", "short", f"short_issue_{si}.mp4")
        meta = os.path.join(slotdir, f"issue_{si}", "short", "short_meta.txt")
        cover = os.path.join(slotdir, f"issue_{si}", "short", "cover.png")
        if not os.path.exists(mp4):
            print("     no mp4 produced (voiced slot without key?); skipping")
            continue
        built += 1

        if args.no_upload:
            continue
        pub = publish_at_utc(run_dt, ist)
        up = [sys.executable, os.path.join(HERE, "upload_short.py"),
              "--video", mp4, "--meta", meta, "--playlist", cfg["playlist"]]
        if os.path.exists(cover):
            up += ["--thumbnail", cover]
        if pub:
            up += ["--publish-at", pub]
        else:
            up += ["--privacy", "public"]
        ru = subprocess.run(up, capture_output=True, text=True)
        ok = ru.returncode == 0 and "URL:" in ru.stdout
        print(f"     upload {'scheduled ' + pub if pub else 'public now'}: "
              f"{'ok' if ok else 'see log'}")
        if ok:
            uploaded += 1

    print(f"\n[{args.desk}] built {built}/{len(lineup)} Shorts, "
          f"uploaded {uploaded}. (best-effort; failures skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
