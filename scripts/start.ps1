param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Chay scripts/setup.ps1 truoc.' }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) { throw 'Chua build Web UI. Chay scripts/setup.ps1.' }
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'
$url = 'http://127.0.0.1:8765'
$existing = $null
try { $existing = Invoke-RestMethod "$url/api/health" -TimeoutSec 2 } catch { }
if ($existing -and $existing.status -eq 'ok' -and $existing.version) {
    Write-Host "Ung dung da chay tai $url"
    if (-not $NoBrowser) { Start-Process $url }
    exit 0
}
Write-Host "Sheet Studio: $url"
Write-Host 'Giu cua so nay mo; Ctrl+C de dung backend. Audio va du lieu nam trong data/.'
if (-not $NoBrowser) {
    $browserJob = Start-Job -ScriptBlock {
        param($targetUrl)
        for ($i = 0; $i -lt 30; $i++) {
            try {
                $check = Invoke-RestMethod "$targetUrl/api/health" -TimeoutSec 1
                if ($check.status -eq 'ok') { Start-Process $targetUrl; break }
            } catch { }
            Start-Sleep -Seconds 1
        }
    } -ArgumentList $url
}
try { & $pythonExe -m uvicorn backend.app:app --host 127.0.0.1 --port 8765 --reload }
finally {
    if ($browserJob) { Stop-Job $browserJob -ErrorAction SilentlyContinue; Remove-Job $browserJob -Force -ErrorAction SilentlyContinue }
}
