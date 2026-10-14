# First launch on Windows: get Python, then hand over to it.
#
# WHAT IT DOES TO YOUR COMPUTER. It downloads a self-contained Python
# (about 25 MB) into Vertcut's own folder in %LOCALAPPDATA%, checks its
# checksum and unpacks it there. Nothing goes into the registry or the
# system, and no administrator rights are needed.
#
# THE SAME AS `install.sh`, WITHIN EXACTLY THE SAME LIMITS. This file has
# one job — get Python; everything else is done by `installer.py`, shared
# by both systems. The less there is in this file, the less is written
# twice and one day drifts apart.
#
# WHY POWERSHELL. Every Windows since 7 has it, there's nothing to
# install, and it can download, compute a checksum and unpack — all
# that's needed before Python exists.
#
# HOW WELL IT'S TESTED. A build machine runs it on a clean Windows on
# every change: unzips the archive, starts Vertcut.exe, waits for the
# install and for Vertcut to answer. It has not been watched on a real
# person's computer yet.

param(
    [Parameter(Mandatory=$true)][string]$Stage,   # where everything is put together
    [Parameter(Mandatory=$true)][string]$Target,  # where to move it when ready
    [Parameter(Mandatory=$true)][string]$Wheel,   # the Vertcut package (.whl)
    [Parameter(Mandatory=$true)][string]$Show,    # where to write the progress page
    [string]$Icon = ''                            # what to put on the Desktop
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

# SO THAT EVERY LETTER REACHES THE LOG INTACT. The launcher captures this
# output and writes it to a file, and PowerShell writes it in the
# console's encoding — which can't hold many letters (a non-English
# folder name, say), so the log would get question marks instead. The
# same issue Python has (`vertcut/report.py`), from the other side.
# Without this, the reason for a failure reached the log but couldn't be
# read.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
$Sources = Join-Path $Here 'sources.txt'

# ── how to tell the person something went wrong ──────────────────────
#
# Vertcut's screen doesn't exist yet, and there's no terminal either.
# That leaves the page — the same one that shows progress. There may be
# no Python at this step, so the page is written by hand here.
function Say-Problem($What, $Details) {
    # To the log FIRST, before any markup. The person might not see the
    # page (there may be no browser), but the log always stays and can be
    # sent as a whole.
    [Console]::Error.WriteLine("installation stopped: $What")
    [Console]::Error.WriteLine($Details)

    New-Item -ItemType Directory -Force -Path $Show | Out-Null
    # **Our own replacement of three characters, not `System.Web`.** That
    # assembly doesn't load by itself, and calling it CRASHES the function
    # that reports problems — the very problem it exists to report. The
    # build machine caught this: the install stopped, the log said
    # "installation failed", and nobody said why.
    # The details get escaped too: they can contain an error's stack trace.
    $w = ("$What" -replace '&', '&amp;' -replace '<', '&lt;' `
                  -replace '>', '&gt;')
    $d = ("$Details" -replace '&', '&amp;' -replace '<', '&lt;' `
                     -replace '>', '&gt;')
    $html = @"
<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Vertcut didn't install</title>
<style>body{margin:0;background:#FBFBFA;color:#191919;
font:15px/1.5 -apple-system,"Segoe UI",system-ui,sans-serif;padding:40px 24px}
@media(prefers-color-scheme:dark){body{background:#1A1A18;color:#F0EFEC}}
.page{max-width:560px;margin:0 auto}h1{font-size:24px;color:#B3261E;margin:0 0 8px}
p{margin:0 0 12px}code{font:13px Consolas,monospace;color:#6B6B6B}</style>
</head><body><div class="page"><h1>Vertcut didn't install</h1>
<p>$w</p><p><code>$d</code></p></div></body></html>
"@
    [System.IO.File]::WriteAllText((Join-Path $Show 'progress.html'), $html,
                                   [System.Text.Encoding]::UTF8)
    exit 1
}

# A CATCH-ALL FOR EVERYTHING ELSE. `$ErrorActionPreference = 'Stop'` stops
# the work on any unexpected error — and without this trap the error goes
# nowhere: the launcher only sees an exit code. A failure without a reason
# is a failure people can only fix by guessing.
trap {
    Say-Problem 'The installer ran into something unexpected.' `
               ("$_" + " | " + $_.ScriptStackTrace)
}

if (-not (Test-Path $Sources)) {
    Say-Problem "Couldn't find the list of what to download." "missing file $Sources"
}

# ── which hardware ───────────────────────────────────────────────────
$Arch = if ([Environment]::Is64BitOperatingSystem) { 'x86_64' } else { 'unknown' }

# ── the Python address and checksum: from the shared list ────────────
#
# The same list the macOS shell script and the installer itself read.
# A number written in three places drifts apart three times as fast.
$Row = $null
foreach ($line in [System.IO.File]::ReadAllLines($Sources,
                  [System.Text.Encoding]::UTF8)) {
    $s = $line.Trim()
    if ($s -eq '' -or $s.StartsWith('#')) { continue }
    $parts = $s -split '\s+'
    if ($parts[0] -eq 'python' -and $parts[1] -eq 'windows' -and $parts[2] -eq $Arch) {
        $Row = $parts; break
    }
}
if (-not $Row) {
    Say-Problem "There's no ready-made Python for this system (windows/$Arch), so Vertcut
can't install itself here. You can still install it from the source code —
see the README on GitHub." `
               "no 'python windows $Arch' row in sources.txt"
}
$Url = $Row[3]
$Want = $Row[4]

# ── start from scratch, not on top ───────────────────────────────────
#
# An unfinished folder left from last time is thrown away entirely:
# building on top of leftovers gives an install nobody can say for sure
# what it's made of.
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $Stage, $Show | Out-Null

# The first page comes BEFORE the first download: the person is waiting.
$FirstPage = @"
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="2"><title>Installing Vertcut</title>
<style>body{margin:0;background:#FBFBFA;color:#191919;
font:15px/1.5 -apple-system,"Segoe UI",system-ui,sans-serif;padding:40px 24px}
@media(prefers-color-scheme:dark){body{background:#1A1A18;color:#F0EFEC}}
.page{max-width:560px;margin:0 auto}h1{font-size:24px;margin:0 0 8px}
p{margin:0 0 8px;color:#6B6B6B}</style></head><body><div class="page">
<h1>Installing Vertcut</h1>
<p>This happens only once and needs the internet — about 800 MB.</p>
<p>After that, Vertcut works offline.</p>
<p>Now: downloading Python, 25 MB.</p></div></body></html>
"@
[System.IO.File]::WriteAllText((Join-Path $Show 'progress.html'), $FirstPage,
                               [System.Text.Encoding]::UTF8)

# ── download Python ──────────────────────────────────────────────────
$Archive = Join-Path $Stage 'python.tar.gz'
try {
    # PowerShell's own progress bar is turned off on purpose: it makes the
    # download several times slower, and we show progress without it.
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $Url -OutFile $Archive -UseBasicParsing -TimeoutSec 600
} catch {
    # The server answered — so the internet works, but the file isn't
    # there: "wait for the internet" would be untrue. The same fork as in
    # `install.sh` and the installer.
    if ($_.Exception.Response) {
        Say-Problem "The internet works, but the server didn't give us Python — it may be
down for a while, or the file has moved. Nothing is broken: try again later,
or get a newer Vertcut." $Url
    }
    Say-Problem "Couldn't download Python — looks like there's no internet connection.
Nothing is broken: open Vertcut again when you're back online." $Url
}

# ── check the checksum ───────────────────────────────────────────────
#
# What arrives here will be run.
# **Computed with .NET, not `Get-FileHash`.** That command comes from
# a module, modules are looked up along paths — and on someone else's
# machine it may not be found: the build machine answered "Get-FileHash
# is not recognized" and the install failed at the first step. Checking
# a download must not depend on whether a module turned up: .NET itself
# can compute the checksum, and .NET is always there.
$Got = & {
    $Hasher = [System.Security.Cryptography.SHA256]::Create()
    $Stream = [System.IO.File]::OpenRead($Archive)
    try {
        ([BitConverter]::ToString($Hasher.ComputeHash($Stream)) `
            -replace '-', '').ToLower()
    } finally {
        $Stream.Dispose(); $Hasher.Dispose()
    }
}
if ($Got -ne $Want) {
    Remove-Item -Recurse -Force $Stage
    Say-Problem "The downloaded Python isn't the file we expected, so the installer
stopped and installed nothing. Maybe it's an update, maybe it was tampered
with — there's no way to tell which." "expected $Want, got $Got"
}

# ── unpack ───────────────────────────────────────────────────────────
#
# `tar` comes with every Windows 10 and newer — PowerShell has no
# unpacker of its own for .tar.gz.
& tar -xzf $Archive -C $Stage
if ($LASTEXITCODE -ne 0) {
    Remove-Item -Recurse -Force $Stage
    Say-Problem "The downloaded Python couldn't be unpacked." $Archive
}
Remove-Item -Force $Archive

$Py = Join-Path $Stage 'python\python.exe'
if (-not (Test-Path $Py)) { Say-Problem 'The downloaded Python archive has no Python inside.' $Py }

# ── the Python half does the rest ────────────────────────────────────
#
# PYTHONUTF8: without it Windows reads Python's output in its old
# encoding, and any non-English letters in the log turn into garbage
# exactly when the log is needed.
$env:PYTHONUTF8 = '1'
$InstallerArgs = @('--stage', $Stage, '--target', $Target, '--wheel', $Wheel,
                   '--page-dir', $Show)
if ($Icon) { $InstallerArgs += @('--icon', $Icon) }
& $Py (Join-Path $Here 'installer.py') @InstallerArgs
exit $LASTEXITCODE
