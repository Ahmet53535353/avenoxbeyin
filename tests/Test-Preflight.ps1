#requires -Version 7.0
<#
    Dependency-gate regression tests.

    Locks two measured Windows traps shut:

    1. C:\...\WindowsApps\python3.exe exists even when Python is NOT installed --
       it is a Microsoft Store shortcut. A presence check passes there, the
       engine then never runs, and the hook still reports success.
    2. scripts/install.ps1 must load and run under Windows PowerShell 5.1. If it
       ever grows a `#requires -Version 7.0`, the user the gate exists for stops
       seeing the gate's message and gets a bare version error instead.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$lib = Join-Path $repo 'template\.claude\hooks\lib.ps1'
$installer = Join-Path $repo 'scripts\install.ps1'

$failures = [System.Collections.Generic.List[string]]::new()
$total = 0

function Assert($name, $condition, $detail) {
    $script:total++
    if ($condition) { Write-Host "  ok   $name" }
    else { Write-Host "  FAIL $name -- $detail"; $script:failures.Add($name) }
}

# A child process is required, not just a changed $env:PATH: PowerShell caches
# command discovery and would keep resolving the real python in-process.
function Invoke-InChild([string]$Exe, [string]$PathValue, [string]$Body) {
    $script = @"
`$env:PATH = '$PathValue'
$Body
"@
    return (& $Exe -NoProfile -NonInteractive -Command $script | Select-Object -Last 1)
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("beyinpre-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
$stubDir = Join-Path $tmp 'stub'
New-Item -ItemType Directory -Force -Path $stubDir | Out-Null

# Behaves like the real Store stub: a message on stderr, a non-zero exit code.
$stubBody = @'
@echo off
echo Python was not found; run without arguments to install from the Microsoft Store. 1>&2
exit /b 9009
'@
foreach ($n in 'python3.cmd', 'python.cmd') {
    Set-Content -LiteralPath (Join-Path $stubDir $n) -Value $stubBody -Encoding ascii
}

# Find a genuinely working Python on this machine, if there is one.
$realPython = $null
foreach ($cmd in @(Get-Command python3, python -All -ErrorAction SilentlyContinue)) {
    if (-not $cmd.Source) { continue }
    try {
        $v = & $cmd.Source '-c' 'import sys; print(sys.version_info.major)' 2>$null
        if ($LASTEXITCODE -eq 0 -and "$v".Trim() -match '^[3-9]$') { $realPython = $cmd.Source; break }
    }
    catch { }
}

Write-Host "Bagimlilik kapisi regresyon testi"
Write-Host ("  gercek python: " + $(if ($realPython) { $realPython } else { '(yok)' }))

# --- lib.ps1 tarafi (kancalarin kullandigi) ---
$r1 = Invoke-InChild 'pwsh' $stubDir ". '$lib'`n`$r = Get-BeyinPython`nif (`$null -eq `$r) { 'NULL' } else { `$r }"
Assert 'lib_stubu_reddeder' ("$r1".Trim() -eq 'NULL') "donen: $r1"

# --- install.ps1 tarafi (kurulum kapisi) ---
$src = Get-Content -LiteralPath $installer -Raw
Assert 'installer_5_1_uyumlu' ($src -notmatch '(?im)^\s*#requires\s+-Version\s+7') 'install.ps1 #requires -Version 7 tasiyor'

$r2 = & powershell.exe -NoProfile -NonInteractive -Command ". '$installer' -PreflightOnly; if (Get-Command Invoke-BeyinPreflight -ErrorAction SilentlyContinue) { 'YUKLENDI' } else { 'YOK' }"
Assert 'installer_5_1_de_yuklenir' (("$r2" | Select-Object -Last 1).Trim() -eq 'YUKLENDI') "donen: $r2"

$r3 = Invoke-InChild 'pwsh' $stubDir ". '$installer' -PreflightOnly`n`$r = Find-BeyinPython`nif (`$null -eq `$r) { 'NULL' } else { `$r }"
Assert 'kapi_stubu_reddeder' ("$r3".Trim() -eq 'NULL') "donen: $r3"

if ($realPython) {
    $realDir = Split-Path -Parent $realPython

    $r4 = Invoke-InChild 'pwsh' "$stubDir;$realDir" ". '$lib'`n`$r = Get-BeyinPython`nif (`$null -eq `$r) { 'NULL' } else { `$r }"
    Assert 'stub_onde_olsa_da_gercek_secilir' ("$r4".Trim() -ne 'NULL' -and "$r4".Trim() -notlike "$stubDir*") "donen: $r4"

    # The 5.1 native-argument trap: PowerShell 5.1 strips embedded double quotes
    # when handing arguments to native commands, so a probe containing them made
    # the gate report Python missing on a machine that had it.
    $r5 = & powershell.exe -NoProfile -NonInteractive -Command ". '$installer' -PreflightOnly; `$p = Find-BeyinPython; if (`$null -eq `$p) { 'NULL' } else { 'BULUNDU' }"
    Assert 'kapi_5_1_de_gercek_pythonu_bulur' (("$r5" | Select-Object -Last 1).Trim() -eq 'BULUNDU') "donen: $r5"
}
else {
    Write-Host '  skip stub_onde_olsa_da_gercek_secilir -- makinede calisan python yok'
    Write-Host '  skip kapi_5_1_de_gercek_pythonu_bulur -- makinede calisan python yok'
}

Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ''
if ($failures.Count -gt 0) {
    Write-Host "BASARISIZ: $($failures.Count)/$total -- $($failures -join ', ')"
    exit 1
}
Write-Host "TAMAM: $total test gecti"
exit 0
