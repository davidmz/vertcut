# Where the subtitle fonts come from, and why these

All four come from Google Fonts (`github.com/google/fonts`), all under
the **SIL Open Font License 1.1**. It allows shipping a font as part of
anything, paid software included, on one condition: the license text
travels with the font. It's in a file next to each one.

These are **variable** fonts (one `wght` axis): one file per family
instead of eight, and the weight is set by a number in the subtitle
style.

| file | family | why it's in the set |
|---|---|---|
| `InterTight.ttf` | Inter Tight | neutral sans-serif; the default |
| `GolosText.ttf` | Golos Text | sans-serif, designed for Cyrillic, a little warmer |
| `Oswald.ttf` | Oswald | condensed: noticeably more fits on a line |
| `Literata.ttf` | Literata | serif — a completely different voice |

**The set is deliberately varied, not five shades of one font.**
People need a real choice, not the look of one: four sans-serifs
would leave nothing to choose between and only make the download
bigger.

**Why not more.** Every font is another megabyte to ship and another
license to keep track of. You can add your own font as a file — that
road has no limit; the built-in set is there so Vertcut works right
away.

**What's not in the set and why:** Montserrat (727 KB) and Rubik
(351 KB) were downloaded and considered — both free and both with
Cyrillic, but both sans-serifs, and next to Inter Tight and Golos Text
they'd add size, not choice.

Downloaded on 1 September 2026, `main` branch.
