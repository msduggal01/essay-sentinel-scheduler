#!/usr/bin/env python3
"""
The Essay Desk - writing-masterclass video renderer.

Reads a video_script_issue_NNN.json (produced by the Essay Sentinel agent),
generates an ElevenLabs voiceover per slide, renders branded slide images with
Pillow, and assembles a final narrated MP4 with ffmpeg.

USAGE
  export ELEVENLABS_API_KEY="your_key_here"
  python3 render_video.py video_script_issue_028.json

OPTIONS
  --slides-only      Only render the slide PNGs (no audio, no video). Fast preview.
  --voice VOICE_ID   Override the ElevenLabs voice id.
  --model MODEL_ID   Override the ElevenLabs model (default eleven_turbo_v2_5).

OUTPUT (under build/issue_NNN/)
  slides/   the slide images
  audio/    the per-slide mp3 narration
  clips/    the per-slide video clips
  video_issue_NNN.mp4   the final video
  youtube_meta.txt      title (and alternates), description with chapter timestamps, tags (yt_meta.py)
  captions.srt          English captions from the voice's word timings
  timings.json, alignment.json   what --meta-only rebuilds the two above from

  --meta-only        Rebuild youtube_meta.txt and captions.srt from a rendered issue, no voice.
"""

import os
import sys
import re
import json
import subprocess

from PIL import Image, ImageDraw, ImageFont

# ----------------------------------------------------------------------------
# Brand palette - Essay Desk literary palette (matches the PDF FROZEN DESIGN).
# Variable names are kept from the original renderer so the draw logic is
# untouched; only the RGB values are repointed to the claret/parchment scheme.
#   STEEL   -> Claret (primary)      ICE    -> Parchment (light bg)
#   MIDSTEEL-> Muted Rose (sub)      NEAR   -> Ink (body)
#   LIGHTST -> Light Border          AMBER  -> Gold (craft accent)
#   GREEN   -> Muted Teal (recap)
# ----------------------------------------------------------------------------
STEEL   = (122, 45, 58)    # #7A2D3A  Claret (primary)
ICE     = (246, 239, 227)  # #F6EFE3  Parchment
MIDSTEEL= (154, 107, 116)  # #9A6B74  Muted Rose
NEAR    = (34, 31, 38)     # #221F26  Ink
LIGHTST = (226, 211, 195)  # #E2D3C3  Light Border
WHITE   = (255, 255, 255)
AMBER   = (184, 134, 11)   # #B8860B  Gold (craft accent)
GREEN   = (42, 111, 107)   # #2A6F6B  Muted Teal (recap)

W, H = 1920, 1080
MARGIN = 130
CONTENT_W = W - 2 * MARGIN

# ----------------------------------------------------------------------------
# Fonts
# ----------------------------------------------------------------------------
REG_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",          # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Linux (Arial-compatible)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",                  # Linux fallback
]
BOLD_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",     # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",     # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",             # Linux fallback
]

def _first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None

REG_PATH = _first_existing(REG_CANDIDATES)
BOLD_PATH = _first_existing(BOLD_CANDIDATES)

def font(bold, size):
    path = BOLD_PATH if bold else REG_PATH
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

# ----------------------------------------------------------------------------
# Text helpers
# ----------------------------------------------------------------------------
def text_w(draw, s, fnt):
    return draw.textlength(s, font=fnt)

def wrap(draw, text, fnt, max_w):
    words = text.split()
    lines, cur = [], ""
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

def draw_lines(draw, lines, x, y, fnt, fill, line_gap=1.35):
    asc, desc = fnt.getmetrics()
    lh = int((asc + desc) * line_gap)
    for ln in lines:
        draw.text((x, y), ln, font=fnt, fill=fill)
        y += lh
    return y

