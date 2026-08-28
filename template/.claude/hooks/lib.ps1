#requires -Version 7.0
<#
    Shared, portable helpers for all beyin hooks -- Windows (PowerShell) port
    of lib.sh. Function names follow PowerShell's Verb-Noun convention; each
    one names its bash original so the two files can be read side by side.

    | lib.sh                       | lib.ps1                     |
    |------------------------------|-----------------------------|
    | beyin_mark_python_missing    | Set-BeyinPythonMissing      |
    | beyin_mtime                  | Get-BeyinMtime              |
    | beyin_session_key            | Get-BeyinSessionKey         |
    | beyin_cleanup_session_state  | Clear-BeyinSessionState     |
    | beyin_emit                   | Write-BeyinEmit             |
    | beyin_yesterday              | Get-BeyinYesterday          |
    | (no equivalent)              | Test-BeyinPythonUsable      |
    | (no equivalent)              | Get-BeyinPython             |
    | (no equivalent)              | Start-BeyinFlush            |

    Two deliberate platform differences, both documented in docs/WINDOWS-PORT.md:

    1. lib.sh shells out to python3 for SHA-256 and JSON escaping. PowerShell has
       both natively, so the hook layer here needs no Python at all -- Python is
       required only by the engine (flush.py). The session key is byte-identical
       to the bash one: SHA-256 of the UTF-8 session_id, lowercase hex.
    2. Python is verified by RUNNING it, not by looking it up. On Windows
       C:\...\WindowsApps\python3.exe exists even when Python is not installed:
       it is a Microsoft Store shortcut. A presence check passes there and the
       engine then never runs while the hook reports success.

    This file is dot-sourced, never executed on its own.
#>

Set-StrictMode -Version Latest

# lib.sh:2 -- the recursion guard. The summarizer's own `claude -p` call opens a
# session; without this every hook would fire again inside it, forever.
if (-not [string]::IsNullOrEmpty($env:BEYIN_INVOKED_BY)) { exit 0 }

# No bash equivalent, and not optional. On Windows [Console]::OutputEncoding
# defaults to the legacy OEM code page -- cp857 on a Turkish machine. Everything
# this system emits is Turkish, and the memory folder name contains an emoji.
# Measured on cp857: "Türkçe" survives as cp857 bytes that are not valid UTF-8,
# and 🔮 is replaced by "?" outright -- unrecoverable, not merely mis-decoded.
# Set once here so every hook that dot-sources this file is covered; setting it
# per-hook is how a hook gets forgotten.
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch { }

# lib.sh:5-13
if (-not [string]::IsNullOrWhiteSpace($env:CLAUDE_PROJECT_DIR)) {
    $script:BeyinProjectDir = $env:CLAUDE_PROJECT_DIR
}
else {
    $script:BeyinProjectDir = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}
$script:BeyinStateDir = Join-Path $script:BeyinProjectDir '.claude\scripts\.state'
New-Item -ItemType Directory -Force -Path $script:BeyinStateDir -ErrorAction SilentlyContinue | Out-Null

$script:BeyinMemoryDir = Join-Path $script:BeyinProjectDir "`u{1F52E} 850-Companion"


