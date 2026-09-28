# The brief content file (brief v2)

`brief_build.py content.json out.pdf` draws the approved v2 brief from one JSON file. It checks
the content first and builds nothing until every check passes. Worked examples, one per desk,
are in `examples/sociology.json` and `examples/essay.json`: copy the shape, not the words.

In the desks' agent sandboxes the kit is mounted read-only at `/mnt/session/uploads/brief/` by the
workflow that starts the session (`mount_kit.py`), because the sandbox network cannot reach GitHub:

```
python3 /mnt/session/uploads/brief/brief_build.py content.json sociology_desk_issue_126_27SEP2026.pdf
```

Anywhere with network access, fetch it instead:

```
curl -fsSL -o briefkit.py    https://raw.githubusercontent.com/msduggal01/essay-sentinel-scheduler/main/brief/briefkit.py
curl -fsSL -o brief_build.py https://raw.githubusercontent.com/msduggal01/essay-sentinel-scheduler/main/brief/brief_build.py
```

Needs Python 3 and ReportLab. Arial and Georgia are used when the machine has them, else Liberation
Sans (the same size as Arial, installed in the sandboxes), else the built-in Helvetica; the serif
falls back to the built-in Times. The layout is the same in every case. The PDF's size depends on
which fonts were embedded (about 90 KB in the sandbox, 15 to 40 KB with only built-in fonts):
judge it by the builder's exit code, not by its size.

## Markup inside any text

| Write | Shows as |
|---|---|
| `[[graded inequality\|2]]` | the phrase highlighted, with a small red 2 after it (answer and essay paragraphs only) |
| `*Annihilation of Caste*` | italic (titles of books, cases, reports) |
| `**text**` | bold |

Plain text otherwise: no HTML, no dashes of any kind, no emojis, no exclamation marks.

## Top level

| Key | Type | Notes |
|---|---|---|
| `desk` | `"sociology"` or `"essay"` | picks the palette, masthead and page plan |
| `issue` | text | `"126"`; padded to three digits |
| `date` | text | `"27 September 2026"` (DD Month YYYY) |
| `motivation` | text | the dark box on page 1: one or two plain sentences |
| `events` | list | Sociology: one entry per selected event, in the order of the issue |
| `topics` | list | Essay: one entry per topic (two on a brief day, Section A then B) |

Page 1 (masthead, "Today in this issue" table, the margin legend, the motivation box) is made
from these; the table rows come from the events or topics. Each event or topic then starts
on a new page.

## A Sociology event

| Key | Type | Notes |
|---|---|---|
| `paper` | 1 or 2 | |
| `syllabus` | text | the unit, for the band: `"Caste system, Dalit movements"` |
| `title` | text | the event's title, under the band and in the table |
| `question` | text | the probable question, without quotation marks |
| `question_summary` | text | the table's short form: `"Caste as a division of labourers: critically examine (20 marks)"` |
| `marks` | 10, 15 or 20 | sets the word limit: 150 for 10 marks, 250 for 15 or 20 |
| `pill` | text, optional | the third tag under the question: `"Asked before: Ambedkar on caste"` |
| `meters` | `{difficulty, probability}` | each `{"level": 1 to 5, "reason": "..."}`, the reason at most 12 words; drawn as five dots each under the tags in the question box |
| `also_likely` | `{question, marks}` | the second probable question, printed under the question box as "Also likely: ..." with its marks tag; `marks` 10, 15 or 20; at most 45 words and two lines |
| `skeleton` | list of `[label, text]` | 3 to 7 lines: `["Introduction", "Ambedkar, 1936, and graded inequality as the idea you will test."]` |
| `sets_apart` | text | finishes "What sets the top answers apart: ..." (do not repeat those words) |
| `chain` | list of `{label, title, text}` | 3 to 5 boxes, news to answer: `THE NEWS`, `THE CONCEPT`, `THE THINKER`, `THE ANSWER` |
| `answer` | list of paragraphs | the complete model answer, see below |
| `ammunition` | list of `{source, line}` | 3 to 10: `{"source": "Ambedkar, *Annihilation of Caste* (1936)", "line": "Caste is a division of labourers as well as of labour."}` |
| `anchors` | list of `{thinker, concept, work, year, application}` | 2 to 4 theoretical anchors, printed in the Ammunition box as "Thinker, concept (*Work*, year): application"; `work` and `year` only when you are certain of them (leave both out otherwise); `application` at most 25 words |
| `comparative_lens` | text | 100 to 120 words, printed in its own box after the Ammunition, titled "Comparative lens" |
| `thinker` | `{name, dates, text}` | thinker of the day; `dates` optional (`"1891 to 1956"`); `text` two or three sentences |
| `practice` | text | the closing dark box: `"Write this answer tonight in eighteen minutes, then get it evaluated at evaluate.upscdesk.com."` |

