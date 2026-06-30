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
  youtube_meta.txt      title, description with chapter timestamps, tags
"""

import os
import sys
import re
import json
import random
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
        d.text((MARGIN, 30), f"The Essay Desk   |   Issue {ctx['issue']}   |   {ctx['date']}",
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
    return text

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
def main():
    args = sys.argv[1:]
    slides_only = "--slides-only" in args
    args = [a for a in args if a != "--slides-only"]

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
    ctx = {"issue": issue, "date": data["date"]}
    slides = data["slides"]

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
    raw_parts, slide_end_global, cum = [], [], 0.0
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

    # build YouTube metadata with chapter timestamps
    cum = {}
    running = 0.0
    for sl in work:
        cum[sl["id"]] = running
        running += durations[sl["id"]]

    lines = []
    lines.append(data["video_title"])
    lines.append("")
    lines.append(data["video_description"])
    lines.append("")
    lines.append("Join our Telegram channel for the daily masterclass and the latest updates:")
    lines.append("https://t.me/upscdesk_essay   (@upscdesk_essay)")
    lines.append("")
    lines.append("Subscribe to the full daily Essay brief - two model essays with the examiner's commentary, three mornings a week:")
    lines.append(os.environ.get("ESSAY_SUBSCRIBE_URL", "https://subscribe.upscdesk.com/essay/"))
    # AI-narration disclosure: NOT on every video - show it on roughly 1 in 10 videos only.
    if random.random() < 0.1:
        lines.append("")
        lines.append("Narration is AI-generated. Content is researched and edited by UPSC Desk.")
    lines.append("")
    lines.append("Chapters:")
    lines.append(f"{fmt_ts(0)} Introduction")
    for ch in data.get("chapters", []):
        sid = ch["slide_id"]
        lines.append(f"{fmt_ts(cum.get(sid, 0))} {ch['title']}")
    lines.append("")
    lines.append("Tags: " + ", ".join(data.get("tags", [])))
    meta = os.path.join(base, "youtube_meta.txt")
    with open(meta, "w") as f:
        f.write("\n".join(lines))
    print(f"YouTube metadata: {meta}")

if __name__ == "__main__":
    main()