function Set-BeyinPythonMissing {
    <# lib.sh:15-18 -- beyin_mark_python_missing #>
    try {
        New-Item -ItemType Directory -Force -Path $script:BeyinStateDir -ErrorAction SilentlyContinue | Out-Null
        Set-Content -LiteralPath (Join-Path $script:BeyinStateDir 'python3-missing') `
            -Value '' -Encoding utf8NoBOM -NoNewline -ErrorAction SilentlyContinue
    }
    catch { }
}


function Get-BeyinMtime {
    <# lib.sh:20-35 -- beyin_mtime. Unix seconds, 0 when absent or unreadable. #>
    param([Parameter(Mandatory)][string]$Path)
    try {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return 0 }
        return [long][System.DateTimeOffset]::new(
            (Get-Item -LiteralPath $Path).LastWriteTimeUtc, [TimeSpan]::Zero
        ).ToUnixTimeSeconds()
    }
    catch { return 0 }
}


function Get-BeyinSessionKey {
    <#
    .SYNOPSIS
        lib.sh:49-66 -- beyin_session_key.
    .DESCRIPTION
        SHA-256 of the UTF-8 session_id as lowercase hex -- byte-identical to
        what bash produces. Returns $null when the payload is not an object,
        has no session_id, or the id is empty, matching bash's exit 1.
    #>
    param([string]$RawPayload)

    if ([string]::IsNullOrWhiteSpace($RawPayload)) { return $null }
    try {
        $payload = $RawPayload | ConvertFrom-Json -ErrorAction Stop
    }
    catch { return $null }
    if ($payload -isnot [pscustomobject]) { return $null }
    if (-not $payload.PSObject.Properties['session_id']) { return $null }

    $id = $payload.session_id
    if ($id -isnot [string] -or [string]::IsNullOrEmpty($id)) { return $null }

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($id))
        return -join ($bytes | ForEach-Object { $_.ToString('x2') })
    }
    finally { $sha.Dispose() }
}


function Clear-BeyinSessionState {
    <#
    .SYNOPSIS
        lib.sh:68-79 -- beyin_cleanup_session_state.
    .DESCRIPTION
        Drops per-session state older than seven days. Same four filename
        patterns and the same stale lock-directory sweep as bash.
    #>
    if (-not (Test-Path -LiteralPath $script:BeyinStateDir -PathType Container)) { return }
    $cutoff = (Get-Date).AddDays(-7)

    try {
        Get-ChildItem -LiteralPath $script:BeyinStateDir -File -ErrorAction SilentlyContinue |
            Where-Object {
                $_.LastWriteTime -lt $cutoff -and (
                    $_.Name -like 'session_start_time.*' -or
                    $_.Name -like 'prompt_count.*' -or
                    $_.Name -like 'needs_reflection.*' -or
                    $_.Name -like 'hookin-*.json'
                )
            } |
            Remove-Item -Force -ErrorAction SilentlyContinue

        Get-ChildItem -LiteralPath $script:BeyinStateDir -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -lt $cutoff -and $_.Name -like 'prompt_count.*.lock' } |
            ForEach-Object {
                # rmdir, not rm -rf: a lock directory that is not empty is a
                # live lock, and bash's rmdir would refuse it too.
                if (-not (Get-ChildItem -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue)) {
                    Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
                }
            }
    }
    catch { }
}


function Write-BeyinEmit {
    <#
    .SYNOPSIS
        lib.sh:81-103 -- beyin_emit.
    .DESCRIPTION
        Emits the hookSpecificOutput envelope on stdout. Bash needs python3 to
        JSON-escape the text and falls back to a sed-escaped warning when it is
        missing; ConvertTo-Json is native here, so the escape path cannot fail
        for lack of Python and no fallback string is needed.
    #>
    param(
        [Parameter(Mandatory)][string]$Event,
        [Parameter(Mandatory)][string]$Text
    )

    if ($Event -notin @('SessionStart', 'UserPromptSubmit', 'SessionEnd', 'PreCompact')) { return }
    if ([string]::IsNullOrEmpty($Text)) { return }

    @{
        hookSpecificOutput = @{
            hookEventName     = $Event
            additionalContext = $Text
        }
    } | ConvertTo-Json -Compress -Depth 5
}


function Get-BeyinYesterday {
    <# lib.sh:105-111 -- beyin_yesterday #>
    return (Get-Date).AddDays(-1).ToString('yyyy-MM-dd')
}


function Test-BeyinPythonUsable {
    <#
    .SYNOPSIS
        Proves a path is a working Python 3 by running it.
    .DESCRIPTION
        No bash equivalent -- bash only needs `command -v python3` because POSIX
        has no Store stub. On Windows C:\...\WindowsApps\python3.exe exists with
        Python uninstalled and opens the Microsoft Store. Looking it up succeeds;
        running it does nothing. Verified by output, not by presence.
    #>
    param([Parameter(Mandatory)][string]$Path)
    try {
        # No quotes in the probe on purpose: Windows PowerShell 5.1 strips
        # embedded double quotes when handing arguments to native commands.
        # scripts/install.ps1 must run under 5.1, so both use the same form.
        $probe = & $Path '-c' 'import sys; print(sys.version_info.major)' 2>$null
        if ($LASTEXITCODE -ne 0) { return $false }
        $line = "$($probe | Select-Object -First 1)".Trim()
        if ($line -notmatch '^(\d+)$') { return $false }
        return ([int]$Matches[1] -ge 3)
    }
    catch { return $false }
}


function Get-BeyinPython {
    <#
    .SYNOPSIS
        First genuinely working Python 3 on PATH, or $null.
    .DESCRIPTION
        -All matters: the Store stub can sit ahead of a real install on PATH.
        Without it the stub wins and the engine silently never runs.
    #>
    foreach ($name in @('python3', 'python')) {
        foreach ($cmd in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
            if ($cmd.Source -and (Test-BeyinPythonUsable -Path $cmd.Source)) {
                return $cmd.Source
            }
        }
    }
    return $null
}


function Start-BeyinPythonDetached {
    <# Start Python without losing arguments that contain spaces. #>
    param(
        [Parameter(Mandatory)][string]$Python,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$WorkingDirectory
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Python
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    foreach ($argument in $Arguments) {
        [void]$startInfo.ArgumentList.Add($argument)
    }
    $process = [System.Diagnostics.Process]::Start($startInfo)
    if ($null -eq $process) { throw 'python-process-start-failed' }
    $process.Dispose()
}


function Start-BeyinFlush {
    <#
    .SYNOPSIS
        Writes the raw hook payload to disk and detaches the summarizer.
        Covers session-end.sh:8-13,49-58 and pre-compact.sh:8-13,15-24.
    .DESCRIPTION
        Never throws; always returns a status string so the caller can decide
        what to record. flush.py deletes the hookin file itself.
    .OUTPUTS
        'baslatildi' | 'payload-yok' | 'motor-yok' | 'python-yok' | 'hata:<mesaj>'
    #>
    param(
        [string]$RawPayload,
        [ValidateSet('sessionend', 'precompact')][string]$Reason = 'sessionend',
        [Parameter(Mandatory)][string]$VaultRoot
    )

    # bash writes hookin-$$.json unconditionally via `cat >` and only checks that
    # the path is nonempty. An empty payload there produces an empty file the
    # engine then rejects. We refuse earlier and say so, which is the same
    # outcome without spawning a doomed process.
    if ([string]::IsNullOrWhiteSpace($RawPayload)) { return 'payload-yok' }

    $scripts = Join-Path $VaultRoot '.claude\scripts'
    $flush = Join-Path $scripts 'flush.py'
    # No bash equivalent: bash launches after checking Python only. Naming a
    # missing engine beats launching a process that cannot start.
    if (-not (Test-Path -LiteralPath $flush -PathType Leaf)) { return 'motor-yok' }

    $python = Get-BeyinPython
    if (-not $python) { return 'python-yok' }

    $hookIn = $null
    try {
        $state = Join-Path $scripts '.state'
        New-Item -ItemType Directory -Force -Path $state | Out-Null

        # Name must match flush.py's hookin-*.json pattern or the file is never
        # cleaned up (see _managed_hook_input).
        $hookIn = Join-Path $state ("hookin-{0}-{1}.json" -f $PID, [guid]::NewGuid().ToString('N').Substring(0, 8))
        Set-Content -LiteralPath $hookIn -Value $RawPayload -Encoding utf8NoBOM -NoNewline

        $argv = [System.Collections.Generic.List[string]]::new()
        $argv.Add($flush)
        $argv.Add('--hook-input')
        $argv.Add($hookIn)
        if ($Reason -eq 'precompact') {
            $argv.Add('--reason')
            $argv.Add('precompact')
        }

        # bash uses nohup ... &. The hook process dying must not kill the
        # summarizer, so the child gets its own hidden window.
        Start-BeyinPythonDetached -Python $python -Arguments $argv.ToArray() `
            -WorkingDirectory $VaultRoot
        return 'baslatildi'
    }
    catch {
        if ($hookIn -and (Test-Path -LiteralPath $hookIn)) {
            Remove-Item -LiteralPath $hookIn -Force -ErrorAction SilentlyContinue
        }
        return "hata:$($_.Exception.Message)"
    }
}


function Write-BeyinFlushError {
    <#
    .SYNOPSIS
        Records a failed flush start durably.
    .DESCRIPTION
        No bash equivalent. bash marks python3-missing and emits a warning that
        vanishes with the session. This adds a timestamped line that survives, so
        `beyin doktor` can see what happened. The python3-missing marker is still
        written by the callers, so upstream's contract is preserved too.
    #>
    param(
        [Parameter(Mandatory)][string]$Reason,
        [Parameter(Mandatory)][string]$Result
    )
    try {
        New-Item -ItemType Directory -Force -Path $script:BeyinStateDir -ErrorAction SilentlyContinue | Out-Null
        Set-Content -LiteralPath (Join-Path $script:BeyinStateDir 'flush_last_error') `
            -Value ("{0} {1} -> {2}" -f $Reason, (Get-Date -Format 'yyyy-MM-dd HH:mm'), $Result) `
            -Encoding utf8NoBOM -ErrorAction SilentlyContinue
    }
    catch { }
}
