# Video elements catalogue (long videos and Reels)

The motion grammar for UPSC Desk videos, separate from the brief catalogue (which the PDF briefs,
carousels and cards use). Approved 27 Sep 2026; the owner's catalogue is
`Video_elements_catalogue.pdf` (~/Documents/UPSC Desk Video elements/, and the upsc-desk-design
skill's references/elements/), with every new element working in `video_elements_demo.mp4`.

Rule: 10 to 15 core elements appear in every long video whatever the content; the rest are picked
by the narration, the content and the topic. Nothing new is added to a daily video without a
mockup the owner has approved.

## Core: drawn by the engine in every long video (no one asks for them)

| # | Element | Where it is drawn (remotion/src/Video.tsx) | Fed by |
|---|---|---|---|
| 1 | Camera zoom in and out | `Camera` | slide `camera` cues |
| 2 | Ruled answer sheet | `AnswerSheet`, `Coached` | answer_sheet, coached, rewrite |
| 5 | Highlight sweep | `Marked` (kind hl) | marks |
| 6 | Underline sweep | `Marked` (kind ul) | marks |
| 7 | Red strike-through | `Marked` (kind strike) | marks |
| 8 | Green insert | `AnswerSheet` (rewrite inserts) | rewrite inserts |
| 10 | Margin notes on the sheet | `MarginNote` in `AnswerSheet` | marks[].note |
| 11 | Boxes and cards | `StatementCards`, `QuestionCard`, `Ledger`, `EndCard` | those layouts |
| 16 | Marks counter | `BandShift` | band_shift |
| 20 | Pop-in entrances | `useReveal`, `rise` | anchors |
| 21 | End card with the offer | `EndCard` | end_card |
| N01 | Callout that points | `QuestionCard` (directive regex) | the directive mark |
| N03 | Ticks and stamps | `MarkGlyph`, `Stamp` | marker pass, rewrite gain |
| N04 | Writing timer | `TaskTimer` in `EndCard` | end_card task_minutes |
| N05 | Live word counter | `AnswerSheet` read-along | answer_sheet read_along |
| N11 | Source card | `SourceCard` overlay | ledger first row source |
| N15 | Chapter card | `ChapterStrip` overlay | chapters from the slide order |
| N16 | Sticky note | `Sticky` | coached |

## Optional: picked by the content (at most two per video)

| # | Element | Layout | When |
|---|---|---|---|
| N09 | Timeline | `timeline` (`TimelineL`) | three to five dated steps in the sources |
| N10 | Balance of arguments | `balance` (`BalanceL`) | critically examine, discuss, evaluate |
| N13 | Venn | `venn` (`VennL`) | compare and contrast, two thinkers or institutions |
| N14 | Term card | `term_card` (`TermCardL`) | one term the answer must use |
| N12 | Growing data bars | `data_bars` (`DataBarsL`) | figures stated in the sources only |
| N06 | Split screen | `split_screen` (`SplitScreenL`) | average against top answer |
| N08 | Self-check list | `checklist` (`ChecklistL`) | before the end card |
| N02 | Pen circle | `Marked` (kind circle) | a key word on the question |
| N07 | Magnifier | `Marked` (kind lens) | one line of the model answer |
| 14 | Mind maps | `mind_map` (`MindMap`) | Prelims and concept slides |
| 15 | Hub and spokes | `connect_dots` (`ConnectDots`) | syllabus neighbours |
| 17 | Word budget | `word_budget` (`WordFlow`) | where the words go |
| 18 | Countdown ring | `prelims_question` | Prelims questions |
| 9 | Struck phrase, arrow, new phrase | `word_swaps` (`WordSwaps`) | the weak and scoring phrase |
| 13 | Pipeline of boxes | Reels (`DeskShort`, `GSShort`) and statement cards | news, concept, thinker, answer |

## Reels (DeskShort on Sociology and Essay, GSShort on GS)

Ruled sheet (2), handwritten text (3), typewriter (4), strike-through (7), struck phrase and arrow
(9), margin notes (10), arrows that draw (12), pipeline (13), marks counter (16), countdown ring
(18, GS), progress bar (19), end card (21).

## Where each desk stands

- GS: all of the above in `remotion/src/Video.tsx`; the agent is told the optional ones in
  `ops/agent_patches/elements.md` (live on the GS agent); `validate_script.py` accepts them.
- Sociology: the same engine copy in `remotion/src/Video.tsx`; `soc_prep.py` offers the optional
  ones to the composer (RULES, OPTIONAL ELEMENTS) and checks them (`extra_errors`).
- Essay: Reels only (DeskShort). The long video still renders with `render_video.py`; the library
  comes with its Remotion port, after a mockup the owner approves.