def pill(draw, x, y, label, bg, fg=WHITE, fsize=30):
    fnt = font(True, fsize)
    tw = text_w(draw, label, fnt)
    padx, pady = 26, 14
    asc, desc = fnt.getmetrics()
    th = asc + desc
    draw.rounded_rectangle([x, y, x + tw + 2 * padx, y + th + 2 * pady],
                           radius=(th + 2 * pady) // 2, fill=bg)
    draw.text((x + padx, y + pady), label, font=fnt, fill=fg)
    return y + th + 2 * pady

# ----------------------------------------------------------------------------
# Slide rendering
# ----------------------------------------------------------------------------
# Essay-channel semantics: the Essay Sentinel reuses the fixed type tokens but
# they mean (per Step 10): concept = DECODE/DIMENSIONS, thinker = ANCHOR,
# answer_bridge = CRAFT (intro/conclusion), question = MODEL LINE.
TYPE_BADGE = {
    "topic_title": ("ESSAY TOPIC", STEEL),
    "concept":     ("DECODE & DIMENSIONS", MIDSTEEL),
    "thinker":     ("ANCHOR", STEEL),
    "answer_bridge": ("CRAFT THE ESSAY", AMBER),
    "question":    ("MODEL LINE", MIDSTEEL),
    "recap":       ("RECAP", GREEN),
}
DARK_TYPES = {"intro", "outro", "topic_title"}

def render_slide(slide, ctx, out_path, reveal=None):
    dark = slide["type"] in DARK_TYPES
    bg = STEEL if dark else WHITE
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)

    heading = slide.get("heading", "")
    bullets = [b for b in slide.get("bullets", []) if b]
    # reveal = how many bullets to show (for progressive build-up); None = all
    vis = bullets if reveal is None else bullets[:reveal]

    if dark:
        # decorative dot grid top-right (like the PDF cover)
        for r in range(5):
            for c in range(5):
                cx = W - 360 + c * 60
                cy = 70 + r * 46
                d.ellipse([cx, cy, cx + 14, cy + 14], fill=(156, 91, 102))
        # brand line
        d.text((MARGIN, 80), "THE ESSAY DESK", font=font(True, 34), fill=WHITE)
        d.text((MARGIN, 128), "UPSC Essay, decoded.",
               font=font(False, 28), fill=ICE)

        if slide["type"] == "topic_title":
            pill(d, MARGIN, 240, "TOPIC", AMBER)
            hl = wrap(d, heading, font(True, 84), CONTENT_W)
            y = draw_lines(d, hl, MARGIN, 330, font(True, 84), WHITE)
            y += 30
            for b in vis:
                d.ellipse([MARGIN, y + 22, MARGIN + 16, y + 38], fill=AMBER)
                bl = wrap(d, b, font(False, 46), CONTENT_W - 60)
                draw_lines(d, bl, MARGIN + 50, y, font(False, 46), ICE)
                y += int(font(False, 46).getmetrics()[0] * 1.35) * max(1, len(bl)) + 18
        else:
            # intro / outro: centered hero
            hl = wrap(d, heading, font(True, 92), CONTENT_W)
            total_h = len(hl) * int(font(True, 92).getmetrics()[0] * 1.3)
            y = (H - total_h) // 2 - 80
            for ln in hl:
                tw = text_w(d, ln, font(True, 92))
                d.text(((W - tw) // 2, y), ln, font=font(True, 92), fill=WHITE)
                y += int(font(True, 92).getmetrics()[0] * 1.3)
            y += 40
            for b in bullets:
                line = "•   " + b
                tw = text_w(d, line, font(False, 44))
                d.text(((W - tw) // 2, y), line, font=font(False, 44), fill=ICE)
                y += 70
    else:
        # light slide: top brand bar
        d.rectangle([0, 0, W, 96], fill=STEEL)
        # the video's own counter: the agent numbers every video with the EPISODE counter
        # and says "episode seventy one" in the intro, so the header says Episode too
        d.text((MARGIN, 30), f"The Essay Desk   |   Episode {ctx['episode']}   |   {ctx['date']}",
               font=font(False, 30), fill=WHITE)

        badge = TYPE_BADGE.get(slide["type"])
        top = 170
        if badge:
            top = pill(d, MARGIN, 150, badge[0], badge[1]) + 30

        # special left accent bar for the exam-bridge slide
        accent = AMBER if slide["type"] == "answer_bridge" else None

        hl = wrap(d, heading, font(True, 66), CONTENT_W)
        y = draw_lines(d, hl, MARGIN, top, font(True, 66), STEEL)
        # underline rule
        y += 6
        d.rectangle([MARGIN, y, W - MARGIN, y + 4], fill=LIGHTST)
        y += 50

        if accent:
            bar_top = y - 10
        for b in vis:
            d.ellipse([MARGIN, y + 20, MARGIN + 18, y + 38], fill=badge[1] if badge else STEEL)
            bl = wrap(d, b, font(False, 50), CONTENT_W - 70)
            draw_lines(d, bl, MARGIN + 56, y, font(False, 50), NEAR)
            y += int(font(False, 50).getmetrics()[0] * 1.35) * max(1, len(bl)) + 26

        if accent:
            d.rectangle([MARGIN - 40, bar_top, MARGIN - 28, y - 10], fill=AMBER)

        # footer
        d.text((MARGIN, H - 70), "Decode the topic. Build the dimensions. Master the craft.",
               font=font(False, 26), fill=MIDSTEEL)

    img.save(out_path, "PNG")

# ----------------------------------------------------------------------------
# Text normalization for TTS
# ----------------------------------------------------------------------------
def normalize_tts(text):
    # numeric ranges like 40-60 -> "40 to 60" (keeps word hyphens intact)
    text = re.sub(r'(\d)\s*-\s*(\d)', r'\1 to \2', text)
    # the desk's address is spoken as an address: the agent writes "team dot upscdesk dot
    # com" or "team@upscdesk.com", and both came out as "team dot upscdesk dot com"
    text = re.sub(r"\b([a-z]+)@upscdesk\.com\b", r"\1 at upscdesk dot com", text, flags=re.I)
    text = re.sub(r"\bteam\s+dot\s+upscdesk\s+dot\s+com\b", "team at upscdesk dot com", text, flags=re.I)
    return text


# The last slide always ends by pointing to the description, on screen and in the voice. It is
# added here, after the humaniser and just before the voice, so no rewrite can drop it.
LINKS_SPOKEN = ("The links to subscribe and to join our Telegram channel are in the description "
                "below; tap them to join.")
LINKS_ON_SCREEN = "Subscribe and Telegram links: in the description below"


def add_links_line(slides):
    """the closing line on the outro (or, failing that, the last slide); safe to run twice"""
    last = next((s for s in reversed(slides) if s.get("type") == "outro"), slides[-1] if slides else None)
    if not last:
        return
    if LINKS_SPOKEN not in last.get("narration", ""):
        last["narration"] = (last.get("narration", "").rstrip() + " " + LINKS_SPOKEN).strip()
    if LINKS_ON_SCREEN not in (last.get("bullets") or []):
        last["bullets"] = [b for b in (last.get("bullets") or []) if b] + [LINKS_ON_SCREEN]

# ----------------------------------------------------------------------------
# ElevenLabs TTS
# ----------------------------------------------------------------------------
def tts(text, out_path, api_key, voice_id, model_id, previous_text=None, next_text=None):
    import urllib.request, urllib.error
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = {
        "text": normalize_tts(text),
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.55,        # higher = steadier; stops the pitch "reset" at each slide
            "similarity_boost": 0.90, # hold the timbre consistent across clips
            "style": 0.18,            # low style = minimal random inflection swings between clips
            "use_speaker_boost": True
        }
    }
    # NOTE: eleven_v3 does NOT support previous_text/next_text request stitching
    # (API rejects it). Steadiness across slides therefore comes from the higher
    # stability + lower style in voice_settings above, not from neighbour context.
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            pass
        print(f"\nElevenLabs HTTP {e.code} error. Response body:\n{detail}\n")
        raise
    with open(out_path, "wb") as f:
        f.write(data)

def tts_full(text, api_key, voice_id, model_id):
    """Synthesise the ENTIRE episode narration in ONE call via the with-timestamps
    endpoint, so the whole video is a single continuous take (no per-slide pitch
    reset). Returns (mp3_bytes, alignment) where alignment carries per-character
    end times, used to work out where each slide ends inside the one audio file."""
    import urllib.request, urllib.error, base64
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.55, "similarity_boost": 0.90,
            "style": 0.18, "use_speaker_boost": True
        }
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "xi-api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"
    })
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = ""
        try: detail = e.read().decode("utf-8")
        except Exception: pass
        print(f"\nElevenLabs with-timestamps HTTP {e.code}:\n{detail}\n")
        raise
    audio = base64.b64decode(d["audio_base64"])
    alignment = d.get("alignment") or d.get("normalized_alignment") or {}
    return audio, alignment

