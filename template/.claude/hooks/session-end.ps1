#requires -Version 7.0
<#
    Mark relational-memory debt, then detach the automatic session flush.
    Windows port of session-end.sh.
#>

Set-StrictMode -Version Latest

# session-end.sh:2
if (-not [string]::IsNullOrEmpty($env:BEYIN_INVOKED_BY)) { exit 0 }

# session-end.sh:5-6
. (Join-Path $PSScriptRoot 'lib.ps1')

$raw = [Console]::In.ReadToEnd()

# session-end.sh:15-18 -- the key comes from the payload; without it there is no
# per-session state to read or clean up.
$key = Get-BeyinSessionKey -RawPayload $raw

# session-end.sh:20-34
$start = [long]0
$prompts = 0
$startFile = $null
$countFile = $null
$reflectionFile = $null

if (-not [string]::IsNullOrEmpty($key)) {
    $startFile = Join-Path $script:BeyinStateDir "session_start_time.$key"
    $countFile = Join-Path $script:BeyinStateDir "prompt_count.$key"
    $reflectionFile = Join-Path $script:BeyinStateDir "needs_reflection.$key"

    if (Test-Path -LiteralPath $startFile -PathType Leaf) {
        $line = Get-Content -LiteralPath $startFile -TotalCount 1 -ErrorAction SilentlyContinue
        [long]::TryParse("$line".Trim(), [ref]$start) | Out-Null
    }
    if (Test-Path -LiteralPath $countFile -PathType Leaf) {
        $line = Get-Content -LiteralPath $countFile -TotalCount 1 -ErrorAction SilentlyContinue
        [int]::TryParse("$line".Trim(), [ref]$prompts) | Out-Null
    }
}

# session-end.sh:36-41 -- "did the agent touch relational memory this session?"
# is answered by mtime, exactly as upstream. A content hash would be stricter
# (a rewrite with identical bytes would no longer count as an update), but that
# changes when reflection debt is recorded, so parity wins here.
$modified = $false
$lastSession = Join-Path $script:BeyinMemoryDir 'Last-Session.md'
if (Test-Path -LiteralPath $lastSession -PathType Leaf) {
    if ((Get-BeyinMtime -Path $lastSession) -gt $start) { $modified = $true }
}

# session-end.sh:43-47
if ($prompts -ge 5 -and -not $modified -and -not [string]::IsNullOrEmpty($reflectionFile)) {
    try {
        Set-Content -LiteralPath $reflectionFile -Encoding utf8NoBOM -ErrorAction SilentlyContinue `
            -Value ("Oturum hafıza güncellemeden bitti. Prompt: {0}. {1}" -f `
                $prompts, (Get-Date -Format 'yyyy-MM-dd HH:mm'))
    }
    catch { }
}

# session-end.sh:49-58
try {
    $result = Start-BeyinFlush -RawPayload $raw -Reason 'sessionend' -VaultRoot $script:BeyinProjectDir
}
catch { $result = "hata:$($_.Exception.Message)" }

if ($result -ne 'baslatildi') {
    # Durable diagnostic; no bash equivalent. Without it a failed flush at
    # session end leaves no trace anywhere -- the session is over, the emitted
    # warning has nowhere to go.
    Write-BeyinFlushError -Reason 'sessionend' -Result $result

    if ($result -eq 'python-yok') {
        # session-end.sh:54-56 -- upstream's marker and warning, preserved.
        Set-BeyinPythonMissing
        Write-BeyinEmit -Event 'SessionEnd' `
            -Text 'Beyin arka plan özeti başlatılamadı: python3 bulunamadı. beyin-doktor çalıştır.'
    }
}

# Git sync - hourly backup to private repo (background, non-blocking)
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitSyncScript = @'
    param($VaultRoot)
    $stateDir = Join-Path $VaultRoot '.claude\scripts\.state'
    $lastPushFile = Join-Path $stateDir 'last-push.json'
    New-Item -ItemType Directory -Force -Path $stateDir -ErrorAction SilentlyContinue | Out-Null
    $nowEpoch = [long][DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $doPush = $false

    if (Test-Path -LiteralPath $lastPushFile -PathType Leaf) {
        try {
            $lastPush = Get-Content -LiteralPath $lastPushFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
            $lastPushTs = if ($lastPush.ts) { [long]$lastPush.ts } else { 0 }
        }
        catch { $lastPushTs = 0 }
        if (($nowEpoch - $lastPushTs) -ge 3600) { $doPush = $true }
    }
    else {
        $doPush = $true
    }

    if ($doPush) {
        try {
            $remote = git -C $VaultRoot remote get-url origin 2>$null
        }
        catch { $remote = $null }
        if (-not [string]::IsNullOrEmpty($remote)) {
            try {
                $branch = git -C $VaultRoot branch --show-current 2>$null
            }
            catch { $branch = 'main' }
            if ([string]::IsNullOrEmpty($branch)) { $branch = 'main' }

            try {
                # Ensure local git identity
                $userName = git -C $VaultRoot config user.name 2>$null
                if ([string]::IsNullOrEmpty($userName)) {
                    git -C $VaultRoot config --local user.name "avenoxbeyin" >$null 2>&1
                    git -C $VaultRoot config --local user.email "beyin@avenox.local" >$null 2>&1
                }

                # Pull with ff-only, ignore failures
                git -C $VaultRoot pull --ff-only -q origin $branch >$null 2>&1

                # Stage all changes
                git -C $VaultRoot add -A >$null 2>&1

                # Check if there are staged changes
                $hasChanges = $false
                try {
                    $diffResult = git -C $VaultRoot diff --cached --quiet 2>$null
                    $hasChanges = ($LASTEXITCODE -ne 0)
                }
                catch { $hasChanges = $false }

                if ($hasChanges) {
                    $nowReadable = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
                    git -C $VaultRoot commit -q -m "vault backup: $nowReadable" >$null 2>&1
                    git -C $VaultRoot push -q origin $branch >$null 2>&1
                    $payload = @{ ts = $nowEpoch; last = $nowReadable } | ConvertTo-Json -Compress
                    Set-Content -LiteralPath $lastPushFile -Value $payload -Encoding utf8NoBOM -NoNewline
                }
            }
            catch { }
        }
    }
'@
    Start-Job -ScriptBlock ([ScriptBlock]::Create($gitSyncScript)) -ArgumentList $script:BeyinProjectDir | Out-Null
}

# session-end.sh:60-61 -- the session is over; its start time and prompt count go.
# needs_reflection.<key> deliberately survives: session-start reads and clears it.
foreach ($path in @($startFile, $countFile)) {
    if (-not [string]::IsNullOrEmpty($path)) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
}

exit 0
