#requires -Version 7.0
<#
    Count prompts and nudge at every multiple of fifteen.
    Windows port of prompt-counter.sh -- same state filenames, same lock
    discipline, same threshold.
#>

Set-StrictMode -Version Latest

# prompt-counter.sh:2
if (-not [string]::IsNullOrEmpty($env:BEYIN_INVOKED_BY)) { exit 0 }

# prompt-counter.sh:5-6
. (Join-Path $PSScriptRoot 'lib.ps1')

# prompt-counter.sh:8-9 -- no usable session_id means no counting at all.
# Deliberately NOT falling back to a shared key: unrelated malformed events
# would then all increment one counter.
$raw = [Console]::In.ReadToEnd()
$key = Get-BeyinSessionKey -RawPayload $raw
if ([string]::IsNullOrEmpty($key)) { exit 0 }

$countFile = Join-Path $script:BeyinStateDir "prompt_count.$key"
$lockDir = "$countFile.lock"

# prompt-counter.sh:12-18 -- the lock is a directory because creating one is
# atomic and fails if it already exists. New-Item without -Force has exactly
# that property; -Force would silently succeed and destroy the mutual exclusion.
$acquired = $false
for ($attempt = 0; $attempt -lt 500; $attempt++) {
    try {
        New-Item -ItemType Directory -Path $lockDir -ErrorAction Stop | Out-Null
        $acquired = $true
        break
    }
    catch { Start-Sleep -Milliseconds 10 }
}
if (-not $acquired) { exit 0 }

$count = 0
# Declared before the try: Set-StrictMode makes the catch block's reference to
# $tmp a runtime error if the throw happens before the assignment.
$tmp = $null
try {
    # prompt-counter.sh:22-28 -- first line only; anything non-numeric is 0.
    if (Test-Path -LiteralPath $countFile -PathType Leaf) {
        $first = Get-Content -LiteralPath $countFile -TotalCount 1 -ErrorAction SilentlyContinue
        [int]::TryParse("$first".Trim(), [ref]$count) | Out-Null
    }
    $count++

    # prompt-counter.sh:31-35 -- write to a temp file and rename over the target.
    # A reader never observes a half-written count.
    $tmp = "$countFile.tmp.$PID"
    Set-Content -LiteralPath $tmp -Value $count -Encoding utf8NoBOM
    Move-Item -LiteralPath $tmp -Destination $countFile -Force
}
catch {
    if ($tmp -and (Test-Path -LiteralPath $tmp)) {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}
finally {
    # prompt-counter.sh:19,36 -- the trap plus the explicit rmdir. finally covers
    # both: the lock is released whether the body succeeded or threw.
    Remove-Item -LiteralPath $lockDir -Force -Recurse -ErrorAction SilentlyContinue
}

# prompt-counter.sh:39-41 -- EVERY multiple of 15, not only the first one.
if ($count -gt 0 -and ($count % 15) -eq 0) {
    Write-BeyinEmit -Event 'UserPromptSubmit' `
        -Text "[Hafıza] $count. mesaj. Oturum sonunda 🔮 850-Companion/Last-Session.md ve Threads.md güncellemeyi unutma."
}
exit 0