# ----------------------------------------------------------------------------
# ffmpeg helpers
# ----------------------------------------------------------------------------
def duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path
    ])
    return float(out.strip())

def prep_audio(mp3, out_aud, speed=1.0, tail=0.12, semitones=0.0,
               bass_gain=0.0, warmth_gain=0.0, presence_cut=0.0, treble_cut=0.0,
               lowpass_hz=0, sr=44100):
    """Shape the narration into a warm, deep, All India Radio style delivery and remove
    the 'sharp in the ears' edge:
      - pitch DOWN (semitones<0) for weight,
      - low-shelf bass + a low-mid bell for chest and body,
      - a presence-band cut (~3.5kHz) and high-shelf roll-off (~6kHz) to kill harshness,
      - a gentle top-end lowpass to remove sizzle,
    while holding the intended playback speed (pitch preserved), then a tiny tail gap."""
    P = 2 ** (semitones / 12.0)               # <1 lowers pitch
    chain = [f"asetrate={int(sr * P)}", f"aresample={sr}"]
    tempo = (speed / P) if P else speed       # restore tempo lost to the pitch shift, then apply playback speed
    t = tempo
    while t > 2.0 - 1e-9: chain.append("atempo=2.0"); t /= 2.0
    while t < 0.5 + 1e-9: chain.append("atempo=0.5"); t /= 0.5
    if abs(t - 1.0) > 1e-3: chain.append(f"atempo={t:.5f}")
    if bass_gain:    chain.append(f"bass=g={bass_gain}:f=130")            # low warmth
    if warmth_gain:  chain.append(f"equalizer=f=240:t=q:w=1.0:g={warmth_gain}")  # low-mid body
    if presence_cut: chain.append(f"equalizer=f=3500:t=q:w=2.0:g={presence_cut}")  # tame harshness
    if treble_cut:   chain.append(f"treble=g={treble_cut}:f=6000")        # roll off sharp highs
    if lowpass_hz:   chain.append(f"lowpass=f={lowpass_hz}")              # remove sizzle
    chain.append(f"apad=pad_dur={tail}")
    subprocess.check_call([
        "ffmpeg", "-y", "-i", mp3, "-af", ",".join(chain), "-c:a", "aac", "-b:a", "192k", out_aud
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def concat_audio(auds, out_path, workdir):
    listfile = os.path.join(workdir, "audio_concat.txt")
    with open(listfile, "w") as f:
        for a in auds:
            f.write(f"file '{os.path.abspath(a)}'\n")
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
        "-c", "copy", out_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def build_final(images_durations, audio_master, out_path, workdir):
    """Single-pass assembly. Each slide image is held for exactly its own
    narration length, then muxed ONCE with the concatenated narration. Because
    image boundaries and audio segments use the same per-slide durations and it
    is one continuous mux, every slide switches the instant its speech ends -
    with no cumulative audio/video drift."""
    listf = os.path.join(workdir, "image_concat.txt")
    with open(listf, "w") as f:
        for img, dur in images_durations:
            f.write(f"file '{os.path.abspath(img)}'\n")
            f.write(f"duration {dur:.4f}\n")
        f.write(f"file '{os.path.abspath(images_durations[-1][0])}'\n")
    adur = duration(audio_master)   # cap to the exact narration length: the concat
    # demuxer holds the trailing repeated frame, which would otherwise leave a long
    # silent last slide (video stream running past the audio).
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listf, "-i", audio_master,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-tune", "stillimage", "-r", "30", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-vf", "scale=1920:1080",
        "-t", f"{adur:.3f}", "-shortest", out_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def fmt_ts(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def _grad(W, H, stops):
    """Smooth diagonal gradient (top-left -> bottom-right) rendered small then upscaled."""
    sw, sh = 64, 36
    g = Image.new("RGB", (sw, sh)); px = g.load()
    for y in range(sh):
        for x in range(sw):
            t = (x / (sw - 1) + y / (sh - 1)) / 2
            for i in range(len(stops) - 1):
                p0, c0 = stops[i]; p1, c1 = stops[i + 1]
                if p0 <= t <= p1:
                    fr = (t - p0) / (p1 - p0) if p1 > p0 else 0
                    px[x, y] = tuple(int(c0[k] + (c1[k] - c0[k]) * fr) for k in range(3)); break
            else:
                px[x, y] = stops[-1][1]
    return g.resize((W, H), Image.BILINEAR)

def make_thumbnail(topic, theme, section, archetype, tagline, out):
    """1280x720 branded Essay thumbnail (locked design): claret gradient, gold left bar,
    signature dot grid, THE ESSAY PAPER over UPSC CSE, topic hero, theme + section pill,
    approach line, a gold separator and a per-episode tagline."""
    W, H = 1280, 720
    GOLD = (184, 134, 11); DEEP = (46, 17, 22); WHITE = (255, 255, 255)
    SUB = (233, 217, 197); DOT = (156, 91, 102)
    img = _grad(W, H, [(0.0, (122, 45, 58)), (0.52, (94, 34, 44)), (1.0, (46, 17, 22))])
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 24, H], fill=GOLD)
    dd, gap = 12, 22; gw = 4 * dd + 3 * gap; x0 = W - 80 - gw; y0 = 68
    for r in range(4):
        for c in range(4):
            x = x0 + c * (dd + gap); y = y0 + r * (dd + gap)
            d.ellipse([x, y, x + dd, y + dd], fill=DOT)
    d.text((88, 50), "THE ESSAY PAPER", font=font(True, 44), fill=GOLD)
    d.text((90, 112), "UPSC CIVIL SERVICES EXAMINATION", font=font(False, 25), fill=SUB)
    d.rectangle([90, 162, 390, 166], fill=GOLD)
    size = 80
    while size > 46:
        tf = font(True, size); lines = wrap(d, topic, tf, W - 88 - 104)
        if len(lines) <= 2:
            break
        size -= 4
    hy = 200; lh = int(size * 1.06)
    for i, ln in enumerate(lines):
        d.text((88, hy + i * lh), ln, font=tf, fill=WHITE)
    my = hy + len(lines) * lh + 40          # generous gap so the theme never touches the hero
    thf = font(True, 46)
    d.text((88, my), theme, font=thf, fill=GOLD)
    if section:
        px_ = 88 + d.textlength(theme, font=thf) + 24
        pf = font(True, 26); ptxt = section.upper(); tw = d.textlength(ptxt, font=pf)
        d.rounded_rectangle([px_, my + 4, px_ + tw + 40, my + 52], radius=24, fill=GOLD)
        d.text((px_ + 20, my + 10), ptxt, font=pf, fill=DEEP)
    if archetype:
        d.text((90, my + 62), "Approach:  " + archetype, font=font(False, 30), fill=SUB)
    d.rectangle([88, H - 104, 548, H - 100], fill=GOLD)
    d.text((88, H - 72), tagline, font=font(True, 40), fill=GOLD)
    img.save(out); return out

def main():
    args = sys.argv[1:]
    slides_only = "--slides-only" in args
    args = [a for a in args if a != "--slides-only"]
    if "--meta-only" in args:
        args.remove("--meta-only")
        meta_only(args[0])
        return

    limit = None
    if "--limit" in args:
        i = args.index("--limit"); limit = int(args[i + 1]); del args[i:i + 2]

    speed = 1.10  # locked playback pace (1.0 = ElevenLabs native), slowed from 1.25 for a calmer delivery. Override with --speed
    if "--speed" in args:
        i = args.index("--speed"); speed = float(args[i + 1]); del args[i:i + 2]

    # Essay Desk LOCKED voice (distinct from Sociology's Mani). Override with
    # ESSAY_VOICE_ID env or --voice if ever needed.
    voice_id = os.environ.get("ESSAY_VOICE_ID", "gad8DmXGyu7hwftX9JqI")  # Essay Desk voice (under selection)
    model_id = "eleven_v3"  # Essay Desk locked model (expressive, supports [breath] audio tags)
    if "--voice" in args:
        i = args.index("--voice"); voice_id = args[i + 1]; del args[i:i + 2]
    if "--model" in args:
        i = args.index("--model"); model_id = args[i + 1]; del args[i:i + 2]

    if not args:
        print("Usage: python3 render_video.py video_script_issue_NNN.json [--slides-only]")
        sys.exit(1)
    json_path = args[0]

    data = json.load(open(json_path))
    issue = data["issue_no"]
    try:
        episode = str(int(re.sub(r"\D", "", str(issue)) or "0"))
    except ValueError:
        episode = str(issue)
    ctx = {"issue": issue, "episode": episode, "date": data["date"]}
    slides = data["slides"]
    add_links_line(slides)

    base = os.path.join("build", f"issue_{issue}")
    sdir = os.path.join(base, "slides")
    adir = os.path.join(base, "audio")
    cdir = os.path.join(base, "clips")
    for dd in (sdir, adir, cdir):
        os.makedirs(dd, exist_ok=True)

    print(f"Rendering {len(slides)} slides for issue {issue}...")
    for sl in slides:
        sid = sl["id"]
        png = os.path.join(sdir, f"slide_{sid:02d}.png")
        render_slide(sl, ctx, png)
    print(f"Slides written to {sdir}")

    # branded thumbnail from the agent's "thumbnail" block, with fallbacks to slide data.
    # The bottom tagline varies every episode: agent-authored if present, else rotated
    # from this pool by issue number (same intent - write to score higher - fresh wording).
    TAGLINES = [
        "Write the essay that lifts your rank.",
        "Craft the essay that tops the paper.",
        "Build the essay that earns the marks.",
        "Turn ideas into a top-scoring essay.",
        "Master the paper that decides the rank.",
        "From a blank page to a winning essay.",
        "The essay habit that separates ranks.",
        "Structure, substance, score, every morning.",
        "Write sharper. Argue better. Score higher.",
        "The daily rep for a top-band essay.",
        "Make the Essay paper your edge.",
        "Practice the essay that beats the cutoff.",
        "Decode, build, and score the essay.",
        "The compulsory paper, finally decoded.",
        "Score more where every mark counts.",
        "One essay a day toward the rank.",
    ]
    tb = data.get("thumbnail", {}) or {}
    def _first(k):
        for s in slides:
            if s.get(k):
                return s[k]
        return ""
    try:
        _ti = int(re.sub(r"\D", "", str(issue)) or "0")
    except Exception:
        _ti = 0
    make_thumbnail(
        tb.get("topic") or data.get("thumbnail_text") or (slides[1]["heading"] if len(slides) > 1 else data.get("video_title", "")),
        tb.get("theme") or _first("concept"),
        tb.get("section") or "",
        tb.get("archetype") or "",
        tb.get("tagline") or TAGLINES[_ti % len(TAGLINES)],
        os.path.join(base, "thumb.png"))
    print("Thumbnail written to", os.path.join(base, "thumb.png"))

    if slides_only:
        print("--slides-only set. Stopping after slide images.")
        return

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("ERROR: set ELEVENLABS_API_KEY in your environment first.")
        sys.exit(1)

    work = slides[:limit] if limit else slides

    # ---- Continuous narration, chunked under the 5000-char TTS limit ----
    # eleven_v3 resets pitch on every call, so we minimise calls: pack whole slides
    # into the FEWEST chunks under the API's 5000-char cap, synthesise each chunk as
    # one continuous take (with timestamps), then stitch. A 9-slide episode becomes
    # ~2 takes => at most one seam instead of eight per-slide restarts.
    CHAR_LIMIT = 4500
    norm = [normalize_tts(sl["narration"]) for sl in work]
    SEP = "  "
    chunks, cur, cur_len = [], [], 0
    for i, t in enumerate(norm):
        add = len(t) + (len(SEP) if cur else 0)
        if cur and cur_len + add > CHAR_LIMIT:
            chunks.append(cur); cur, cur_len = [], 0
            add = len(t)
        cur.append(i); cur_len += add
    if cur: chunks.append(cur)

    print(f"Generating narration in {len(chunks)} continuous take(s) for {len(work)} slides...")
    raw_parts, slide_end_global, cum, align_parts = [], [], 0.0, []
    for k, idxs in enumerate(chunks):
        combined = SEP.join(norm[i] for i in idxs)
        bounds, pos = [], 0
        for j, i in enumerate(idxs):
            pos += len(norm[i])
            bounds.append(pos - 1)
            if j < len(idxs) - 1:
                pos += len(SEP)
        audio_bytes, alignment = tts_full(combined, api_key, voice_id, model_id)
        part = os.path.join(base, f"part_{k:02d}.mp3")
        with open(part, "wb") as f:
            f.write(audio_bytes)
        raw_parts.append(part)
        ends = alignment.get("character_end_times_seconds", [])
        n = len(ends)
        part_dur = duration(part)
        align_parts.append({"offset": cum, "characters": alignment.get("characters", []),
                            "starts": alignment.get("character_start_times_seconds", []), "ends": ends})
        for b in bounds:
            et = ends[min(b, n - 1)] if n else part_dur
            slide_end_global.append(cum + et)
        cum += part_dur

    # concatenate the raw takes into one file, then process the whole thing once
    raw_full = os.path.join(base, "narration_raw.mp3")
    if len(raw_parts) == 1:
        os.replace(raw_parts[0], raw_full)
    else:
        listf = os.path.join(base, "raw_parts.txt")
        with open(listf, "w") as f:
            for p in raw_parts:
                f.write(f"file '{os.path.abspath(p)}'\n")
        subprocess.check_call(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listf,
                               "-c:a", "libmp3lame", "-q:a", "2", raw_full],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    master = os.path.join(base, "narration.m4a")
    prep_audio(raw_full, master, speed=speed, tail=0.12)
    master_dur = duration(master)

    raw_durs, prev = [], 0.0
    for et in slide_end_global:
        raw_durs.append(max(0.10, et - prev)); prev = et
    scale = master_dur / (sum(raw_durs) or 1.0)   # make slide times sum to the real audio length

    durations, imgs_dur = {}, []
    for i, sl in enumerate(work):
        sid = sl["id"]
        png = os.path.join(sdir, f"slide_{sid:02d}.png")
        d_i = raw_durs[i] * scale
        durations[sid] = d_i
        imgs_dur.append((png, d_i))
        print(f"  slide {sid:02d}  {d_i:.1f}s")

    final = os.path.join(base, f"video_issue_{issue}.mp4")
    build_final(imgs_dur, master, final, base)
    total = sum(durations.values())
    print(f"\nFinal video: {final}  ({fmt_ts(total)})")

    # the timings and the voice's word alignment are kept beside the video, so the metadata and
    # the captions can be rebuilt without the voice (python3 render_video.py SCRIPT --meta-only)
    with open(os.path.join(base, "timings.json"), "w") as f:
        json.dump({"durations": {str(k): v for k, v in durations.items()}, "total": total}, f)
    with open(os.path.join(base, "alignment.json"), "w") as f:
        json.dump({"speed": speed, "parts": align_parts}, f)
    write_meta_and_captions(data, work, durations, base)


def write_meta_and_captions(data, work, durations, base):
    """youtube_meta.txt (title and alternates, description with chapters from the slide starts,
    tags) and captions.srt (from the narration's word timings, if they were kept)"""
    import yt_meta
    starts, running = {}, 0.0
    for sl in work:
        starts[sl["id"]] = running
        running += durations[sl["id"]]
    chaps = yt_meta.chapters(data, starts, running)
    titles = yt_meta.long_titles(data)
    # the video's last line sends viewers to the description, so the links are full https
    # addresses (an empty ESSAY_SUBSCRIBE_URL secret used to leave the subscribe line blank)
    subscribe = (os.environ.get("ESSAY_SUBSCRIBE_URL") or "").strip() or yt_meta.SUBSCRIBE
    if not subscribe.startswith("http"):
        subscribe = "https://" + subscribe.lstrip("/")
    desc = yt_meta.long_description(data, titles[0], chaps, subscribe)
    meta = os.path.join(base, "youtube_meta.txt")
    yt_meta.write_meta(meta, titles, desc, yt_meta.long_tags(data))
    print(f"YouTube metadata: {meta}  ({titles[0]!r}, {len(chaps)} chapters)")
    if len(chaps) < 3:
        print("::warning::the long video has fewer than three chapters of ten seconds; its description carries none")

    al = os.path.join(base, "alignment.json")
    if not os.path.exists(al):
        return
    a = json.load(open(al))
    speed = float(a.get("speed") or 1.0)
    words = []
    for part in a.get("parts", []):
        # the narration is quickened once, as a whole, so a time in the raw takes over the speed is
        # its time in the video
        words += yt_meta.words_from_alignment(part.get("characters", []), part.get("starts", []),
                                              part.get("ends", []), offset=part.get("offset", 0.0),
                                              scale=1.0 / speed)
    if not words:
        print("::warning::no word timings in the voice's alignment; the long video goes up without captions")
        return
    text = yt_meta.srt(words)
    errs = yt_meta.check_srt(text)
    if errs:
        print("::warning::captions: " + "; ".join(errs[:5]))
    srt = os.path.join(base, "captions.srt")
    with open(srt, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Captions: {srt}  ({text.count(chr(10) + chr(10)) + 1} cues)")


def meta_only(json_path):
    """rebuild youtube_meta.txt and captions.srt from a rendered issue's timings.json and
    alignment.json, without the voice"""
    data = json.load(open(json_path))
    slides = data["slides"]
    add_links_line(slides)
    base = os.path.join("build", f"issue_{data['issue_no']}")
    t = json.load(open(os.path.join(base, "timings.json")))
    durations = {int(k): v for k, v in t["durations"].items()}
    write_meta_and_captions(data, [s for s in slides if s["id"] in durations], durations, base)


if __name__ == "__main__":
    main()
