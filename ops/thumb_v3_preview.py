#!/usr/bin/env python3
"""
thumb_v3_preview.py - the desk's thumbnails for stored scripts, as the daily run would make them
(thumbnails v3, else the T1 to T6 fallback), with the rotation chained across the scripts.
Read-only: it writes props files and a plan; nothing goes to YouTube and no state artifact is kept.

  python3 ops/thumb_v3_preview.py <sociology|gs|essay> <outdir> script1.json[:kind] script2.json[:kind] ...

The scripts go oldest first. GS takes the kind (prelims or mains) after a colon and keeps one
rotation per kind, as gs_daily.yml does. Writes <outdir>/<n>_props.json and <outdir>/plan.json:
[{n, script, kind, issue, format, composition, plate}], which the preview workflow renders.
"""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (HERE, os.path.join(HERE, "ops")):
    if p not in sys.path: sys.path.insert(0, p)

COMPOSITION = {"sociology": "DeskThumb", "gs": "DeskThumbV2", "essay": "DeskThumb"}


def main():
    desk, out, items = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs(out, exist_ok=True)
    plan = []
    for n, item in enumerate(items, 1):
        path, _, kind = item.partition(":")
        d = json.load(open(path))
        state = os.path.join(out, f"state_{kind or desk}.json")
        nxt = os.path.join(out, f"state_{kind or desk}.next.json")
        os.environ["THUMB_V3_STATE"] = state if os.path.exists(state) else ""
        os.environ["THUMB_V3_STATE_OUT"] = nxt
        plate = None
        if desk == "sociology":
            import soc_prep
            props, key = soc_prep.thumbnail(d)
            plate = f"{key}.jpg"
        elif desk == "gs":
            import remotion_prep
            key = remotion_prep.subject(d, json.load(open(os.path.join(HERE, "art", "library.json"))))
            plate = f"{key}.jpg"
            pub = os.path.join(out, f"public_{n}")
            os.makedirs(pub, exist_ok=True)
            props = remotion_prep.write_thumbs(d, kind or d.get("video", "prelims"), "", plate, pub)
        else:
            import desk_thumb
            props = desk_thumb.props_for(d, True)
            plate = props.get("plate") or None
        if os.path.exists(nxt):
            shutil.move(nxt, state)
        props = {k: v for k, v in props.items() if not k.startswith("_")}
        pf = os.path.join(out, f"{n}_props.json")
        json.dump(props, open(pf, "w"), ensure_ascii=False, indent=1)
        fm = props.get("f") or props.get("v") or props.get("variant")
        plan.append({"n": n, "script": path, "kind": kind, "issue": str(d.get("issue_no", "")), "format": fm,
                     "composition": COMPOSITION[desk], "plate": plate, "title": d.get("video_title", "")})
        print(f"preview {n}: issue {d.get('issue_no')} {kind} -> {fm}: {props.get('hook') or props.get('big')!r}", flush=True)
    json.dump(plan, open(os.path.join(out, "plan.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
