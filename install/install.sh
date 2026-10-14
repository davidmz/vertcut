#!/bin/bash
# First launch on macOS and Linux: get Python, then hand over to it.
#
# WHAT IT DOES TO YOUR COMPUTER. It downloads a self-contained Python
# (about 25 MB) into Vertcut's own folder, checks its checksum and
# unpacks it there. Nothing is installed into the system, nothing needs
# an administrator password.
#
# WHY THIS IS A SHELL SCRIPT AND NOT PYTHON. On a clean machine there's
# no Python at all, so this part can't be written in Python. That's why
# this file has exactly one job — get Python — and everything else is
# done by `installer.py`, shared by macOS and Windows. The less there is
# in this file, the less has to be written twice.
#
# WHY NOT /usr/bin/python3. macOS has one, but it isn't Python — it's a
# placeholder: the first time it runs, it opens a window asking you to
# install the developer tools, and waits. That's exactly the
# conversation with the system this installer avoids.
#
# THE PYTHON ADDRESS AND CHECKSUM ARE NOT WRITTEN HERE. They're in
# `sources.txt` together with the reasons; the Python half reads them
# from there too. A number written in two places will one day drift
# apart, quietly.

set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCES="$HERE/sources.txt"

STAGE="${1:?stage folder}"     # folder where everything is put together
TARGET="${2:?target folder}"   # where to move it once it is ready
WHEEL="${3:?Vertcut package}"  # the Vertcut package file (.whl)
SHOW="${4:?page folder}"       # where to write the progress page
ICON="${5:-}"                  # what to put on the Desktop

# ── which system and which hardware ──────────────────────────────────
which_os() {
  case "$(uname -s)" in
    Darwin) echo darwin ;;
    Linux)  echo linux ;;
    *)      echo unknown ;;
  esac
}
# The architecture of the MACHINE, not of this process.
#
# `uname -m` answers about the process, and under Rosetta it honestly
# says "x86_64" on an Apple Silicon (arm64) Mac. A program started with
# a double-click can end up running under Rosetta — both Vertcut and its
# icon have been caught by this. The installer would then download Intel
# Python and Intel libraries onto an Apple Silicon Mac: they'd work, but
# through translation and slower, and speech recognition is the slowest
# thing Vertcut does as it is.
#
# What's asked is not a flag but an ATTEMPT: `arch -arm64` runs
# something tiny. If it exits with zero, the machine can run arm64,
# whatever we ourselves happen to be running as.
which_arch() {
  if [ "$(uname -s)" = "Darwin" ] \
     && /usr/bin/arch -arm64 /usr/bin/true >/dev/null 2>&1; then
    echo arm64
    return
  fi
  case "$(uname -m)" in
    arm64|aarch64) echo arm64 ;;
    x86_64|amd64)  echo x86_64 ;;
    *)             echo unknown ;;
  esac
}
OS="$(which_os)"
ARCH="$(which_arch)"

# ── how to tell the person something went wrong ──────────────────────
#
# Vertcut's screen doesn't exist yet, and the person has no terminal
# open either. That leaves the page: the same one that shows progress,
# written by hand here — at this step there may be no Python at all,
# so there's nothing to run `progress.py` with.
fail() {
  mkdir -p "$SHOW"
  {
    printf '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    printf '<title>Vertcut didn'"'"'t install</title>'
    printf '<style>body{margin:0;background:#FBFBFA;color:#191919;'
    printf 'font:15px/1.5 -apple-system,system-ui,sans-serif;padding:40px 24px}'
    printf '@media(prefers-color-scheme:dark){body{background:#1A1A18;color:#F0EFEC}}'
    printf '.page{max-width:560px;margin:0 auto}h1{font-size:24px;color:#B3261E;'
    printf 'margin:0 0 8px}p{margin:0 0 12px}code{font:13px ui-monospace,Menlo,monospace;'
    printf 'color:#6B6B6B}</style></head><body><div class="page">'
    printf '<h1>Vertcut didn'"'"'t install</h1><p>%s</p><p><code>%s</code></p>' "$1" "$2"
    printf '</div></body></html>'
  } > "$SHOW/progress.html"
  echo "installation stopped: $1" >&2
  exit 1
}

if [ ! -f "$SOURCES" ]; then
  fail "Couldn't find the list of what to download." "missing file $SOURCES"
fi

# ── the Python address and checksum: from the shared list ────────────
ROW="$(awk -v os="$OS" -v arch="$ARCH" \
  '$1=="python" && $2==os && $3==arch {print $4" "$5; exit}' "$SOURCES")"
