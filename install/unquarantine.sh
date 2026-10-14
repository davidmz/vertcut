#!/bin/bash
# The backup way, for when macOS won't let you open Vertcut.
#
# WHAT IT DOES. It removes the "downloaded from the internet" mark from
# Vertcut — the very mark that makes macOS ask for permission. Nothing
# else: it installs nothing, goes nowhere, needs no internet. After it,
# Vertcut opens with a double-click, like any app of your own.
#
# WHY IT WORKS AT ALL. macOS checks what is opened with a DOUBLE-CLICK
# in Finder. What you start yourself from Terminal isn't checked.
#
# WHY IT CAN'T BE ONE MORE ICON. A file that "types into Terminal and
# does everything by itself" would have to be opened with a double-click
# — and it would be checked before it could take its first step. You
# start this file yourself, and that is the only reason it works.
#
# WHY IT DOESN'T INSTALL ANYTHING. Installing has a way of its own: you
# watch its progress on a page in the browser, and at the end an icon
# appears on your Desktop. This file only removes what stands in the way.
#
# (For whoever edits this file: variable names stay in plain Latin —
# the bash 3.2 that comes with macOS stops at the first non-Latin name.
# This file sits on top of the archive, next to README.html, and people
# open it to see what it does before running it: every word in it,
# comments included, is in English. There is a test for that.)

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/Vertcut.app"

if [ ! -d "$APP" ]; then
  echo "There's no Vertcut next to this file."
  echo "This file has to be in the same folder as the Vertcut app —"
  echo "put it back there and run it again."
  exit 1
fi

xattr -dr com.apple.quarantine "$APP" 2>/dev/null

# Check instead of hoping: without write access `xattr` says nothing,
# and you would be left with the same refusal.
LEFT="$(xattr -pr com.apple.quarantine "$APP" 2>/dev/null | head -1)"
if [ -n "$LEFT" ]; then
  echo "Couldn't remove the \"downloaded from the internet\" mark."
  echo "Most likely the folder is somewhere you can't change files."
  echo "Move the whole folder to Downloads, for example, and run this again."
  exit 1
fi

echo "Done."
echo "Close this window and open Vertcut with a double-click, as usual."
