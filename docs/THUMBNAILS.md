# YouTube thumbnails (the long video)

Approved 7 Oct 2026: the UPSC Desk thumbnail design system (the owner's mockups,
`~/Documents/UPSC Desk Thumbnail mockups/source/DeskThumbV2.tsx`) replaces the PIL thumbnail
that `render_video.py` drew. Titles still start "UPSC Essay:" (yt_meta.py); this changes only
the picture.

## Thumbnails v3 (approved 15 Oct 2026)

The owner approved the compact header and the formats F1 to F7 of the UPSC Desk thumbnail
playbook on 15 Oct 2026. They come first on every long video; the designs below stay as the
fallback. The same two files are in all three desk repos: `ops/thumb_v3.py` (the choice and the
words) and `remotion/src/DeskThumbV3.tsx` (the drawing), drawn through this repo's usual
thumbnail composition whenever the props carry `f`. The backup of the earlier workflow is the
branch `backup/thumbnails-v2-2026-10-15` and the tag `thumbnails-v2-backup-2026-10-15`.

**Header HC.** One line top left: the desk name, then the paper in an accent pill. Issue and date
top right on current-affairs videos only. It ends at y 84. The T1 to T6 fallback uses it too.

| Id | Format | Filled from the script |
|---|---|---|
| F1 | Portrait + Verdict: the thinker (a portrait from release `thinker-portraits` when it has one, else the name, giant) and a question on the news | the lead event's thinker |
| F2 | Versus: two names either side of a VS disc, the verdict in an accent band (Essay: four topic cards) | two thinkers; GS Mains `balance`; Essay `topics` |
| F3 | Ladder: three or four steps rising left to right, on the desk's tint | three or more thinkers; GS Prelims sections; Essay dimensions |
| F4 | Stakes Object: one real number on a card (a gauge for a share), an arrow | a figure in the material, never a year |
| F5 | Proof: an answer sheet with the marks before and after | Sociology answer bridge "14 versus 19" of 20; GS Mains `band_shift` |
| F6 | Quiet Statement: a concept or the essay topic in large type | the lead concept; the essay topic |
| F7 | Strike-through: the old line crossed out over the new one | average vs top move; GS `word_swaps`; Essay "avoid ..." vs "Opening: ..." |

**The choice** (`thumb_v3.make`):
1. Content type: one small Claude call picks it from the desk's list (Sociology: current affairs,
   topic, concept, thinkers, answer writing; Essay: topic, structure, answer writing; GS Prelims:
   current affairs, geography and IR, laws; GS Mains: answer writing, laws, PYQ). Without a key
   or after three bad replies, the desk's default.
2. The content type's first choice of format, unless it was the previous video's; then its second;
   neither when both were used in the last two videos; no format more than twice in five; F3 first
   when the last five had no light surface. A format the day's script cannot fill is skipped.
3. The words: one small Claude call per format, checked in code (at most six words, the accent
   inside the hook, every number from the material, no dashes, emojis, "!", script, candidate or
   topper), three tries; F3, F5, F6 and F7 have code-built fallbacks.
4. No format fits: the T1 to T6 designs below, with header HC. That turn is logged as "T".

**The rotation state** is one small JSON (`{"formats": [...], "issue": ...}`) uploaded by the
daily run as the artifact `thumb-v3-<desk>` (GS: `thumb-v3-gs-prelims`, `thumb-v3-gs-mains`, 90
days) and read back by `ops/thumb_v3_state.sh` for the next issue. Dry runs never upload it.
`THUMB_V3=off` in the environment turns v3 off and the T1 to T6 designs draw every day.

Try it by hand: `python3 ops/thumb_v3.py <desk> script.json [--video prelims] --format F5 --no-llm --out p.json`,
then `npx remotion still src/index.ts DeskThumbV3 x.png --props=p.json` in `remotion/`.

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
