#!/usr/bin/env python3
"""
The Sociology Desk - daily YouTube Short builder (v3: "See the sociology" storyboard).

The Short is a recurring teaching hook, NOT a concept dump. Its single intent,
voiced FRESH every day in a different style:

    "An event happened. Everyone files it under current affairs.
     You file it under Sociology Paper 1.
     Here is the concept, here is the thinker - that is how a 14 becomes a 19."

Each Short takes TWO events from the day's video and connects each
  event -> Paper 1 concept -> thinker -> marks.

The narration is PURPOSE-WRITTEN per day (so the tone, angle and phrasing vary)
and synthesised in the SAME voice as the long video (gad8DmXGyu7hwftX9JqI /
eleven_v3). Word-by-word karaoke captions lock to the speech.

Script source, in priority order:
  1. data["short_script"]            - if the daily agent ever emits one
  2. --script-file PATH              - a hand-authored JSON (used for previews)
  3. ANTHROPIC_API_KEY               - generate one in a rotating STYLE (production)
  4. deterministic template          - last-resort fallback (still varies a little)

Audio:
  --synced (or in production with ELEVENLABS_API_KEY): regenerate with word
  timestamps for frame-perfect karaoke. Without a key it builds a SILENT preview
  with even-split caption timing so the motion/layout can be reviewed.

USAGE
  python3 make_short.py video_script_issue_014.json --script-file scripts/short_014_sample.json
  python3 make_short.py video_script.json --synced          # production, perfect sync
  python3 make_short.py video_script.json --style mentor     # force a style

OUTPUT (under build/issue_NNN/short/)
  short_issue_NNN.mp4   1080x1920, 30fps, H.264/AAC
  short_meta.txt        title / description / tags (#Shorts) for upload_short.py
  short_script.json     the script actually used (for the record)
"""

import argparse
import base64
import os
import re
import sys
import json
import subprocess

from PIL import Image, ImageDraw, ImageFont

# ----------------------------------------------------------------------------
# Voice - MUST match render_video.py so the Short sounds like the long video
# ----------------------------------------------------------------------------
VOICE_ID = "gad8DmXGyu7hwftX9JqI"
MODEL_ID = "eleven_v3"
VOICE_SETTINGS = {"stability": 0.55, "similarity_boost": 0.90,
                  "style": 0.18, "use_speaker_boost": True}

# ----------------------------------------------------------------------------
# Style personas - rotated by issue number so no two days sound the same.
# `label` is the small on-screen tag; `voice` steers the script generator.
# ----------------------------------------------------------------------------
STYLES = [
    {"name": "provocateur", "label": "SAME EVENT. DIFFERENT EYES.",
     "voice": "a sharp wake-up call that challenges the aspirant to stop seeing news and start seeing theory"},
    {"name": "mentor", "label": "A HABIT OF TOPPERS",
     "voice": "a calm, warm senior mentor sharing the one habit that separates toppers"},
    {"name": "myth_buster", "label": "THIS ISN'T CURRENT AFFAIRS",
     "voice": "a myth-buster who insists this is not current affairs, it is sociology in disguise"},
    {"name": "storyteller", "label": "READ THE EVENT LIKE A SOCIOLOGIST",
     "voice": "a vivid storyteller who sets the scene of each event before naming the theory"},
    {"name": "strategist", "label": "WHERE THE MARKS HIDE",
     "voice": "a tactical exam strategist focused on exactly where the extra marks come from"},
    {"name": "contrarian", "label": "EVERYONE ELSE SEES NEWS",
     "voice": "a contrarian: everyone else memorises the event, you decode the structure"},
    {"name": "insider", "label": "THROUGH THE EXAMINER'S EYES",
     "voice": "an examiner revealing what a top answer does that an average one does not"},
    {"name": "rapid", "label": "60 SECONDS, TWO EVENTS, FULL MARKS",
     "voice": "fast, punchy, high-energy, short clauses, relentless momentum"},
]

# ----------------------------------------------------------------------------
# Brand palette (matches render_video.py)
# ----------------------------------------------------------------------------
STEEL     = (30, 58, 95)
DEEPSTEEL = (16, 32, 56)
ICE       = (220, 232, 245)
MIDSTEEL  = (74, 111, 165)
NEAR      = (26, 26, 46)
LIGHTST   = (184, 204, 224)
DIM       = (96, 120, 152)
WHITE     = (255, 255, 255)
AMBER     = (245, 158, 11)
GREEN     = (46, 125, 50)
MOTIF     = (60, 88, 128)    # decorative dots/lines (themed)
BAR       = (40, 60, 90)     # progress-bar track (themed)
STRIP     = (12, 26, 46)     # event bottom strip (themed)

W, H = 1080, 1920
MARGIN = 70
CONTENT_W = W - 2 * MARGIN

CHANNEL_HANDLE = "@upscdesk_sociology"
SUBSCRIBE = os.environ.get("SOC_SUBSCRIBE_URL", "https://subscribe.upscdesk.com/sociology/")