## An Essay topic

| Key | Type | Notes |
|---|---|---|
| `section` | `"A"` or `"B"` | |
| `archetype` | text | `"Abstract"` or `"Socio-economic"`; the first tag and the table's section column |
| `theme` | text | the theme family, for the band |
| `band_sub` | text, optional | the small line under the band |
| `topic` | text | the topic, verbatim |
| `asks` | text | the table's "What it asks": one or two short sentences |
| `pill` | text, optional | the third tag: `"Set in 2022 and 2024 · rising"` (years and heat) |
| `skeleton` | list of `[label, text]` | 3 to 7 lines, usually Decode, Thesis, Ways in |
| `sets_apart` | text | finishes "What sets the top essays apart: ..." |
| `architecture` | list of `{label, title, text}` | 3 to 5 boxes: `OPENING`, `DECODE`, `LENSES`, `CLOSE` |
| `lenses` | `{hub, spokes}` | `hub` a few words; `spokes` 4 to 9 `[lens, few words]` in the order the essay uses them, drawn clockwise from the top |
| `essay` | list of paragraphs | the complete model essay, see below |
| `lifted` | text | finishes "What lifted this essay: ..." |
| `ammunition` | list of `{source, line}` | as above |
| `practice` | text, optional | a closing dark box after the ammunition |

## A paragraph of the answer or essay

```json
{"text": "... He called this [[graded inequality|2]]: every caste has one above it ...",
 "notes": [{"n": 2, "tag": "WHY IT SCORES", "text": "The concept is named in the first three lines, with the book and the year."}]}
```

`tag` is one of `AVOID`, `WHY IT SCORES`, `CURRENT AFFAIRS`, `EXAMPLE`, `ADD`. A paragraph may
have no notes (`"notes": []`).

## What the builder checks (each failure is listed; fix the content and run again)

- Word count of the model answer: 143 to 150 words for 10 marks, 238 to 250 for 15 or 20 marks
  (within five per cent under, never over); the model essay 1,000 to 1,200 words. Counted as
  `len(text.split())` over the words the reader sees, printed beside the heading.
- Sociology: `meters`, `also_likely`, `anchors` and `comparative_lens` are all present; each meter
  level is 1 to 5 and its reason at most 12 words and one line; the second question differs from
  the first and fits two lines; 2 to 4 anchors, each application at most 25 words; the comparative
  lens 100 to 120 words (printed with the answer's count). The voice checks apply to all of them.
- Every note number marks exactly one phrase in the paragraph the note sits beside, and every
  highlighted number has its note; numbers run 1, 2, 3 in reading order within each event or topic.
- A note is at most 25 words; at most two notes per paragraph; the note column is never taller
  than its paragraph.
- Text that would be cut off: chain or architecture boxes, the lens hub and lenses, the tags.
- No em or en dashes, no double hyphen, no spaced hyphen used as a dash, no emojis, no
  exclamation marks; never "script" or "candidate" (write answer, essay, aspirant).
- The brief-voice list: the banned words (delve, tapestry, landscape, navigate, pivotal, crucial,
  robust, holistic, multifaceted, nuanced, underscore, testament, realm, embark, unlock, harness,
  leverage, paradigm, synergy, game-changer, seamless, intricate, myriad) and phrases (in today's
  world, in an era of, it is important to note, arguably, at its core, ultimately, in conclusion,
  the need of the hour, and the rest); an "Imagine" opener; a colon reveal; a clipped
  one or two word sentence (except the directive a question ends on, such as "Comment."); the "not X, but Y" turn more than once in the whole brief. A phrase
  inside quotation marks, quoted in order to warn against it, is not counted.
- Every character can be drawn in the font in use (write "Rs" or "rupees" if the rupee sign cannot).

The builder prints the fonts, each word count, `Voice check: N problems`, then either the numbered
problems (exit code 1, no PDF) or `All checks passed. Built ...` (exit code 0).
`python3 brief_build.py content.json --check` runs the checks without building.
