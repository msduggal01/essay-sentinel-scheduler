#!/usr/bin/env python3
"""
carousel_render.py - one PNG per slide of the day's carousel, from carousel_props.py's props.

  python3 ops/carousel_render.py carousel_out/props.json carousel_out

remotion/src/DeskCarousel.tsx draws every slide (compositions DeskCarousel, 1080 x 1350, and
DeskCard, 1080 x 1080, registered in remotion/src/Root.tsx). The project is bundled once and
each slide is a still of that bundle with the props {desk, issue, date, square, i, n, slide}.
Writes slide_01.png ... slide_NN.png and sheet.jpg (all the slides side by side, to look at).

A slide whose words do not fit spills out of its page, and nothing in the browser says so.
Each still is checked for that in the pixels: the white strips between the band header and
the page, and between the page and the footer, must stay white; the cover's headline must stay
inside its band; the last slide's box must stay above its footer. A slide that spills and is
optional (carousel_props.py marks them) is left out and the carousel rendered again; a spill on
a slide the carousel needs exits 2 with a ::warning::, so nothing is posted that day.
"""
import json, os, subprocess, sys, tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REM = os.path.join(ROOT, "remotion")
PAGE_KINDS = {"pipeline", "question", "answer", "mostwrite", "ladder", "budget", "card", "opening", "anchors",
              "mistake", "checklist", "glossary", "mcq", "picture"}


def warn(msg):
    print(f"::warning::{msg}")
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as f: f.write(f"- {msg}\n")
        except OSError:
            pass


def count(img, box, test):
    raw = img.crop(box).tobytes()
    return sum(1 for k in range(0, len(raw), 3) if test(raw[k:k + 3]))


def spills(png, kind):
    """True when the slide's words have run out of their place"""
    img = Image.open(png).convert("RGB")
    W, H = img.size
    not_white = lambda p: max(abs(255 - c) for c in p) > 40
    near_white = lambda p: min(p) > 215
    if kind in PAGE_KINDS:
        return count(img, (40, 135, W - 40, 149), not_white) > 30 or count(img, (40, H - 99, W - 40, H - 84), not_white) > 30
    if kind == "cover":
        # white headline letters low in the band, or the takeaway box running into the footer
        return count(img, (72, 728, 700, 764), near_white) > 60 or count(img, (40, H - 99, W - 40, H - 84), not_white) > 30
    if kind == "practice":
        return count(img, (72, H - 100, W - 72, H - 84), near_white) > 60
    return False


def bundle(tmp):
    out = os.path.join(tmp, "bundle")
    subprocess.run(["npx", "remotion", "bundle", "src/index.ts", "--out-dir", out], cwd=REM, check=True)
    return out


def render(props, outdir, serve, tmp):
    slides = props["slides"]
    comp = "DeskCard" if props.get("square") else "DeskCarousel"
    pngs = []
    for i, s in enumerate(slides):
        inp = {"desk": props["desk"], "issue": props.get("issue", ""), "date": props.get("date", ""), "square": bool(props.get("square")),
               "i": i, "n": len(slides), "slide": {k: v for k, v in s.items() if k != "optional"}}
        pf = os.path.join(tmp, f"p{i}.json")
        json.dump(inp, open(pf, "w", encoding="utf-8"), ensure_ascii=False)
        png = os.path.join(outdir, f"slide_{i + 1:02d}.png")
        subprocess.run(["npx", "remotion", "still", serve, comp, os.path.abspath(png), f"--props={pf}", "--log=error"], cwd=REM, check=True)
        pngs.append(png)
    return pngs


def sheet(pngs, path):
    ims = [Image.open(p).convert("RGB") for p in pngs]
    h = 540
    ims = [im.resize((round(im.width * h / im.height), h)) for im in ims]
    out = Image.new("RGB", (sum(im.width for im in ims) + 12 * (len(ims) - 1), h), "white")
    x = 0
    for im in ims:
        out.paste(im, (x, 0)); x += im.width + 12
    out.save(path, quality=88)


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    props = json.load(open(src, encoding="utf-8"))
    os.makedirs(outdir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        serve = bundle(tmp)
        for _ in range(4):
            for f in os.listdir(outdir):
                if f.startswith("slide_") and f.endswith(".png"): os.remove(os.path.join(outdir, f))
            pngs = render(props, outdir, serve, tmp)
            bad = [i for i, (p, s) in enumerate(zip(pngs, props["slides"])) if spills(p, s["kind"])]
            if not bad:
                break
            need = [i for i in bad if not props["slides"][i].get("optional")]
            if need:
                warn(f"carousel: the {props['slides'][need[0]]['kind']} slide does not fit its page; no carousel today")
                return 2
            for i in reversed(bad):
                print(f"carousel: the {props['slides'][i]['kind']} slide does not fit its page and is left out")
                props["slides"].pop(i)
        else:
            warn("carousel: slides still spilled after three passes; no carousel today")
            return 2
    if len(props["slides"]) < 2:
        warn("carousel: fewer than two slides fit; no carousel today")
        return 2
    json.dump(props, open(src, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sheet(pngs, os.path.join(outdir, "sheet.jpg"))
    print(f"carousel: {len(pngs)} slides rendered to {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