# Not "install Python yourself and Vertcut will work": the launcher only
# uses its own Python. Installing from the source code is the real way out.
if [ -z "$ROW" ]; then
  fail "There's no ready-made Python for this system ($OS/$ARCH), so Vertcut
can't install itself here. You can still install it from the source code —
see the README on GitHub." \
       "no \"python ${OS} ${ARCH}\" row in sources.txt"
fi
URL="${ROW%% *}"
WANT="${ROW##* }"

# ── start from scratch, not on top ───────────────────────────────────
#
# An unfinished folder left from last time is thrown away entirely.
# Building on top of leftovers gives an install nobody can say for sure
# what it's made of.
rm -rf "$STAGE"
mkdir -p "$STAGE" "$SHOW" || fail "Couldn't create the install folder." "$STAGE"

# The first page comes BEFORE the first download: the person is already
# waiting, and staying silent during that minute isn't an option.
{
  printf '<!doctype html><html lang="en"><head><meta charset="utf-8">'
  printf '<meta http-equiv="refresh" content="2">'
  printf '<title>Installing Vertcut</title>'
  printf '<style>body{margin:0;background:#FBFBFA;color:#191919;'
  printf 'font:15px/1.5 -apple-system,system-ui,sans-serif;padding:40px 24px}'
  printf '@media(prefers-color-scheme:dark){body{background:#1A1A18;color:#F0EFEC}}'
  printf '.page{max-width:560px;margin:0 auto}h1{font-size:24px;margin:0 0 8px}'
  printf 'p{margin:0 0 8px;color:#6B6B6B}</style></head><body><div class="page">'
  printf '<h1>Installing Vertcut</h1>'
  printf '<p>This happens only once and needs the internet — about 800 MB.</p>'
  printf '<p>After that, Vertcut works offline.</p>'
  printf '<p>Now: downloading Python, 25 MB.</p>'
  printf '</div></body></html>'
} > "$SHOW/progress.html"

# ── download Python ──────────────────────────────────────────────────
ARCHIVE="$STAGE/python.tar.gz"
# If the server ANSWERED with an error (4xx, 5xx), the internet works but
# the file isn't there. "Wait for the internet" would be untrue then, and
# would keep the person waiting forever.
# We look at the HTTP status, not at curl's exit code: the curl in
# macOS 26 (8.7.1) returns 56 on a 404 instead of the documented 22.
# No connection at all gives status 000.
HTTP_CODE="$(curl -fsSL --connect-timeout 30 --retry 3 -o "$ARCHIVE" \
  -w '%{http_code}' "$URL")"
CURL_CODE=$?
if [ "$CURL_CODE" -ne 0 ] && [ "${HTTP_CODE:-000}" != "000" ]; then
  fail "The internet works, but the server didn't give us Python — it may be
down for a while, or the file has moved. Nothing is broken: try again later,
or get a newer Vertcut." "$URL"
elif [ "$CURL_CODE" -ne 0 ]; then
  fail "Couldn't download Python — looks like there's no internet connection.
Nothing is broken: open Vertcut again when you're back online." \
       "$URL"
fi

# ── check the checksum ───────────────────────────────────────────────
#
# What arrives here will be run. "Downloaded and ran it" without
# checking means taking someone else's server at its word.
if command -v shasum >/dev/null 2>&1; then
  GOT="$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')"
elif command -v sha256sum >/dev/null 2>&1; then
  GOT="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
else
  GOT="nothing-to-check-with"
fi
if [ "$GOT" != "nothing-to-check-with" ] && [ "$GOT" != "$WANT" ]; then
  rm -rf "$STAGE"
  fail "The downloaded Python isn't the file we expected, so the installer
stopped and installed nothing. Maybe it's an update, maybe it was tampered
with — there's no way to tell which." "expected $WANT, got $GOT"
fi

# ── unpack ───────────────────────────────────────────────────────────
if ! tar -xzf "$ARCHIVE" -C "$STAGE"; then
  rm -rf "$STAGE"
  fail "The downloaded Python couldn't be unpacked." "$ARCHIVE"
fi
rm -f "$ARCHIVE"

PY="$STAGE/python/bin/python3"
[ -x "$PY" ] || fail "The downloaded Python archive has no Python inside." "$PY"

# ── the Python half does the rest ────────────────────────────────────
ICON_ARG=""
[ -n "$ICON" ] && ICON_ARG="--icon"
exec "$STAGE/python/bin/python3" "$HERE/installer.py" \
  --stage "$STAGE" --target "$TARGET" --wheel "$WHEEL" --page-dir "$SHOW" \
  ${ICON_ARG:+"$ICON_ARG" "$ICON"}
