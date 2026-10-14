# What runs when you double-click Vertcut on Windows (Vertcut.exe and
# install\Vertcut.cmd both just start this file).
#
# THE SAME AS `launcher.sh`, WITHIN THE SAME LIMITS: check whether Vertcut
# is installed; if not, install it while showing progress; then start it
# and open a tab. There's no logic here — it lives in Python, and the
# terminal command uses the same code.
#
# WHAT IT TOUCHES. Three folders, listed below. Everything it says goes
# into a log file in the settings folder, so there's something to read
# and send if it fails.
#
# WHY VERTCUT RUNS AS A CHILD PROCESS INSTEAD OF REPLACING THIS SCRIPT.
# Otherwise the launcher wouldn't see Vertcut crash on startup — exactly
# the kind of failure that happens before Vertcut's screen exists, so
# it's the launcher that has to report it. Vertcut watches for the
# launcher going away itself: `--exit-with-icon`.
#
# HOW WELL IT'S TESTED. A build machine runs it on a clean Windows on
# every change. It has not been watched on a real person's computer yet.

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── three places, each for its own reason ────────────────────────────
#
#   program   — what was downloaded and installed (%LOCALAPPDATA%\vertcut);
#   settings  — your AI key, spending log, your own subtitle style: they
#               survive a reinstall;
#   your work — analyzed videos and exported clips; nothing ever touches
#               them (they're in %USERPROFILE%\vertcut, not used here).
$Program  = Join-Path $env:LOCALAPPDATA 'vertcut'
$Settings = if ($env:VERTCUT_HOME) { Join-Path $env:VERTCUT_HOME '.settings' }
            else { Join-Path $env:USERPROFILE '.vertcut' }
$Logs = Join-Path $Settings 'logs'
$Show = Join-Path $Settings 'install'
$Py   = Join-Path $Program 'python\python.exe'

New-Item -ItemType Directory -Force -Path $Logs, $Show | Out-Null
$Log = Join-Path $Logs ("launch-" + (Get-Date -Format 'yyyy-MM-dd-HHmmss') + ".log")

# Everything Vertcut says goes to a file: there's no terminal, and after
# a crash there must be something to read and to send.
function Write-Log($Line) {
    Add-Content -Path $Log -Value $Line -Encoding UTF8
}

# A PAGE THAT DIDN'T OPEN IS NOT A FAILURE. The same rule as on the Mac,
# and here it needs its own lines: `$ErrorActionPreference = 'Stop'` would
# stop the whole launcher at the first hiccup, and there may be nothing to
# open the page with — the computer may have no default browser at all.
# Failing the install over a tab that didn't open would turn an
# inconvenience into a breakage.
function Open-Page($What) {
    try { Start-Process $What | Out-Null }
    catch { Write-Log ("couldn't open " + $What + ": " + $_) }
}
Write-Log ("── launch " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " ──")

# PYTHONUTF8: without it Windows writes the log in its old encoding, and
# non-English letters turn into garbage exactly when the log is needed.
$env:PYTHONUTF8 = '1'

# ── not installed yet ────────────────────────────────────────────────
$JustInstalled = $false
if (-not (Test-Path (Join-Path $Program 'version.json'))) {
    $JustInstalled = $true
    Write-Log 'not installed yet — installing'
    $Wheel = Get-ChildItem -Path $Here -Filter '*.whl' | Select-Object -First 1
    if (-not $Wheel) {
        Write-Log 'no Vertcut package (.whl) next to the launcher'
        exit 1
    }
    # The page is opened BEFORE the work starts: it's already written and
    # already says how much will be downloaded. Staying silent isn't an
    # option.
    # THE INSTALLER'S WORDS GO TO THE LOG. Otherwise they go nowhere: the
    # launcher runs hidden, it has no console, and everything the installer
    # says is lost — the launcher would write "installation failed" and not
    # say why. (The Mac side does the same with one line,
    # `exec >>"$LOG" 2>&1`.)
    #
    # Two files, because Start-Process can't send both streams into one;
    # they're merged right after.
    $OutFile = "$Log.install"
    $ErrFile = "$Log.install.err"
    $Installing = Start-Process -PassThru -NoNewWindow -FilePath 'powershell' `
        -RedirectStandardOutput $OutFile -RedirectStandardError $ErrFile `
        -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',
                        (Join-Path $Here 'install.ps1'),
                        # THE STAGE FOLDER NAME IS PLAIN LATIN. Its path
                        # is passed on to `tar`, and another program reads
                        # its command line in its own encoding: with
                        # a non-Latin folder name the install on an
                        # English Windows stopped with "Failed to open
                        # vertcut.?????".
                        '-Stage', "$Program.new", '-Target', $Program,
                        '-Wheel', $Wheel.FullName, '-Show', $Show,
                        # The icon itself: the installer puts a copy on
                        # your Desktop so you don't have to look for it
                        # later. On Windows the "icon" is the folder
                        # that holds Vertcut.exe.
                        '-Icon', (Split-Path $Here -Parent))
    Start-Sleep -Seconds 1
    Open-Page (Join-Path $Show 'progress.html')
    $Installing.WaitForExit()
    foreach ($File in @($OutFile, $ErrFile)) {
        if (Test-Path $File) {
            Get-Content $File -Encoding UTF8 |
                ForEach-Object { Write-Log $_ }
            Remove-Item -Force $File -ErrorAction SilentlyContinue
        }
    }
    # DID IT INSTALL? WE ASK THE DISK, NOT THE EXIT CODE.
    # `Start-Process -PassThru` doesn't always give the exit code: on the
    # build machine it came back empty, and "installation failed, code "
    # is a failure that says nothing. The installer writes `version.json`
    # as its very last action, and that answers the same question
    # every time.
    if (-not (Test-Path (Join-Path $Program 'version.json'))) {
        Write-Log 'installation failed — nothing was installed'
        exit 1
    }
}

