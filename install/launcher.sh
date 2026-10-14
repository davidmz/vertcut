#!/bin/bash
# What runs when you double-click the Vertcut icon. macOS and Linux.
#
# WHAT IT DOES. Checks whether Vertcut is installed; if not, installs
# it, showing progress as a page in your browser. Then starts Vertcut
# and opens a tab. That's all. There's no logic here and there shouldn't
# be: it lives in Python, and the terminal command uses the same code.
#
# WHAT IT TOUCHES. Three folders, listed below. Everything it says goes
# into a log file in the settings folder, so there's something to read
# and send if it fails.
#
# WHY NOT exec. It's tempting: one line, one process, and closing the
# launcher stops Vertcut by itself. But then the launcher wouldn't see
# Vertcut crash on startup — exactly the kind of failure that happens
# before Vertcut's screen exists, so it's the launcher that has to
# report it. That's why Vertcut runs as a child process and watches for
# the launcher going away itself: `--exit-with-icon`.
#
# VARIABLE NAMES ARE PLAIN LATIN. The bash 3.2 that ships with macOS
# doesn't understand non-Latin variable names and fails on the first line.

set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The installer sits in its own folder next to this file. Inside the Mac
# app it's a link to Resources — that's where macOS wants such files,
# and the link connects the two.
KIT="$HERE/install"

# ── three places, each for its own reason ────────────────────────────
#
#   program   — what was downloaded and installed. Delete the folder
#               and Vertcut is gone, nothing else;
#   settings  — your AI key, spending log, your own subtitle style.
#               They survive a reinstall;
#   your work — analyzed videos and exported clips. Nothing ever
#               touches them (they're in ~/vertcut, not used here).
case "$(uname -s)" in
  Darwin) PROGRAM="$HOME/Library/Application Support/vertcut" ;;
  *)      PROGRAM="${XDG_DATA_HOME:-$HOME/.local/share}/vertcut" ;;
esac
SETTINGS="${VERTCUT_HOME:+$VERTCUT_HOME/.settings}"
SETTINGS="${SETTINGS:-$HOME/.vertcut}"
LOGS="$SETTINGS/logs"
SHOW="$SETTINGS/install"
PY="$PROGRAM/python/bin/python3"

mkdir -p "$LOGS" "$SHOW"
LOG="$LOGS/launch-$(date +%Y-%m-%d-%H%M%S).log"

# Everything Vertcut says goes to a file: there's no terminal, and after
# a crash there must be something to read and to send.
exec >>"$LOG" 2>&1
echo "── launch $(date '+%Y-%m-%d %H:%M:%S') ──"

# `open` on macOS, `xdg-open` on Linux. They can't be chained with `&&`:
# `open` returns non-zero when the file is missing, and then xdg-open
# would run next — and macOS doesn't have it at all.
open_page() {
  if command -v open >/dev/null 2>&1; then
    open "$1"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$1"
  else
    echo "no way to open a browser: $1"
  fi
}

# ── PATH: a double-click gets a different one ────────────────────────
#
# **A program started from an icon doesn't live in the same world as
# a command typed in a terminal.**
#
# macOS gives it a short PATH: `/usr/bin:/bin:/usr/sbin:/sbin`. Neither
# `/opt/homebrew/bin` nor `/usr/local/bin` is in it — so an ffmpeg you
# installed with Homebrew would be invisible, and Vertcut would say
# "no ffmpeg". True about its own PATH, untrue about your computer.
#
# So we take the PATH of your LOGIN SHELL — the same one you see in the
# terminal. Not a hand-written list of folders: one person has Homebrew,
# another MacPorts, a third their own build in the home folder, and
# a three-line list would one day miss all three.
# The shell gets no input (`</dev/null`): it has nothing to read, and if
# someone's shell profile asks a question, it won't hang waiting for an
# answer and take the whole launch with it.
LOGIN_PATH="$(/bin/zsh -lc 'printf %s "$PATH"' </dev/null 2>/dev/null || true)"
if [ -z "$LOGIN_PATH" ]; then
  LOGIN_PATH="$(/bin/bash -lc 'printf %s "$PATH"' </dev/null 2>/dev/null || true)"
fi
# Does it look like a real PATH? The shell could have printed anything
# into it — a greeting, a complaint, nothing — and using that as PATH
# would leave us with no PATH at all. Two checks: a line break means
# something else was printed before the paths, and every real PATH
# contains `/usr/bin`.
case "$LOGIN_PATH" in
  *"
"*) LOGIN_PATH="" ;;
esac
case ":$LOGIN_PATH:" in
  *":/usr/bin:"*) PATH="$LOGIN_PATH" ;;
esac
export PATH

# **This comes BEFORE the install, on purpose.** The installer downloads
# its own ffmpeg only when it can't find one on the system, and with the
# short double-click PATH it never would — so everyone who already has
# ffmpeg would download an extra 80 MB and get a second copy.