# ----------------------------------------------------------------------------
# Per-desk theme + brand copy. set_desk() rebinds the module globals so every
# render function themes automatically. Sociology = Steel & Amber; the SAME
# engine serves Essay Desk in Claret & Gold.
# ----------------------------------------------------------------------------
DESK_THEMES = {
    "sociology": dict(STEEL=(30, 58, 95), DEEPSTEEL=(16, 32, 56), ICE=(220, 232, 245),
                      MIDSTEEL=(74, 111, 165), LIGHTST=(184, 204, 224),
                      DIM=(96, 120, 152), AMBER=(245, 158, 11),
                      MOTIF=(60, 88, 128), BAR=(40, 60, 90), STRIP=(12, 26, 46)),
    "essay": dict(STEEL=(122, 45, 58), DEEPSTEEL=(70, 26, 34), ICE=(246, 239, 227),
                  MIDSTEEL=(150, 80, 92), LIGHTST=(214, 180, 188),
                  DIM=(150, 110, 120), AMBER=(184, 134, 11),
                  MOTIF=(120, 70, 82), BAR=(90, 45, 55), STRIP=(50, 18, 24)),
}
BRAND_COPY = {
    "sociology": dict(
        wordmark="THE SOCIOLOGY DESK", tagline="UPSC SOCIOLOGY OPTIONAL",
        handle="@upscdesk_sociology", subscribe_env="SOC_SUBSCRIBE_URL",
        subscribe_default="https://subscribe.upscdesk.com/sociology/", voice_env=None,
        hook_l1="It is not current affairs.", hook_l2="It is SOCIOLOGY.",
        payoff_l1="See sociology everywhere.", payoff_l2="That is how a 14 becomes a 19.",
        concept_label="SOCIOLOGY",
        end_title="Turn today's events into 19-mark answers",
        end_bullets=["Both events, full model answers", "Answer skeletons + quotations",
                     "Examiner 14 vs 19 notes"],
        end_sub="Subscribe for the full daily brief",
        meta_title="Is this Sociology?",
        meta_lead="Every event is Sociology - Paper 1 or Paper 2 - if you know where to look.",
        meta_offer="Full model answers, skeletons and the quotation arsenal:",
        hashtags="#UPSC #Sociology #UPSCMains #IAS #Shorts #SociologyOptional",
        tags_seed=["UPSC", "Sociology", "UPSC Mains 2026", "IAS", "Shorts", "Sociology Optional"]),
    "essay": dict(
        wordmark="THE ESSAY DESK", tagline="UPSC ESSAY, DECODED",
        handle="@upscdesk_essay", subscribe_env="ESSAY_SUBSCRIBE_URL",
        subscribe_default="https://subscribe.upscdesk.com/essay/", voice_env="ESSAY_VOICE_ID",
        hook_l1="It is not just a topic.", hook_l2="It is a full ESSAY.",
        payoff_l1="Decode. Argue one thesis. Build.", payoff_l2="That is how you cross 75.",
        concept_label="ESSAY",
        end_title="Turn today's topic into a top essay",
        end_bullets=["Two full model essays", "Dimension maps + anchor bank",
                     "Examiner margin notes"],
        end_sub="Subscribe for the full brief",
        meta_title="Could you write this essay?",
        meta_lead="Every topic is a full essay once you can decode it.",
        meta_offer="Two full model essays, dimension maps and the anchor bank:",
        hashtags="#UPSC #Essay #UPSCEssay #IAS #Shorts #UPSCMains",
        tags_seed=["UPSC", "Essay", "UPSC Essay", "IAS", "Shorts", "UPSC Mains 2026"]),
}
BRAND = BRAND_COPY["sociology"]


def set_desk(desk):
    """Rebind palette + brand globals for the chosen desk."""
    global VOICE_ID, CHANNEL_HANDLE, SUBSCRIBE, BRAND
    global STEEL, DEEPSTEEL, ICE, MIDSTEEL, LIGHTST, DIM, AMBER, MOTIF, BAR, STRIP
    t = DESK_THEMES.get(desk, DESK_THEMES["sociology"])
    STEEL, DEEPSTEEL, ICE = t["STEEL"], t["DEEPSTEEL"], t["ICE"]
    MIDSTEEL, LIGHTST, DIM, AMBER = t["MIDSTEEL"], t["LIGHTST"], t["DIM"], t["AMBER"]
    MOTIF, BAR, STRIP = t["MOTIF"], t["BAR"], t["STRIP"]
    _GRADIENT_CACHE.clear()
    b = BRAND_COPY.get(desk, BRAND_COPY["sociology"])
    BRAND = b
    CHANNEL_HANDLE = b["handle"]
    SUBSCRIBE = os.environ.get(b["subscribe_env"], b["subscribe_default"])
    if b["voice_env"]:
        VOICE_ID = os.environ.get(b["voice_env"], VOICE_ID)

# ----------------------------------------------------------------------------
# Fonts
# ----------------------------------------------------------------------------
REG_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
BOLD_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None


REG_PATH = _first_existing(REG_CANDIDATES)
BOLD_PATH = _first_existing(BOLD_CANDIDATES)


def font(bold, size):
    try:
        return ImageFont.truetype(BOLD_PATH if bold else REG_PATH, size)
    except Exception:
        return ImageFont.load_default()


