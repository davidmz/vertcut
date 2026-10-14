# Interface fonts — where they come from and why they're kept SEPARATE

These are the fonts Vertcut's **screen** is set in. The fonts used to
draw **subtitles in clips** live one level up, in `assets/fonts/`, and
those are two different jobs.

**Kept apart on purpose.** The `assets/fonts/` folder is the set people
choose their clip's look from (`vertcut fonts`, `--font`). Put an
interface font there and it would show up in that choice — and nobody
wants a monospace font in subtitles. The reverse is just as wrong: when
someone changes the subtitle font, the screen mustn't change by a
single pixel.

| file | family | where on screen |
|---|---|---|
| `JetBrainsMono.ttf` | JetBrains Mono | all numbers: timecodes, durations, sizes, keys |
| `LiterataItalic.ttf` | Literata Italic | italics in headings and the step numbers |

**The italic came as a separate file because otherwise there would be
none.** The `Literata.ttf` that ships with Vertcut is variable along two
axes — optical size and weight — but it has no slant: for this family
the italic lives in its own file. Without it the browser slants the
upright letters itself, and on a serif font that shows right away: you
get not an italic but a font leaning over. And the italic here isn't
decoration — the design uses it to carry meaning in the second half of
headings, and it appears on every screen, in the step numbers.

From Google Fonts (`github.com/google/fonts`, `main` branch, downloaded
on 2 September 2026), **SIL Open Font License 1.1** — the text is in
a file next to it. A variable font with one `wght` axis: one file
instead of two.

**The other two screen fonts already ship with Vertcut** and are taken
from `assets/fonts/` — Golos Text (interface) and Literata (headings).
There's no second copy on disk: the screen serves the very same files.
The design asks to load all three from Google Fonts; here they're served
from your own disk, because Vertcut has to work without the internet.

## What these three fonts don't have

Checked by reading each font's character table (`vertcut/fonts.py`)
against every character used in the design:

| character | Golos Text | Literata | JetBrains Mono |
|---|---|---|---|
| `✓` check mark | no | no | no |
| `⇧` Shift key | no | no | yes |
| `⌘` Cmd key | no | no | yes |

The browser would substitute a character from a system font — so on
someone else's computer the check mark would look foreign, and on a bare
one it might not show at all. So on screen:

- **the check mark is drawn with lines** (svg), not typed as a character;
- **keys are named in words** — "Shift", not `⇧`.
