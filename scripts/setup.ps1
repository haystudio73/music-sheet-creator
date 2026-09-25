param([switch]$SkipFrontend)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:UV_CACHE_DIR = Join-Path $projectRoot '.cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.runtime\python'
$env:npm_config_cache = Join-Path $projectRoot '.cache\npm'
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Chua co uv. Cai uv theo https://docs.astral.sh/uv/getting-started/installation/ roi chay lai.'
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
    & uv venv --python 3.12 --managed-python .venv
    if ($LASTEXITCODE -ne 0) { throw 'Khong tao duoc Python runtime.' }
}
& uv pip sync --python $pythonExe requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Khong cai duoc thu vien Python.' }

if (-not $SkipFrontend) {
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Can Node.js 22+ va npm de build Web UI.' }
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'npm ci that bai.' }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Build giao dien that bai.' }
    } finally { Pop-Location }
}
Write-Host 'Da cai Web UI va backend. Chay Start.cmd de mo ung dung.'
Write-Host 'SheetSage2 duoc cai rieng bang scripts/setup-model.ps1; xem docs/model-setup.md.'