# ----------------------------------------------------------------------------
# Text helpers
# ----------------------------------------------------------------------------
def text_w(draw, s, fnt):
    return draw.textlength(s, font=fnt)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_w(draw, trial, fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def center_text(d, s, fnt, y, fill):
    d.text((W / 2 - text_w(d, s, fnt) / 2, y), s, font=fnt, fill=fill)


_GRADIENT_CACHE = {}


def vertical_gradient(top_rgb, bot_rgb):
    """Cached: build the gradient column once (it is identical for every frame)
    and return a fresh copy. Pure-Python per-pixel fills would cost minutes
    across ~80 frames otherwise."""
    key = (top_rgb, bot_rgb)
    if key not in _GRADIENT_CACHE:
        col = Image.new("RGB", (1, H))
        cpx = col.load()
        for y in range(H):
            t = y / (H - 1)
            cpx[0, y] = tuple(int(top_rgb[i] + (bot_rgb[i] - top_rgb[i]) * t)
                              for i in range(3))
        _GRADIENT_CACHE[key] = col.resize((W, H))
    return _GRADIENT_CACHE[key].copy()


def pill_center(d, label, cy, fsize, bg, fg, bold=True):
    fnt = font(bold, fsize)
    tw = text_w(d, label, fnt)
    padx, pady = 30, 14
    asc, desc = fnt.getmetrics()
    th = asc + desc
    x0 = W / 2 - (tw + 2 * padx) / 2
    d.rounded_rectangle([x0, cy, x0 + tw + 2 * padx, cy + th + 2 * pady],
                        radius=(th + 2 * pady) // 2, fill=bg)
    d.text((x0 + padx, cy + pady), label, font=fnt, fill=fg)
    return cy + th + 2 * pady


def outline_pill_center(d, label, cy, fsize, color):
    fnt = font(True, fsize)
    tw = text_w(d, label, fnt)
    padx, pady = 26, 12
    asc, desc = fnt.getmetrics()
    th = asc + desc
    x0 = W / 2 - (tw + 2 * padx) / 2
    d.rounded_rectangle([x0, cy, x0 + tw + 2 * padx, cy + th + 2 * pady],
                        radius=(th + 2 * pady) // 2, outline=color, width=3)
    d.text((x0 + padx, cy + pady), label, font=fnt, fill=color)
    return cy + th + 2 * pady


# ----------------------------------------------------------------------------
# Daily visual variant - keeps the steel+amber palette, varies the composition
# ----------------------------------------------------------------------------
def draw_motif(d, variant):
    if variant == 0:                       # dot grid, top-right
        for r in range(5):
            for c in range(6):
                cx, cy = W - 340 + c * 52, 70 + r * 42
                d.ellipse([cx, cy, cx + 11, cy + 11], fill=MOTIF)
    elif variant == 1:                     # diagonal corner stripes, bottom-left
        for i in range(6):
            off = i * 46
            d.line([(0, H - 120 - off), (180 - off, H)], fill=MOTIF, width=8)
    else:                                  # amber corner tabs
        d.rectangle([0, 0, 120, 14], fill=AMBER)
        d.rectangle([0, 0, 14, 120], fill=AMBER)
        d.rectangle([W - 120, H - 14, W, H], fill=AMBER)
        d.rectangle([W - 14, H - 120, W, H], fill=AMBER)


def progress_bar(d, frac):
    d.rectangle([0, 0, W, 12], fill=BAR)
    d.rectangle([0, 0, int(W * max(0.0, min(1.0, frac))), 12], fill=AMBER)


def top_brand(d):
    d.text((MARGIN, 44), BRAND["wordmark"], font=font(True, 34), fill=WHITE)
    lbl = BRAND["tagline"]
    d.text((W - MARGIN - text_w(d, lbl, font(False, 26)), 52),
           lbl, font=font(False, 26), fill=LIGHTST)


# ----------------------------------------------------------------------------
# Karaoke
# ----------------------------------------------------------------------------
def lay_out_words(d, words, fnt, max_w):
    space = text_w(d, " ", fnt)
    lines, cur, cur_w = [], [], 0.0
    for gi, w in enumerate(words):
        ww = text_w(d, w, fnt)
        add = ww if not cur else ww + space
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur, cur_w = [(gi, w)], ww
        else:
            cur.append((gi, w))
            cur_w += add
    if cur:
        lines.append(cur)
    return lines


def draw_karaoke_line(d, line, fnt, cy, current_gi):
    space = text_w(d, " ", fnt)
    widths = [text_w(d, w, fnt) for _, w in line]
    total = sum(widths) + space * (len(line) - 1)
    x = W / 2 - total / 2
    asc, desc = fnt.getmetrics()
    for (gi, w), ww in zip(line, widths):
        if gi == current_gi:
            d.rounded_rectangle([x - 14, cy - 6, x + ww + 14, cy + asc + desc + 6],
                                radius=16, fill=AMBER)
            d.text((x, cy), w, font=fnt, fill=STEEL)
        elif gi < current_gi:
            d.text((x, cy), w, font=fnt, fill=WHITE)
        else:
            d.text((x, cy), w, font=fnt, fill=DIM)
        x += ww + space


def karaoke_band(d, lines, line_index, current_gi, cy=720):
    kf = font(True, 86)
    asc, desc = kf.getmetrics()
    lh = int((asc + desc) * 1.2)
    draw_karaoke_line(d, lines[line_index], kf, cy, current_gi)
    if line_index + 1 < len(lines):
        nline = lines[line_index + 1]
        words = " ".join(w for _, w in nline)
        center_text(d, words, font(True, 50), cy + lh + 36, DIM)


# ----------------------------------------------------------------------------
# Scene chrome
# ----------------------------------------------------------------------------
def scene_base(variant, frac):
    img = vertical_gradient(STEEL, DEEPSTEEL)
    d = ImageDraw.Draw(img)
    draw_motif(d, variant)
    progress_bar(d, frac)
    top_brand(d)
    return img, d


def hook_chrome(d, style_label, variant):
    outline_pill_center(d, style_label, 200, 32, AMBER)
    center_text(d, BRAND["hook_l1"], font(False, 40), 380, LIGHTST)
    center_text(d, BRAND["hook_l2"], font(True, 56), 440, WHITE)


def fit_font(d, text, bold, start, min_size, max_w):
    fs = start
    while fs > min_size and text_w(d, text, font(bold, fs)) > max_w:
        fs -= 2
    return font(bold, fs)


def event_chrome(d, ev, index, total, variant):
    # top: the type chip (THINKER / CONCEPT / PYQ / 14 -> 19), else EVENT i OF n
    chip = ev.get("chip") or (f"EVENT {index + 1} OF {total}" if total > 1 else "TODAY")
    pill_center(d, chip, 150, 30, AMBER, STEEL)
    nl = wrap(d, ev.get("event", ""), font(True, 46), CONTENT_W)
    y = 250
    for ln in nl[:2]:
        center_text(d, ln, font(True, 46), y, ICE)
        y += 56

    # bottom strip: the label (Paper / Decode / Dimension...) + concept + anchors
    by = 1300
    d.rectangle([0, by, W, by + 340], fill=STRIP)
    d.rectangle([0, by, W, by + 6], fill=AMBER)
    strip = ev.get("strip_label")
    if not strip:
        p = ev.get("paper")
        strip = (p + " CONCEPT") if p else (BRAND["concept_label"] + " CONCEPT")
    center_text(d, strip.upper(), font(True, 28), by + 26, AMBER)
    cyy = by + 64
    for ln in wrap(d, ev.get("concept", ""), font(True, 46), CONTENT_W)[:2]:
        center_text(d, ln, font(True, 46), cyy, WHITE)
        cyy += 54

    # up to two anchors, each tagged Indian / Western
    anchors = ev.get("thinkers") or ([{"name": ev.get("thinker", ""),
                                       "tradition": tradition(ev.get("thinker", ""))}]
                                     if ev.get("thinker") else [])
    if anchors:
        names = [f"{a['name']} ({a['tradition']})" if a.get("tradition") else a["name"]
                 for a in anchors[:2]]
        line = "ANCHORS   " + "   +   ".join(names)
        center_text(d, line, fit_font(d, line, False, 36, 22, CONTENT_W), cyy + 18, LIGHTST)


def payoff_chrome(d, variant):
    outline_pill_center(d, "THE WHOLE GAME", 200, 32, AMBER)
    center_text(d, BRAND["payoff_l1"], font(True, 52), 360, WHITE)
    center_text(d, BRAND["payoff_l2"], font(True, 46), 1500, AMBER)


def end_card(out_path, variant):
    img, d = scene_base(variant, 1.0)
    cx, y = W / 2, 430
    for ln in wrap(d, BRAND["end_title"], font(True, 72), CONTENT_W):
        center_text(d, ln, font(True, 72), y, WHITE)
        y += 90
    y += 20
    for line in BRAND["end_bullets"]:
        center_text(d, "•  " + line, font(False, 46), y, ICE)
        y += 74
    y += 36
    y = pill_center(d, "Join FREE on Telegram", y, 46, AMBER, STEEL) + 28
    center_text(d, CHANNEL_HANDLE, font(True, 56), y, WHITE)
    y += 104
    center_text(d, BRAND["end_sub"], font(False, 38), y, LIGHTST)
    center_text(d, "SUBSCRIBE TO UPSC DESK", font(True, 50), H - 200, AMBER)
    center_text(d, "A new Short every single day", font(False, 36), H - 132, LIGHTST)
    img.save(out_path, "PNG")


def make_cover(script, out_path):
    """A strong static thumbnail/cover (not a mid-karaoke frame)."""
    img, d = scene_base(script.get("variant", 0), 0.0)
    cx = W / 2
    outline_pill_center(d, "IS THIS CURRENT AFFAIRS?", 280, 34, AMBER)
    center_text(d, "NO.", font(True, 160), 380, WHITE)
    center_text(d, "IT'S SOCIOLOGY.", font(True, 76), 580, AMBER)
    y = 820
    for ev in script.get("events", [])[:2]:
        for ln in wrap(d, "•  " + ev.get("event", ""), font(True, 50), CONTENT_W)[:2]:
            center_text(d, ln, font(True, 50), y, ICE)
            y += 64
        y += 18
    center_text(d, "Decoded for UPSC Mains in 30 seconds", font(False, 40), H - 360, LIGHTST)
    center_text(d, CHANNEL_HANDLE, font(True, 50), H - 150, WHITE)
    img.save(out_path, "PNG")


def render_word_frame(scene, words_lines, line_index, current_gi, frac, out_path):
    img, d = scene_base(scene["variant"], frac)
    stype = scene["type"]
    if stype == "hook":
        hook_chrome(d, scene["style_label"], scene["variant"])
    elif stype == "event":
        event_chrome(d, scene["event"], scene["index"], scene["total"], scene["variant"])
    elif stype == "payoff":
        payoff_chrome(d, scene["variant"])
    karaoke_band(d, words_lines, line_index, current_gi, cy=760 if stype == "event" else 720)
    center_text(d, CHANNEL_HANDLE + "   ·   full answer below",
                font(True, 32), H - 70, LIGHTST)
    img.save(out_path, "PNG")


# ----------------------------------------------------------------------------
# Script -> narration segments -> per-word scene assignment
# ----------------------------------------------------------------------------
def assemble_segments(script):
    """Return ordered list of (scene_dict, text) covering hook, events, payoff, cta."""
    variant = script.get("variant", 0)
    style_label = script.get("style_label", "SAME EVENT. DIFFERENT EYES.")
    segs = []
    if script.get("hook"):
        segs.append(({"type": "hook", "variant": variant, "style_label": style_label},
                     script["hook"]))
    evs = script.get("events", [])
    for i, ev in enumerate(evs):
        segs.append(({"type": "event", "variant": variant, "event": ev,
                      "index": i, "total": len(evs)}, ev.get("line", "")))
    if script.get("payoff"):
        segs.append(({"type": "payoff", "variant": variant}, script["payoff"]))
    if script.get("cta"):
        # CTA words ride on the payoff scene so we don't karaoke over the end card
        segs.append(({"type": "payoff", "variant": variant}, script["cta"]))
    return segs


def narration_text(script):
    parts = [script.get("hook", "")]
    parts += [e.get("line", "") for e in script.get("events", [])]
    parts += [script.get("payoff", ""), script.get("cta", "")]
    return " ".join(p.strip() for p in parts if p.strip())


# ----------------------------------------------------------------------------
# Audio + timing
# ----------------------------------------------------------------------------
def normalize_tts(text):
    return re.sub(r'(\d)\s*-\s*(\d)', r'\1 to \2', text)


def ffprobe_dur(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path])
    return float(out.strip())


def atempo_chain(speed):
    speed = max(0.5, float(speed))
    parts = []
    while speed > 2.0:
        parts.append("atempo=2.0")
        speed /= 2.0
    parts.append(f"atempo={speed:.5f}")
    return ",".join(parts)


def speed_audio(src, dst, speed):
    subprocess.check_call([
        "ffmpeg", "-y", "-i", src, "-af", atempo_chain(speed) + ",apad=pad_dur=0.10",
        "-c:a", "aac", "-b:a", "192k", dst
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def words_from_timestamps(chars, char_starts, speed):
    words, starts, cur, cur_start = [], [], "", None
    for ch, st in zip(chars, char_starts):
        if ch == " ":
            if cur:
                words.append(cur)
                starts.append(cur_start / speed)
                cur, cur_start = "", None
        else:
            if cur_start is None:
                cur_start = st
            cur += ch
    if cur:
        words.append(cur)
        starts.append(cur_start / speed)
    return words, starts


def synth_with_timestamps(text, out_mp3, speed):
    import urllib.request
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        return None
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps"
    payload = {"text": normalize_tts(text), "model_id": MODEL_ID,
               "voice_settings": VOICE_SETTINGS}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"xi-api-key": api_key,
                                          "Content-Type": "application/json"})
    try:
        import urllib.error
        with urllib.request.urlopen(req, timeout=120) as r:
            obj = json.loads(r.read().decode())
    except Exception as e:
        print("  with-timestamps failed:", str(e))
        return None
    with open(out_mp3, "wb") as f:
        f.write(base64.b64decode(obj["audio_base64"]))
    align = obj.get("alignment") or obj.get("normalized_alignment") or {}
    out_m4a = out_mp3[:-4] + ".m4a"
    speed_audio(out_mp3, out_m4a, speed)
    words, starts = words_from_timestamps(align.get("characters", []),
                                          align.get("character_start_times_seconds", []),
                                          speed)
    return out_m4a, words, starts


def silent_track(seconds, out_path):
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "lavfi", "-t", f"{seconds:.3f}",
        "-i", "anullsrc=r=44100:cl=stereo", "-c:a", "aac", "-b:a", "128k", out_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_audio_track(narration, hook_sec, end_sec, out_path):
    """narration with optional leading/trailing silence. Zero-length pads are
    skipped (a 0-duration anullsrc stalls ffmpeg's concat)."""
    inputs, labels, idx = [], [], 0
    if hook_sec and hook_sec > 0.01:
        inputs += ["-f", "lavfi", "-t", f"{hook_sec:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
        labels.append(f"[{idx}:a]"); idx += 1
    inputs += ["-i", narration]; labels.append(f"[{idx}:a]"); idx += 1
    if end_sec and end_sec > 0.01:
        inputs += ["-f", "lavfi", "-t", f"{end_sec:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
        labels.append(f"[{idx}:a]"); idx += 1
    fc = "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[a]"
    subprocess.check_call([
        "ffmpeg", "-y", *inputs, "-filter_complex", fc,
        "-map", "[a]", "-c:a", "aac", "-b:a", "192k", out_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


MUSIC_EXTS = (".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac")


def pick_music(music_arg, seed):
    """Resolve the background bed: an explicit file, or a rotating pick from a
    folder (default pipeline assets/music). Returns a path or None."""
    if music_arg and os.path.isfile(music_arg):
        return music_arg
    folders = [music_arg] if (music_arg and os.path.isdir(music_arg)) else []
    folders += ["assets/music", os.path.join("..", "..", "pipeline_repo", "assets", "music")]
    for folder in folders:
        if folder and os.path.isdir(folder):
            tracks = sorted(f for f in os.listdir(folder)
                            if f.lower().endswith(MUSIC_EXTS))
            if tracks:
                return os.path.join(folder, tracks[seed % len(tracks)])
    return None


def apply_music(base_audio, music_file, out_path, music_vol):
    """Overlay a looped, low, faded music bed under the base track. Output length
    follows the base track (voice or silence), so caption timing is unchanged."""
    dur = ffprobe_dur(base_audio)
    fade = max(0.0, dur - 1.2)
    subprocess.check_call([
        "ffmpeg", "-y", "-i", base_audio, "-stream_loop", "-1", "-i", music_file,
        "-filter_complex",
        f"[1:a]volume={music_vol},afade=t=in:st=0:d=1.0,"
        f"afade=t=out:st={fade:.2f}:d=1.2[m];"
        f"[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
        "-map", "[a]", "-c:a", "aac", "-b:a", "192k", out_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def assemble(frames_durations, audio_track, out_path, workdir):
    listf = os.path.join(workdir, "short_frames.txt")
    with open(listf, "w") as f:
        for img, dur in frames_durations:
            f.write(f"file '{os.path.abspath(img)}'\n")
            f.write(f"duration {dur:.4f}\n")
        f.write(f"file '{os.path.abspath(frames_durations[-1][0])}'\n")
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listf, "-i", audio_track,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-tune", "stillimage", "-r", "30", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-vf", "scale=1080:1920", "-shortest", out_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ----------------------------------------------------------------------------
# Extract the day's two events (event -> concept -> thinker -> lever) from slides
# ----------------------------------------------------------------------------
# Well-known Indian sociologists, so the Short can tag the thinker's tradition.
# Names not matched here are treated as Western. Keep lowercase.
INDIAN_THINKERS = {
    "ghurye", "srinivas", "m.n. srinivas", "mn srinivas", "dube", "s.c. dube",
    "beteille", "andre beteille", "andré béteille", "a.r. desai", "ar desai", "desai",
    "yogendra singh", "oommen", "t.k. oommen", "tk oommen", "veena das",
    "dipankar gupta", "irawati karve", "leela dube", "partha chatterjee",
    "ambedkar", "b.r. ambedkar", "gail omvedt", "radhakamal mukerjee",
    "d.p. mukerji", "dp mukerji", "a.k. saran", "ranajit guha", "nandu ram",
    "sharmila rege", "g.s. ghurye", "gs ghurye",
}


def tradition(name):
    low = (name or "").lower().strip()
    return "Indian" if any(k in low for k in INDIAN_THINKERS) else "Western"


def detect_paper(texts):
    """Read 'Paper 1'/'Paper 2' hints out of the event's slide text. Paper 1 =
    theory/thinkers/institutions/change; Paper 2 = Indian society (caste, tribe,
    village, kinship, religion in India, social movements)."""
    t = " ".join(texts).lower()
    p1 = "paper 1" in t or "paper one" in t or "paper-1" in t
    p2 = "paper 2" in t or "paper two" in t or "paper-2" in t
    if p1 and p2:
        return "Paper 1 + 2"
    if p2:
        return "Paper 2"
    if p1:
        return "Paper 1"
    return ""


def extract_events(slides, limit=2):
    events = []
    n = len(slides)
    for i, s in enumerate(slides):
        if s.get("type") != "topic_title":
            continue
        seg_text = list(s.get("bullets", [])) + [s.get("heading", "")]
        ev = {"event": s.get("heading", ""), "paper": "", "concept": "",
              "thinkers": [], "thinker": "", "thinker_tag": "", "line": ""}
        for j in range(i + 1, n):
            t = slides[j].get("type")
            if t == "topic_title":
                break
            seg_text += list(slides[j].get("bullets", [])) + [slides[j].get("heading", "")]
            if t == "concept" and not ev["concept"]:
                ev["concept"] = slides[j].get("heading", "")
            if t == "thinker":
                h = slides[j].get("heading", "")
                parts = re.split(r'\s[-–]\s', h, maxsplit=1)
                nm = parts[0].strip()
                tg = parts[1].strip() if len(parts) > 1 else ""
                ev["thinkers"].append({"name": nm, "tag": tg, "tradition": tradition(nm)})
        ev["paper"] = detect_paper(seg_text)
        if ev["thinkers"]:
            ev["thinker"] = ev["thinkers"][0]["name"]
            ev["thinker_tag"] = ev["thinkers"][0]["tag"]
        events.append(ev)
        if len(events) >= limit:
            break
    return events


# ----------------------------------------------------------------------------
# Script sources
# ----------------------------------------------------------------------------
def pick_style(issue_no, override):
    if override:
        for s in STYLES:
            if s["name"] == override:
                return s
    return STYLES[int(issue_no) % len(STYLES)]


def template_script(events, style):
    """Deterministic fallback when no LLM key is present (still style-flavoured)."""
    ev_lines = []
    for ev in events:
        anchors = ev.get("thinkers", [])
        if anchors:
            names = " and ".join(a["name"] for a in anchors[:2])
        else:
            names = ev.get("thinker", "the key thinker")
        paper = ev.get("paper") or "the syllabus"
        ev["line"] = (f"Take {ev['event']}. To everyone else it is a headline. "
                      f"To you it is {paper}: {ev['concept'].lower()}. Anchor it to {names}.")
        ev_lines.append(ev)
    return {
        "style": style["name"], "style_label": style["label"],
        "hook": "An event just happened. Your rivals saw the news. "
                "You are going to see the sociology underneath it.",
        "events": ev_lines,
        "payoff": "Stop seeing current affairs. Start seeing sociology, Paper 1 or "
                  "Paper 2. That is how a 14 becomes a 19.",
        "cta": "Full model answers, free on Telegram.",
    }


def generate_script(events, style, issue_no):
    """Write a fresh ~110-word Short script in the day's STYLE via the Anthropic API."""
    import urllib.request
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    def ev_line(e):
        thk = "; ".join(f"{t['name']} ({t['tradition']})" for t in e.get("thinkers", [])) \
            or e.get("thinker", "")
        paper = e.get("paper") or "decide Paper 1 or Paper 2"
        return (f"- Event: {e['event']} | Likely paper: {paper} | "
                f"Concept: {e['concept']} | Thinkers available: {thk}")
    ev_brief = "\n".join(ev_line(e) for e in events)
    sys_prompt = (
        "You write 30-40 second YouTube Short scripts for an anonymous, serious UPSC "
        "Sociology Optional channel. House voice: plain, flowing, no hype, no emojis, "
        "NO em dashes, no exclamation marks. The ONE intent, every time: an event is not "
        "merely current affairs, it is Sociology. Decide whether each event belongs to "
        "PAPER 1 (theory, thinkers, social institutions, social change) or PAPER 2 "
        "(Indian society: caste, tribe, village, kinship, religion in India, social "
        "movements, modernisation of Indian tradition) - it can be both. Connect the "
        "event to the right paper, the right concept, and the right thinkers. Where the "
        "content allows, pair an INDIAN thinker with a WESTERN thinker and name both "
        "traditions; never force Paper 1. That is how a 14-mark answer becomes a 19. "
        "Vary tone day to day. Return STRICT JSON only.")
    user_prompt = (
        f"Style for today: {style['voice']}.\n"
        f"Use BOTH of today's events. For each: name the event, say which paper it maps "
        f"to, reframe it as the syllabus concept, and name the thinker anchors (an Indian "
        f"and a Western one where appropriate).\n\nEVENTS:\n{ev_brief}\n\n"
        'Keep it TIGHT - the whole Short must run about 35 seconds spoken, roughly 80 '
        'words total across all fields. '
        'Return JSON: {"hook": str (<=18 words, in today\'s style, ends by promising the '
        'aspirant will now see the sociology in the news), "events": [{"event": str, '
        '"paper": "Paper 1"|"Paper 2"|"Paper 1 + 2", "concept": str, "thinkers": '
        '[{"name": str, "tradition": "Indian"|"Western", "tag": str}], "thinker": str '
        '(primary name), "thinker_tag": str, "line": str (<=28 words, spoken, names the '
        'paper and at least one thinker)}], "payoff": str (<=22 words: every event is a '
        'syllabus theme - Paper 1 or Paper 2 - and that is how a 14 becomes a 19), '
        '"cta": str (<=9 words, point to Telegram)}')
    body = {"model": os.environ.get("SHORT_SCRIPT_MODEL", "claude-sonnet-4-6"),
            "max_tokens": 900, "system": sys_prompt,
            "messages": [{"role": "user", "content": user_prompt}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"x-api-key": api_key,
                                          "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            obj = json.loads(r.read().decode())
        text = "".join(b.get("text", "") for b in obj.get("content", []))
        m = re.search(r"\{.*\}", text, re.S)
        script = json.loads(m.group(0))
    except Exception as e:
        print("  script generation failed:", str(e))
        return None
    script["style"] = style["name"]
    script["style_label"] = style["label"]
    return script


# ----------------------------------------------------------------------------
# Meta
# ----------------------------------------------------------------------------
def build_meta(data, script, out_path):
    evs = script.get("events", [])
    names = " + ".join(e.get("event", "").split(":")[0] for e in evs)[:60]
    title = f"{BRAND['meta_title']} {names} | UPSC in 30s #Shorts"[:100]
    tg = "https://t.me/" + CHANNEL_HANDLE.lstrip("@")
    tags = list(data.get("tags", []))
    for e in evs:
        for v in (e.get("thinker", ""), e.get("concept", "")):
            if v and v not in tags:
                tags.append(v)
    for t in BRAND["tags_seed"]:
        if t not in tags:
            tags.append(t)
    desc = [BRAND["meta_lead"], ""]
    for e in evs:
        paper = e.get("paper", "")
        anchors = ", ".join(t.get("name", "") for t in e.get("thinkers", [])) or e.get("thinker", "")
        tag = f" [{paper}]" if paper else ""
        desc.append(f"- {e.get('event','')}{tag}: {e.get('concept','')} ({anchors})")
    desc += ["", BRAND["meta_offer"],
             f"Telegram: {tg}  ({CHANNEL_HANDLE})",
             f"Subscribe: {SUBSCRIBE}", "", BRAND["hashtags"]]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join([title, ""] + desc + ["", "Tags: " + ", ".join(tags)]))


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def find_build_dir(cli_dir, issue):
    # An explicit --build-dir is authoritative (the orchestrator gives each slot
    # its own dir). Only auto-discover when none was passed.
    if cli_dir:
        return cli_dir
    for base in ["build", os.path.join("..", "video_pipeline", "build")]:
        if os.path.isdir(os.path.join(base, f"issue_{issue}")):
            return base
    return "build"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("--script-file", help="hand-authored short_script JSON (for previews)")
    ap.add_argument("--style", help="force a style persona (else rotates by issue)")
    ap.add_argument("--variant", type=int, help="force a visual variant 0-2 (else issue%%3)")
    ap.add_argument("--build-dir", default=None)
    ap.add_argument("--max-sec", type=float, default=42.0)
    ap.add_argument("--pace", type=float, default=1.35)
    ap.add_argument("--synced", action="store_true", help="regenerate audio with word timestamps")
    ap.add_argument("--no-llm", action="store_true", help="skip API generation, use template")
    ap.add_argument("--silent", action="store_true",
                    help="no TTS: a music-bed Short (even-split captions). For the "
                         "6 non-voiced daily slots.")
    ap.add_argument("--music", default=None,
                    help="background music file or folder (default: assets/music, rotated)")
    ap.add_argument("--music-on-voice", action="store_true",
                    help="also lay a faint music bed under voiced Shorts")
    ap.add_argument("--slot", type=int, default=0,
                    help="slot index (rotates the music/style seed across the day)")
    ap.add_argument("--desk", default="sociology", choices=list(DESK_THEMES),
                    help="theme + brand (sociology = Steel/Amber, essay = Claret/Gold)")
    args = ap.parse_args()

    set_desk(args.desk)
    data = json.load(open(args.json_path))
    issue = f"{int(data['issue_no']):03d}"
    slides = data["slides"]
    style = pick_style(data["issue_no"], args.style)
    variant = args.variant if args.variant is not None else int(data["issue_no"]) % 3

    # ---- resolve the script ----
    script = None
    src = ""
    if isinstance(data.get("short_script"), dict):
        script, src = data["short_script"], "data.short_script"
    elif args.script_file and os.path.exists(args.script_file):
        script, src = json.load(open(args.script_file)), f"file:{args.script_file}"
    else:
        events = extract_events(slides, 2)
        if not args.no_llm:
            script = generate_script(events, style, data["issue_no"])
            src = "LLM" if script else ""
        if not script:
            script, src = template_script(events, style), "template"
    script.setdefault("style", style["name"])
    script.setdefault("style_label", style["label"])
    script["variant"] = variant
    print(f"Issue {issue}: style={script['style']} variant={variant} script_src={src}")
    for e in script.get("events", []):
        print(f"  event: {e.get('event','')!r} -> {e.get('concept','')!r} / {e.get('thinker','')!r}")

    build_dir = find_build_dir(args.build_dir, issue)
    out_base = os.path.join(build_dir, f"issue_{issue}", "short")
    fdir = os.path.join(out_base, "frames")
    os.makedirs(fdir, exist_ok=True)
    json.dump(script, open(os.path.join(out_base, "short_script.json"), "w"),
              ensure_ascii=False, indent=2)

    HOOK_SEC, END_SEC = 0.0, 3.0   # hook is now spoken (karaoke), not a silent card
    full_nar = narration_text(script)

    # ---- audio + word timeline ----
    words, starts, body_audio, silent = None, None, None, False

    def make_silent_body(reason):
        wlist = re.sub(r'\s+', ' ', full_nar).split()
        bd = max(8.0, len(wlist) / 2.6)   # ~2.6 words/sec reading pace
        path = os.path.join(out_base, "silent_body.m4a")
        silent_track(bd, path)
        per = bd / max(1, len(wlist))
        print(f"  audio: {reason} (~{bd:.1f}s, even-split captions).")
        return path, wlist, [i * per for i in range(len(wlist))]

    if args.silent:
        # deliberate music-bed slot: no TTS spend at all
        body_audio, words, starts = make_silent_body("SILENT music-bed slot")
        silent = True
    elif args.synced:
        res = synth_with_timestamps(full_nar, os.path.join(out_base, "synced.mp3"), args.pace)
        if res:
            body_audio, words, starts = res
            print("  audio: SYNCED regen with word timestamps (same voice).")
        else:
            # In production we must NOT publish a silent voiced-slot Short. Skip cleanly.
            print("  --synced requested but voice synth unavailable. "
                  "Skipping Short (non-blocking) so no silent video is uploaded.")
            return 0
    if body_audio is None:
        body_audio, words, starts = make_silent_body("SILENT preview (no key)")
        silent = True

    body_dur = ffprobe_dur(body_audio)
    total = HOOK_SEC + body_dur + END_SEC

    # ---- map each narration word to its scene ----
    segs = assemble_segments(script)
    scene_of_word = []
    for scene, text in segs:
        for _ in re.sub(r'\s+', ' ', text.strip()).split():
            scene_of_word.append(scene)
    # guard against off-by-one between narration_text and segment join
    while len(scene_of_word) < len(words):
        scene_of_word.append(segs[-1][0])
    scene_of_word = scene_of_word[:len(words)]

    # ---- karaoke layout (per scene, so lines reset between scenes) ----
    tmp = ImageDraw.Draw(Image.new("RGB", (W, H)))
    # build per-scene word groupings to keep lines tidy
    frames = []
    # precompute lines over the WHOLE word list for index continuity
    lines = lay_out_words(tmp, words, font(True, 86), CONTENT_W)
    gi_to_line = {gi: li for li, line in enumerate(lines) for gi, _ in line}

    for i in range(len(words)):
        nxt = starts[i + 1] if i + 1 < len(words) else body_dur
        dur = max(0.16, nxt - starts[i])
        frac = starts[i] / max(0.1, body_dur)
        png = os.path.join(fdir, f"f_{i:03d}.png")
        render_word_frame(scene_of_word[i], lines, gi_to_line[i], i, frac, png)
        frames.append((png, dur))

    end_png = os.path.join(fdir, "end.png")
    end_card(end_png, variant)
    frames.append((end_png, END_SEC))

    # static cover for the YouTube thumbnail
    cover_png = os.path.join(out_base, "cover.png")
    make_cover(script, cover_png)
    print(f"  rendered {len(words)} karaoke frames + end card + cover; total ~{total:.1f}s")

    # ---- audio track + assemble ----
    audio_track = os.path.join(out_base, "short_audio.m4a")
    build_audio_track(body_audio, HOOK_SEC, END_SEC, audio_track)

    # background music: full bed for silent slots, faint bed under voice if asked
    music_tag = ""
    if silent or args.music_on_voice:
        track = pick_music(args.music, int(data["issue_no"]) * 10 + args.slot)
        if track:
            vol = 0.30 if silent else 0.06
            mixed = os.path.join(out_base, "short_audio_mus.m4a")
            apply_music(audio_track, track, mixed, vol)
            audio_track = mixed
            music_tag = f"  + music({os.path.basename(track)})"
        elif silent:
            music_tag = "  (NO music track found in assets/music - add tracks)"

    out_mp4 = os.path.join(out_base, f"short_issue_{issue}.mp4")
    assemble(frames, audio_track, out_mp4, out_base)
    kind = "SILENT+music" if silent else "VOICED"
    print(f"\nShort: {out_mp4}  ({total:.1f}s, 1080x1920)  [{kind}]{music_tag}")

    build_meta(data, script, os.path.join(out_base, "short_meta.txt"))
    print(f"Short metadata: {os.path.join(out_base, 'short_meta.txt')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