# ── not installed yet ────────────────────────────────────────────────
FRESH=""
if [ ! -f "$PROGRAM/version.json" ]; then
  echo "not installed yet — installing"
  FRESH="yes"
  WHEEL="$(ls "$HERE"/*.whl 2>/dev/null | head -1)"
  if [ -z "$WHEEL" ]; then
    echo "no Vertcut package (.whl) next to the launcher"
    exit 1
  fi
  # The page is opened BEFORE the work starts: it's already written and
  # already says how much will be downloaded. Staying silent here isn't
  # an option — the person just clicked and is waiting.
  # The fifth argument is the icon itself: the installer puts a copy of it
  # on your Desktop so you don't have to look for it later. Inside the
  # Mac app this file lives in Contents/MacOS, and the icon is the folder
  # two levels up.
  ICON="$HERE"
  case "$HERE" in
    */Vertcut.app/Contents/MacOS) ICON="$(cd "$HERE/../.." && pwd)" ;;
  esac
  bash "$KIT/install.sh" "$PROGRAM.new" "$PROGRAM" "$WHEEL" "$SHOW" \
       "$ICON" &
  INSTALL=$!
  sleep 1
  open_page "$SHOW/progress.html"
  wait $INSTALL || { echo "installation failed"; exit 1; }
fi

# ── start Vertcut ────────────────────────────────────────────────────
if [ ! -x "$PY" ]; then
  echo "no Python at $PY"
  exit 1
fi

# The ARCHITECTURE is picked by the system too, and for an icon it can
# be picked differently.
#
# Python from python.org is a universal program (Intel and Apple Silicon
# in one file), but the libraries are built for ONE architecture. A
# double-click used to start such a Python as Intel, under Rosetta — and
# the Apple Silicon builds of numpy, onnxruntime and ctranslate2 wouldn't
# load into it at all: "incompatible architecture (have 'arm64', need
# 'x86_64')". Vertcut then said "libraries missing" to someone who had
# them installed and working.
#
# Checked not by a system flag but by an ATTEMPT: does the lowest of the
# compiled libraries (numpy — the other three sit on top of it) load as
# arm64? If yes, the environment is arm64 and Python runs that way. If
# not (an Intel Mac, an Intel environment), we run it as is, and if the
# libraries don't load, Vertcut says so in words instead of "reinstall".
ARCH=""
if [ "$(uname -s)" = "Darwin" ] \
   && /usr/bin/arch -arm64 "$PY" -c "import numpy" >/dev/null 2>&1; then
  ARCH="/usr/bin/arch -arm64"
fi

# Just installed — then Vertcut does NOT open a tab.
#
# The person is already looking at the progress page. Opening a second
# tab would leave them with two: the one they were watching and a new
# one on top. Instead we send the tab they're looking at to Vertcut
# ourselves — below.
#
# A normal launch is the other way round: there's no progress page, so
# Vertcut opens the tab itself.
if [ -n "$FRESH" ]; then
  $ARCH "$PY" -m vertcut screen --exit-with-icon --no-browser &
else
  $ARCH "$PY" -m vertcut screen --exit-with-icon &
fi
SERVER=$!

# If it dies in the first seconds, Vertcut's screen never appeared, and
# the launcher has to say so. Later than that is Vertcut's normal life,
# and its own screen does the talking.
sleep 3
if ! kill -0 $SERVER 2>/dev/null; then
  wait $SERVER
  CODE=$?
  # Zero is NOT a crash, and telling the two apart matters.
  #
  # Vertcut was already running: the second copy found the first one,
  # opened its tab and exited cleanly. Without this check, clicking the
  # icon a second time gave two tabs at once — the running Vertcut and
  # a "Vertcut didn't start" page on top of it.
  if [ "$CODE" -eq 0 ]; then
    echo "Vertcut was already running — it opened its own tab; exiting"
    exit 0
  fi
  echo "Vertcut didn't start, exit code $CODE"
  # If we just installed, the person is looking at the progress page,
  # and the problem is shown THERE. Zero means "the page got it";
  # otherwise we open the file in a new tab.
  if ! "$PY" "$KIT/progress.py" --page-dir "$SHOW" \
    --title "Vertcut didn't start" \
    --hint "Below are the last lines of the log. The whole log is here: $LOG" \
    --log-tail "$LOG"; then
    open_page "$SHOW/progress.html"
  fi
  exit $CODE
fi

# Just installed — so the person is looking at the progress page. We send
# it on to Vertcut: two tabs, one of them dead, is a poor ending for a
# good install.
if [ -n "$FRESH" ]; then
  URL="$("$PY" -m vertcut screen --print-address 2>/dev/null || true)"
  if [ -n "$URL" ]; then
    # In the background and for a long time: a background tab asks rarely
    # — the browser saves effort — and it still has to be sent on when the
    # person comes back to it ten minutes later. Vertcut shouldn't wait
    # for that.
    "$PY" "$KIT/progress.py" --page-dir "$SHOW" --go-to "$URL" \
      --wait 900 &
  fi
fi

wait $SERVER
echo "── Vertcut stopped $(date '+%Y-%m-%d %H:%M:%S') ──"
