# What Vertcut is made of, and under which licenses

Vertcut itself is under the MIT license — the text is in the `LICENSE`
file. It allows everything and asks for nothing in return.

Below is everything that isn't ours: what comes with Vertcut, what it
downloads to your computer on first launch, and the license of each.

**Checked on September 3, 2026, and again on October 9 and October 11, 2026**, and not
from memory: the licenses were read from the files each library puts
next to itself when it is installed. An automatic check fails if a
copyleft license shows up among them. It reads only those files, not
the binaries a library carries inside — that is how the GPL encoders
inside `av` went unnoticed until a person looked.

**There are no copyleft licenses (GPL, LGPL, AGPL) in what we hand out**
— the download itself: our code, the fonts and the face detector
weights. This is not a reassuring footnote: the face detector was
replaced early on precisely because the old one was built on a library
under AGPL, and that license would most likely have required releasing
everything else under it too.

**What gets installed on your computer is a different matter.** ffmpeg
is under GPL, and so are parts of the copy of ffmpeg's libraries that
the `av` library brings along (see below). We don't hand either of them
out — they come from their own sites — but they are on your computer,
and it would be wrong to say there is no GPL there.

---

## Comes with Vertcut

### Subtitle fonts — SIL Open Font License 1.1

Each font has its license text in a file next to it.

| font | what it is |
|---|---|
| Inter Tight | neutral sans-serif |
| Golos Text | sans-serif with character |
| Oswald | condensed |
| Literata | serif (plus a separate italic) |

The SIL OFL allows using, changing and sharing the fonts; it forbids
selling a font on its own and requires a changed font to have a
different name. We don't change them.

### Fonts of the Vertcut window — SIL Open Font License 1.1

JetBrains Mono and Literata Italic. They are kept apart from the
subtitle fonts on purpose: you choose subtitle fonts for your clips,
and a monospaced interface font has no place among them.

### Face detector weights — MIT

`yunet.onnx`, 230 KB, with its license text in a file next to it
(`yunet-LICENSE.txt`).

### Colors and interface parts

`tokens.css` and `components.css` are copied byte for byte from this
project's own design package. They are ours, not someone else's.

---

## Libraries installed on first launch

`pip` installs them from the regular Python package index. We don't
hand them out: each one arrives on your computer by itself, with its
license inside.

**Six are direct dependencies**; the rest come along with them. The
exact version of each is in `constraints.txt` — it is what gets
installed.

| library | license | why it's there |
|---|---|---|
| faster-whisper | MIT | direct: speech recognition |
| av | BSD, **but brings its own ffmpeg** — see below | direct (for its version limit): reads the sound for speech recognition |
| numpy | BSD (plus Apache-2.0 and MIT in bundled parts) | direct: math |
| onnxruntime | MIT | direct: face detector engine |
| pillow | MIT-CMU (plus FreeType — see below) | direct: drawing subtitles |
| PyYAML | MIT | direct: subtitle styles |
| ctranslate2 | MIT | with speech recognition |
| tokenizers | Apache-2.0 | with speech recognition |
| huggingface-hub | Apache-2.0 | with speech recognition |
| hf-xet | Apache-2.0 | with huggingface-hub |
| filelock | MIT | with huggingface-hub |
| fsspec | BSD | with huggingface-hub |
| click | BSD | with huggingface-hub |
| packaging | Apache-2.0 or BSD | with huggingface-hub |
| httpx2, httpcore2, h11 | BSD / BSD / MIT | with huggingface-hub |
| truststore | MIT | with httpx2 |
| anyio | MIT | with httpx2 |
| idna | BSD | with httpx2 |
| tqdm | **MPL-2.0** and MIT | with speech recognition |
| flatbuffers | Apache-2.0 | with onnxruntime |
| protobuf | BSD | with onnxruntime |
| typing-extensions | PSF | with many |
| colorama | BSD | Windows only: with click and tqdm |
| coloredlogs, humanfriendly | MIT / MIT | Intel Macs only: with the older onnxruntime they get |
| sympy, mpmath | BSD / BSD | Intel Macs only: with the older onnxruntime they get |

**About the MPL-2.0 one.** This license is weak copyleft and works
file by file: it requires sharing changes made TO THOSE FILES, not to
the program that uses them. We don't change them and we don't hand them
out, so it puts no obligations on us. It is named separately because
weak copyleft is still copyleft, and it's worth knowing about.

**About `av`.** The library itself is under BSD, but the ready-made
build that `pip` installs carries its own copy of ffmpeg's libraries
inside (`libavcodec`, `libavformat` and others, which are LGPL), and
with them the **x264 and x265 encoders, which are GPL**. Vertcut uses
`av` only through speech recognition, to read the audio; it never
encodes video with it. We don't hand `av` out either — `pip` installs
it from the package index — so this puts no obligations on us. It is
written here because "no GPL on your computer" would not be true.

**About FreeType in pillow.** On Windows, pillow brings the FreeType
font engine with it. FreeType is offered under a choice of two
licenses — its own FreeType License (FTL, permissive) or GPLv2 — and we
use it under the FTL. That's why the GPLv2 text shows up next to pillow
on Windows.

**Three of them ship without a license file** — ctranslate2,
tokenizers, flatbuffers. Their license is declared in the package
description (MIT, Apache-2.0, Apache-2.0). That's their oversight, not
our choice, and it's written down here so it doesn't look like ours.
(onnxruntime used to be the fourth; it now ships `LICENSE` and
`ThirdPartyNotices.txt` inside the package.)

---

## ffmpeg — GPL, and we do NOT hand it out

Nothing works without ffmpeg: it extracts the audio, cuts the picture
and exports the clip.

**Builds that can encode video are under GPL** — they include the x264
encoder, which is GPL.

**We don't hand it out.** There is no ffmpeg inside the download. On
first launch Vertcut checks whether ffmpeg is already on your system,
and only if it isn't, downloads it **to your computer** from the site of
whoever builds it. A file called `ORIGIN.md` is put next to it: where
it came from and under which license.

Vertcut runs ffmpeg as a separate program and never builds it in, so
ffmpeg's GPL would not extend to Vertcut's own code even if ffmpeg came
inside the download. What handing it out WOULD bring is the duty that
comes with every GPL binary: put the license next to it and provide the
exact source code of that very build, for each system we ship — and
keep doing so for every update. Not handing it out avoids that, keeps
the download small, and doesn't put a second copy on computers that
already have ffmpeg.

The addresses and checksums are in `install/sources.txt`.

- macOS (Apple Silicon and Intel): https://www.osxexperts.net/
- Windows: https://github.com/GyanD/codexffmpeg

---

## Speech recognition model — MIT

Downloaded on first launch, about 486 MB, into the shared model cache
on your computer. We don't hand it out.

It's Whisper by OpenAI (MIT), converted for the ctranslate2 engine
(also MIT) and published on Hugging Face as
`Systran/faster-whisper-small`.

---

## Python — PSF License

Also downloaded on first launch, if your computer doesn't have the
right version. The build is from `astral-sh/python-build-standalone`;
the license text is inside the unpacked folder.

The PSF license allows everything MIT does.

---

## What isn't here, and why

**No opencv and no ultralytics.** Both were removed: ultralytics, under
AGPL, was replaced as the face detector; opencv was replaced in the
shot-change detection.
