# YouTube thumbnails (the long video)

Approved 7 Oct 2026: the UPSC Desk thumbnail design system (the owner's mockups,
`~/Documents/UPSC Desk Thumbnail mockups/source/DeskThumbV2.tsx`) replaces the PIL thumbnail
that `render_video.py` drew. Titles still start "UPSC Essay:" (yt_meta.py); this changes only
the picture.

## Where it is made

| Piece | File |
|---|---|
| The design, 1280 x 720, composition `DeskThumb` | `remotion/src/DeskThumb.tsx` (registered in `remotion/src/Root.tsx`) |
| The words, the layout, the render | `ops/desk_thumb.py video_script.json` |
| The art plate | `assets/thumb/plate.jpg` (the Sociology art library's `social.jpg`, 1600 x 900), copied to `remotion/public/thumb_plate.jpg` at render time |
| The workflow step | "YouTube thumbnail in the design system" in `essay_daily.yml` and `essay_rerun.yml`, after "Render video", before the upload |

`render_video.py` still draws its PIL thumbnail at `build/issue_N/thumb.png` first. The Remotion
still (`npx remotion still src/index.ts DeskThumb`) then replaces it; the PIL one is kept beside it
as `thumb_pil.png` and the props as `thumb_props.json`. If anything fails (Chrome libraries,
`npm ci`, the still, a size over 2 MB), the step prints a `::warning::` and the PIL thumbnail is
uploaded as before. A thumbnail never stops the day's upload.

## The rules

- **Header H2** on every Essay thumbnail: a full-width gold bar, "UPSC CIVIL SERVICES EXAMINATION"
  left and "ESSAY PAPER" right; under it "THE ESSAY DESK" and "Issue N · 7 October 2026" (the
  day's date without a leading zero). Claret and gold (night `#240E14`, deep `#7A2D3A`, gold
  `#E0B35A`), Barlow Condensed.
- **The hook**: at most six words from the essay topic, its key phrase, as a statement or a
  question (e.g. "When the Ballot Outpaces the Home"). One small Claude call (`claude-sonnet-5`,
  as `ops/reel_props.py`) from the real topic (`yt_meta.essay_topic`: `thumbnail.topic`, else the
  topic slide's heading when it is not a label, else the spoken topic line) and the key phrase.
  Checked in code: six words at most, under 45 characters, no "script" or "candidate", no
  dashes, hyphens, emojis or "!", not a label ("Today's topic", "UPSC", the desk). Sent back with
  the reasons, three tries. Fallback: the key phrase (the video title's middle, or the agent's
  thumbnail text when the title's is over six words) cut to six words at a word boundary.
- **The accent**: the hook's key words, copied exactly (a substring), in gold.
- **The key word**: for T2 (the giant word) and T5 (the stamp, labelled "KEY WORD"), the topic's
  one key word, at most 12 letters, from the topic or the hook (e.g. "Ballot"). No key word (or
  the fallback hook) means T2 and T5 are skipped that day.
- **Rotation**: one of T1 to T6 per issue, pseudo-random from a hash of the issue number, never
  the previous issue's. `v(n) = v(n-1) + 1 + h(n) mod 5 (mod 6)`; when v(n) is T2 or T5 and there
  is no key word, a stand-in from T1, T3, T4, T6 that is neither v(n-1), the previous stand-in,
  nor v(n+1). No state is kept; checked for every combination over issues 1 to 1200.
- **Art**: T1, T2, T3, T5 use the plate under a claret fade; without the plate, a plain claret
  gradient. T4 and T6 use no art.

## The six layouts

| | Layout | The hook's box |
|---|---|---|
| T1 | the hook large over the art, a gold rule under it | x 48 to 868, bottom-anchored at y 628, up to 112 px |
| T2 | the key word giant in gold, the hook under it in cream | x 48 to 1232, from y 205, all above y 590 |
| T3 | a full-width gold band carrying the hook in night | the band ends by y 600; it rises from y 330 when the hook needs three lines |
| T4 | an oversized gold quotation mark, the hook beside it, no art | x 230 to 1210, y 230 to 590; the dots only where the hook leaves room |
| T5 | the hook, a rotated gold stamp with the key word | x 48 to 808, y 215 to 590; the stamp x 880 to 1210 |
| T6 | minimal type, not upper case, one gold phrase, no art | x 48 to 1232, centred in y 160 to 600 |

Every hook is fitted: measured in the loaded font and shrunk until it fits its box, so no hook
overflows, nothing starts above y 150 (the H2 header ends at about y 135), and nothing is drawn in
the bottom-right 300 x 120 (x 980 to 1280, y 600 to 720), where YouTube puts the timestamp.
Checked with every layout and the longest hooks (six long words, e.g. "Institutional
Accountability Versus Bureaucratic Discretion", a 12-letter key word).

## Changing it

Change the design only from an approved mockup. Render a layout locally with
`python3 ops/desk_thumb.py video_script.json --out x.png --variant T4 --no-llm` (needs
`npm ci` in `remotion/`).
