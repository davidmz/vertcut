# Contributing

Thanks for wanting to help. Bug reports and ideas go to
[Issues](https://github.com/eduard1414ed/vertcut/issues). For code,
read this first.

## The development docs are in Russian

Vertcut's code, comments and development docs (`CLAUDE.md`,
`docs/decisions.md`, `TODO.md`) are written in Russian. Everything a
user sees — the screen, messages, the command line, these public docs —
is in English, and a test keeps it that way. `docs/glossary.md` lists
the English word for each thing on screen. If you write text a user
will see, take the words from there.

If you don't read Russian, an AI agent can read the docs for you:
[CLAUDE.md](CLAUDE.md) is written to be read by one.

## Set up from source

Same as [installing in a terminal](README.md#2-install-it-yourself-in-a-terminal),
but editable and with the test tools:

```
git clone https://github.com/eduard1414ed/vertcut.git
cd vertcut
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]" -c constraints.txt
.venv/bin/vertcut check
```

You need git, Python 3.11–3.14 and ffmpeg on PATH. On macOS,
`python install/build-dev-launcher.py` puts a "Vertcut (dev)" icon on
your Desktop that runs this working copy.

Don't clone into `~/vertcut`: that's where Vertcut keeps its videos and
clips.

## Run the checks

```
.venv/bin/python -m pytest -q
```

The tests never touch your real `~/vertcut` or `~/.vertcut`: each one
gets its own temporary folder through `VERTCUT_HOME`. Use the same
variable when you try things by hand:

```
VERTCUT_HOME=/tmp/vertcut-try .venv/bin/vertcut screen
```

Green tests don't prove that ffmpeg is happy with a real video. If you
changed analysis or export, run it on a real video too.

Before a release there's a sweep that runs Vertcut the way a person
does — the command line, the screen in a headless Chrome, the files it
writes, the installers — and looks for any Russian that reached the
user:

```
.venv/bin/python tools/cyrillic-sweep.py
```

It needs macOS (it makes its test video with `say`), Google Chrome and
ffmpeg, takes 5–10 minutes and must end with zero findings.

## Library versions

`constraints.txt` holds the exact version of every library Vertcut
installs, including the ones other libraries pull in; the installer,
the README commands and the build machines all install from it, so a
new release of anything reaches people only after it's checked here.
To update it, run `.venv/bin/python tools/pins.py --newest` to see
what's newer, change the numbers in the file (a library that wasn't
there before needs its own line, and `LICENSES.md` a row), and run
`.venv/bin/python tools/pins.py`: it checks that every system and
every Python from 3.11 to 3.14 gets ready-made packages and that
nothing unpinned slips in. Then reinstall your `.venv` with
`-c constraints.txt`, run the tests and a real analysis and export, and
push — the Windows and Linux build machines install from the file and
compare what they got with `tools/pins.py --installed`. The weekly
**Newest libraries** check (`.github/workflows/newest.yml`) installs
the newest versions without the file and runs a real analysis and
export on macOS, Windows and Linux; update the file when it's green,
not when it's red.

## If you publish your own build

Please point people at your own repository, so that reports about your
version don't land here. The address of this repository is written in:

- `vertcut/assets/web/js/screens/help.js` — where the **Not working?**
  page sends people;
- `install/build-release.py` — the link in the installer's
  `README.html`;
- `tools/doc-commands.py` — the clone address that the build machines
  replace;
- `README.md`, `INSTALL.md`, `SECURITY.md` and
  `.github/ISSUE_TEMPLATE/`.

`grep -rn eduard1414ed .` finds all of them.

## Releases

The version lives in one place: `version` in `pyproject.toml`. Pushing
a tag `v<version>` makes the build machines build both installers,
check them by unzipping, and put them with `SHA256SUMS.txt` into a
**draft** release (`.github/workflows/release.yml`). The Windows
installer is then downloaded from that draft and installed on a clean
Windows. Nothing is published automatically: a person checks the draft
and presses Publish. The release text is `.github/release-notes.md`.

## Pull requests

Small and focused is best: one change, with a test that would have
caught the problem. Say what you checked by hand. The Windows and Linux
build machines run on every pull request.
