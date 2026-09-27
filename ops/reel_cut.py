#!/usr/bin/env python3
"""
reel_cut.py - voice the Reel, time every element to its word, render it, write its metadata.

  python3 ops/reel_cut.py reel_props.json reel.mp4 reel_meta.txt

The narration is built from the Reel's own lines, so what is said is what is on screen. It
goes to ElevenLabs (eleven_v3, /with-timestamps, the desk's voice from VOICE_ID), is quickened
with ffmpeg (v3 ignores its speed setting), and each beat is the moment its cue phrase is
spoken in the character alignment. Then Remotion renders the DeskShort composition.

Env: ELEVENLABS_API_KEY, VOICE_ID (the desk's voice), REEL_TEMPO (default 1.34).
"""
import base64, json, os, re, subprocess, sys, urllib.request

TEMPO = float(os.environ.get("REEL_TEMPO", "1.34"))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTION = os.path.join(HERE, "remotion")
NUM = {7: "seven", 8: "eight", 9: "nine", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty"}


def say(s):
    """what the voice should read for an on-screen line"""
    s = s.replace("·", ",").replace("&", "and").replace("%", " per cent")
    return re.sub(r"\s+", " ", s).strip()


def sent(s):
    s = say(s).rstrip()
    return s if s.endswith((".", "?")) else s + "."


def narration(d):
    """(text, cues): cues map a beat to the phrase that fires it, in speaking order"""
    parts, cues = [], []
    def add(text, beat=None, cue=None):
        if beat: cues.append((beat, cue or text))
        parts.append(text)
    def notes(d):
        """the margin notes in one breath, each still firing its own strike"""
        ns = [say(l["note"]).rstrip(".") for l in d["average"]]
        for i, n in enumerate(ns):
            cues.append((f"s{i}", n.lower()))
        parts.append(", ".join(ns).capitalize() + ".")
    if d["desk"] == "sociology":
        add(sent(d["headline"]), "hook", sent(d["headline"])[:20])
        add("Is this Sociology?", "hook2")
        add(f"It is Paper {'one' if d.get('paper') == '1' else 'two'}.")
        add(f"The news, {say(d['news']['title'])}.", "news", "The news")
        add(f"The concept, {say(d['concept']['title'])}.", "concept", "The concept")
        add(f"The thinker, {say(d['thinker']['title'])}.", "thinker", "The thinker")
        add(f"The question. {sent(d['question'])}", "question", "The question")
        add(f"{d['directive']}.", "directive", d["directive"])
        add("Most aspirants open like this.", "write", "Most aspirants open")
        add(" ".join(say(l["text"]) for l in d["average"]).rstrip(".,;") + ".")
        notes(d)
        add("Now write it as sociology.", "fix", "write it as sociology")
        for i, l in enumerate(d["better"]):
            add(sent(l), f"f{i}", say(l)[:18])
        add(f"Name the concept, and {NUM.get(d['from'], d['from'])} becomes {NUM.get(d['to'], d['to'])} out of twenty.", "jump", "Name the concept")
        add("Write this answer, then get it evaluated at evaluate dot upscdesk dot com.", "cta", "Write this answer")
        add("Five free every month.", "free", "Five free")
    else:
        add(sent(d["topic"]), "hook", sent(d["topic"])[:20])
        add("Could you write this essay?", "hook2", "Could you write")
        add(f"Most read it as {say(d['literal']).rstrip('.').lower()}.", "literal", "Most read it")
        dec = sent(d["decode"]); add(f"It asks: {dec[0].lower() + dec[1:]}", "decode", "It asks")
        ls = [say(l["title"]).lower() for l in d["lenses"]]
        cues.append(("lenses", "Read it through"))
        for i, t in enumerate(ls):
            cues.append((f"l{i}", t))
        count = {3: "three", 4: "four", 5: "five", 6: "six", 7: "seven"}.get(len(ls), str(len(ls)))
        parts.append(f"Read it through {count} lenses: " + ", ".join(ls[:-1]) + f" and {ls[-1]}.")
        add("Now the opening most write.", "open", "the opening most write")
        add(" ".join(say(l["text"]) for l in d["average"]).rstrip(".,;") + ".")
        notes(d)
        add("Open with a claim instead.", "fix", "Open with a claim")
        for i, l in enumerate(d["better"]):
            add(sent(l), f"f{i}", say(l)[:18])
        add("Write this essay, then get it evaluated at evaluate dot upscdesk dot com.", "cta", "Write this essay")
        add("Five free every month.", "free", "Five free")
    return " ".join(parts), cues


def tts(text, voice):
    body = {"text": text, "model_id": "eleven_v3",
            "voice_settings": {"stability": 0.55, "similarity_boost": 0.90, "style": 0.18, "use_speaker_boost": True}}
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps", data=json.dumps(body).encode(),
                                 headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "content-type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=240).read())
    return base64.b64decode(r["audio_base64"]), r["alignment"]


def beats_from(text, al, cues):
    chars, starts, ends = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    spoken = "".join(chars).lower()
    B, pos, last = {}, 0, 0.0
    for beat, cue in cues:
        i = spoken.find(cue.lower()[:24], pos)
        t = starts[i] / TEMPO if i >= 0 else last + 0.6
        if i >= 0: pos = i + 1
        t = max(t, last + 0.05) if beat != "hook" else 0.2
        B[beat], last = round(t, 3), t
    return B, round(ends[-1] / TEMPO + 1.4, 2)


def fit_title(base, tail):
    """YouTube allows 100 characters; drop the label before cutting the words, then cut at a word"""
    for t in (base + tail, base + " #Shorts"):
        if len(t) <= 100: return t
    words, out = base.split(), ""
    for w in words:
        if len(out + " " + w) + 11 > 100: break
        out = (out + " " + w).strip()
    return out.rstrip(",:;") + "... #Shorts"


def meta(d, path):
    if d["desk"] == "sociology":
        title = fit_title(f"Is this Sociology? {d['news']['title']}: {d['concept']['title']}", " | UPSC in 30s #Shorts")
        desc = (f"{d['headline']} Read it as sociology: {d['concept']['title']}, with {d['thinker']['title']}.\n\n"
                f"The question: {d['question']} {d['directive']}.\n\n"
                "Write this answer, then get it evaluated: https://evaluate.upscdesk.com (five free every month)\n"
                "Telegram: https://t.me/upscdesk_sociology\n\n#UPSC #Sociology #SociologyOptional #UPSCMains #IAS #Shorts")
        tags = ["UPSC", "Sociology Optional", "UPSC Mains", d["concept"]["title"], d["thinker"]["title"], "answer writing"]
    else:
        title = fit_title(f"Could you write this essay? {d['topic']}", " | UPSC Essay #Shorts")
        desc = (f"\"{d['topic']}\"\n\nWhat it asks: {d['decode']}\n\nLenses: " + ", ".join(l["title"] for l in d["lenses"]) + ".\n\n"
                "Write this essay, then get it evaluated: https://evaluate.upscdesk.com (five free every month)\n"
                "Telegram: https://t.me/upscdesk_essay\n\n#UPSC #Essay #UPSCEssay #UPSCMains #IAS #Shorts")
        tags = ["UPSC", "UPSC Essay", "Essay writing", "UPSC Mains"] + [l["title"] for l in d["lenses"][:3]]
    with open(path, "w") as f:
        f.write(title + "\n\n" + desc + "\n\nTags: " + ", ".join(tags) + "\n")


def main():
    src, out, meta_path = sys.argv[1], sys.argv[2], sys.argv[3]
    props = json.load(open(src)); d = props["data"]
    text, cues = narration(d)
    print("reel_cut: narration:", text)
    audio, al = tts(text, os.environ["VOICE_ID"])
    pub = os.path.join(REMOTION, "public"); os.makedirs(pub, exist_ok=True)
    raw, fast = os.path.join(pub, "reel_voice_raw.mp3"), os.path.join(pub, "reel_voice.mp3")
    open(raw, "wb").write(audio)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-filter:a", f"atempo={TEMPO}", fast], check=True)
    B, seconds = beats_from(text, al, cues)
    # the sheet's strikes and the rewrite's lines, each on its own spoken word
    data = dict(d)
    data["strikeAt"] = [B[k] for k in ("s0", "s1", "s2") if k in B]
    data["fixAt"] = [B[k] for k in ("f0", "f1", "f2") if k in B]
    if d["desk"] == "essay":
        data["lensAt"] = [B[f"l{i}"] for i in range(len(d["lenses"])) if f"l{i}" in B]
    B["strike"] = data["strikeAt"][0] if data["strikeAt"] else B.get("fix", 0) - 3
    props = {"beats": B, "data": data, "voice": "reel_voice.mp3", "seconds": seconds}
    pj = os.path.join(pub, "reel_props.json"); json.dump(props, open(pj, "w"), ensure_ascii=False, indent=1)
    print("reel_cut: beats", json.dumps(B), "seconds", seconds)
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "DeskShort", os.path.abspath(out), f"--props={pj}", "--log=error"],
                   cwd=REMOTION, check=True)
    meta(d, meta_path)
    print("reel_cut: made", out)


if __name__ == "__main__":
    main()
