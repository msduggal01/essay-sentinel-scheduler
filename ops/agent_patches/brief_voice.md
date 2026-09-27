## The brief is written by a person: the voice check (applies to every word of the brief and the email)

The owner reads every brief. Text that sounds generated costs the desk its credibility with
aspirants, so the brief is held to the same standard as the narration. This covers every text
element: headings, the question box, the skeleton, the model answer or essay, every margin note,
the ammunition, the thinker or anchor of the day, the motivation line, tables and the email.

### How to write it
Write the way a senior teacher explains something to one aspirant across a desk. Say the point
directly, in full sentences with ordinary verbs. Mix short and medium sentences. Prefer the
concrete example to the abstract claim. Plain words; the paper's own technical terms stay exact.

### What never appears
- The "not X, but Y" or "it is not A; it is B" flourish, and "not just ... but also". At most
  once in a whole brief, and only when the contrast is the point.
- Lists of three used for rhythm. Use the number of items the facts have.
- Openers and fillers: "In today's world", "In an era of", "In the ever-evolving", "Imagine",
  "Picture this", "Let's dive in", "Here's the thing", "It is important to note that",
  "It is worth mentioning", "In many ways", "Arguably", "At its core", "Ultimately".
- These words: delve, tapestry, landscape (as a metaphor), navigate (as a metaphor), pivotal,
  crucial, robust, holistic, multifaceted, nuanced, underscore, testament, realm, embark,
  unlock, harness, leverage, paradigm, synergy, game-changer, seamless, intricate, myriad,
  a stark reminder, a double-edged sword, the need of the hour, a clarion call.
- Rhetorical questions used as hooks, one-word or clipped sentences for effect ("Simple."),
  colon reveals ("The answer: ..."), and paragraphs that end on a slogan or aphorism.
- Em dashes, en dashes, double hyphens, exclamation marks, emojis, Title Case headings in body.
- Any figure, quotation, year, case or report that is not in the source you were given.

### The complete answer, at its word limit
The model answer (Sociology, GS) or model essay (Essay) is written out in full, at its word
limit: 150 words for a 10-mark question, 250 for a 15 or 20-mark question, and 1,000 to 1,200
words for an essay. For a single limit, stay within five per cent under it and never over it; an
essay stays between 1,000 and 1,200 words. Count the words
with code (len(text.split())), not by estimate, and print the count beside the heading, for
example "Model answer, 247 words (limit 250)". Margin notes stay short (at most 25 words each,
at most two per paragraph), so that no note column runs longer than the paragraph beside it.

### The check, before the PDF is built
After all the brief's text is written and before the PDF is generated, run one Python pass over
every text field. It lists each sentence that contains a phrase or word above, and each dash or
exclamation mark. Rewrite every sentence it lists in plain words, keeping the meaning, the facts,
the citations and the word counts, and run it again until it lists nothing. Then reread the
margin notes and the motivation line aloud in your head: if a line sounds like an advertisement
or a slogan, rewrite it as a teacher would say it. Print one line in your log, "Voice check:
N sentences rewritten, 0 remaining", and never put that line in the brief itself.
