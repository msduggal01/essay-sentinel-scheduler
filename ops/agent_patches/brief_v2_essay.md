## The brief PDF, version 2 (replaces the layout of Step 6 and the FROZEN DESIGN SPECIFICATION)

The owner has approved a new design for the brief. From this run on, the PDF on brief days is
drawn by a shared kit, not by ReportLab code you write. This section overrides Step 6 and the
FROZEN DESIGN SPECIFICATION (PDF) further down (its cover, table of contents, per-essay layout,
strip, margin callouts, page furniture and footer band) and Hard Rules 0, 17, 18 and 19
wherever they describe the PDF. The desk's palette and masthead identity (Claret and Gold,
"The Essay Desk", issue and date, no image) stay, and the kit draws them; do not restyle
anything. Steps 0 to 5 and Steps 7 to 10 stay as they are: the email, the archives, the
write-back and the video are unchanged, and the file name stays
essay_desk_issue_[NNN]_[DDMMMYYYY].pdf. Everything in the voice check (BRIEF_VOICE) applies.
Video days are unchanged: no PDF.

### What you write (Step 4 stays; this is how its content fills the new brief)
Put the two essays into one file, content.json, in the shape of the kit's SCHEMA.md and
examples/essay.json: desk "essay", issue, date (DD Month YYYY), motivation (one or two plain
sentences for page 1 that ask the aspirant to write something tonight, for example an
introduction in twelve minutes), and topics, Section A first. For each topic:
- section, archetype ("Abstract" or "Socio-economic"), theme (the theme family, for the band),
  band_sub (for example "Two model essays on a brief day; this is the first"), topic (verbatim),
  asks (the decode in one or two short sentences, for the table on page 1), and pill (the trend:
  the years the family appeared and its heat, for example "Set in 2022 and 2024 · rising"; at
  most about 28 characters, so with three years write "2021, 2023, 2024 · rising").
- skeleton: [label, text] pairs from the strip: Decode, Thesis, and Ways in (the hook options).
- sets_apart: one sentence on what the top essays on this topic do; the builder prints "What
  sets the top essays apart:" before it.
- architecture: four boxes, OPENING, DECODE, LENSES, CLOSE, each a short title and a few words.
- lenses: hub (the thesis in a few words) and spokes, the six to nine dimensions in the order the
  essay uses them, each [lens, a few words].
- essay: the model essay in full, one entry per paragraph, 1,000 to 1,200 words (aim for 1,100
  to 1,180 and count with len(text.split()) before the first builder run; never over 1,200). The margin
  commentary becomes numbered notes: mark the phrase each note speaks to as [[phrase|n]], give a
  paragraph at most two notes, each at most 25 words, tagged AVOID, WHY IT SCORES, CURRENT
  AFFAIRS, EXAMPLE or ADD. Notes stay selective and varied as Step 4 says.
- lifted: the "What lifted this essay" line without those words.
- ammunition: the anchors and sourced facts the essay uses, one line each, source then the point,
  five to eight lines.
The strip's TARGET mark band is not printed in the new brief.

### How you build it
1. The kit is mounted read-only in the sandbox at /mnt/session/uploads/brief/ (briefkit.py,
   brief_build.py, SCHEMA.md, examples/essay.json); check with ls. If it is not there, try:
   mkdir -p brief_kit && for f in briefkit.py brief_build.py SCHEMA.md examples/essay.json; do curl -fsSL --max-time 60 -o "brief_kit/$(basename $f)" "https://raw.githubusercontent.com/msduggal01/essay-sentinel-scheduler/main/brief/$f" || echo "KIT DOWNLOAD FAILED: $f"; done
   and use brief_kit/ in place of the mounted folder. Read SCHEMA.md and essay.json once before
   writing content.json. ReportLab is already installed in the sandbox.
2. Write content.json in the working directory, then run:
   python3 /mnt/session/uploads/brief/brief_build.py content.json essay_desk_issue_[NNN]_[DDMMMYYYY].pdf
3. The builder checks everything first and prints each word count, "Voice check: N problems"
   and a numbered list of problems. If it exits with code 1, fix every listed problem in
   content.json (rewrite the sentence, shorten the note, move the number, adjust the word count
   and count again) and run it again, until it prints "All checks passed. Built ...". It also
   rejects a hyphen used as a dash (" - "): use a comma or a full stop. Copy its word counts and
   the Voice check line into your log.
4. The PDF is ready when the builder exits 0. This replaces the 60KB size check: the
   size depends on the fonts in the sandbox (about 90 KB there today) and does not matter. Email it in Step 7 as before.

### If the kit cannot be used
If the kit is neither mounted nor downloadable, or the builder still reports problems after six rounds of
fixes, build this one run's PDF the old way, following the FROZEN DESIGN SPECIFICATION as
written, and write one line in your log beginning "BRIEF V2 FALLBACK:" with the reason and the
builder's last output. Never skip the brief on a brief day.