if (-not (Test-Path $Py)) {
    Write-Log "no Python at $Py"
    exit 1
}

# ── start Vertcut ────────────────────────────────────────────────────
# Just installed — then Vertcut does NOT open a tab: the person is already
# looking at the progress page, and we'll send that page on to Vertcut
# ourselves. A normal launch is the other way round: there's nothing to
# send on, and Vertcut opens the tab itself.
$ServerArgs = @('-m','vertcut','screen','--exit-with-icon')
if ($JustInstalled) { $ServerArgs += '--no-browser' }
$Server = Start-Process -PassThru -NoNewWindow -FilePath $Py `
    -ArgumentList $ServerArgs `
    -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"

# If it dies in the first seconds, Vertcut's screen never appeared, and
# the launcher has to say so. Later than that, Vertcut's screen talks.
Start-Sleep -Seconds 3
if ($Server.HasExited) {
    # Zero is NOT a crash, and telling the two apart matters. Vertcut was
    # already running: the second copy found the first one, opened its tab
    # and exited cleanly. Without this check, clicking the icon a second
    # time gives two tabs at once — the running Vertcut and a "Vertcut
    # didn't start" page on top of it.
    if ($Server.ExitCode -eq 0) {
        Write-Log 'Vertcut was already running — it opened its own tab; exiting'
        exit 0
    }
    Write-Log ("Vertcut didn't start, exit code " + $Server.ExitCode)
    # VERTCUT'S ERROR IS IN THE SECOND FILE: Start-Process doesn't merge
    # the streams, and Python's traceback goes to stderr. We merge them
    # ourselves — like the installer's words above — so the actual problem
    # shows both in the log and on the page.
    if (Test-Path "$Log.err") {
        Get-Content "$Log.err" -Encoding UTF8 | ForEach-Object { Write-Log $_ }
        Remove-Item -Force "$Log.err" -ErrorAction SilentlyContinue
    }
    # If we just installed, the person is looking at the progress page,
    # and the problem is shown THERE. Zero means "the page got it";
    # otherwise we open the file in a new tab.
    & $Py (Join-Path $Here 'progress.py') --page-dir $Show `
        --title "Vertcut didn't start" `
        --hint "Below are the last lines of the log. The whole log is here: $Log" `
        --log-tail $Log
    if ($LASTEXITCODE -ne 0) {
        Open-Page (Join-Path $Show 'progress.html')
    }
    exit $Server.ExitCode
}

# Just installed — so the person is looking at the progress page. We send
# it on to Vertcut: the address is asked of the one who knows it, not
# put together here a second time.
if ($JustInstalled) {
    $Address = & $Py -m vertcut screen --print-address 2>$null
    if ($Address) {
        # In the background and for a long time: a background tab asks
        # rarely — the browser saves effort — and it still has to be sent
        # on when the person comes back ten minutes later. Vertcut
        # shouldn't wait for that.
        # Quotes by hand: Start-Process joins arguments with spaces and
        # doesn't quote them, and paths can contain spaces.
        Start-Process -WindowStyle Hidden -FilePath $Py -ArgumentList @(
            ('"' + (Join-Path $Here 'progress.py') + '"'),
            '--page-dir', ('"' + $Show + '"'),
            '--go-to', ('"' + $Address + '"'), '--wait', '900') | Out-Null
    }
}

$Server.WaitForExit()
Write-Log ("── Vertcut stopped " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " ──")
