#requires -Version 7.0
<#
    Detach a pre-compaction flush without changing live session state.
    Windows port of pre-compact.sh.

    Live session state (session_start_time, prompt_count) is deliberately NOT
    touched here: the session is still running.
#>

Set-StrictMode -Version Latest

# pre-compact.sh:2
if (-not [string]::IsNullOrEmpty($env:BEYIN_INVOKED_BY)) { exit 0 }

# pre-compact.sh:5-6
. (Join-Path $PSScriptRoot 'lib.ps1')

# A PreCompact failure must never block compaction, so everything is swallowed.
try {
    $raw = [Console]::In.ReadToEnd()

    # pre-compact.sh:8-24 -- write the payload, then launch the engine detached.
    $result = Start-BeyinFlush -RawPayload $raw -Reason 'precompact' -VaultRoot $script:BeyinProjectDir

    if ($result -ne 'baslatildi') {
        # Durable diagnostic; no bash equivalent. The emitted warning below dies
        # with the session, this line does not.
        Write-BeyinFlushError -Reason 'precompact' -Result $result

        if ($result -eq 'python-yok') {
            # pre-compact.sh:20-22 -- upstream's marker and warning, kept as-is
            # so anything watching for python3-missing still sees it.
            Set-BeyinPythonMissing
            Write-BeyinEmit -Event 'PreCompact' `
                -Text 'Beyin sıkıştırma öncesi özeti başlatılamadı: python3 bulunamadı. beyin-doktor çalıştır.'
        }
    }
}
catch { }

exit 0
