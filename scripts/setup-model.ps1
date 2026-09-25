param([switch]$Cpu)
$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $projectRoot
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.runtime/python'
$env:UV_CACHE_DIR = Join-Path $projectRoot '.cache/uv-model'
$env:HF_HOME = Join-Path $projectRoot '.cache/huggingface'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is required. Install uv, then rerun scripts/setup-model.ps1.'
}
$modelPython = Join-Path $projectRoot '.venv-model/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $modelPython)) {
    & uv venv .venv-model --python 3.11 --python-preference only-managed
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python 3.11 model environment.' }
}
& $modelPython -c 'import sys; assert sys.version_info[:2] == (3, 11), "Model runtime requires Python 3.11"'
if ($LASTEXITCODE -ne 0) { throw 'Existing model environment is not Python 3.11; choose a new environment before setup.' }
$torchVariant = if ($Cpu) { 'cpu' } else { 'cu126' }
$torchIndex = "https://download.pytorch.org/whl/$torchVariant"
# Include the local version so rerunning setup can switch CPU/CUDA wheels.
& uv pip install --python $modelPython "torch==2.8.0+$torchVariant" "torchaudio==2.8.0+$torchVariant" --index-url $torchIndex
if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }
& uv pip install --python $modelPython transformers==4.45.2 huggingface-hub==0.36.0 safetensors==0.5.3 numpy==1.24.3 scipy==1.13.1 mir_eval==0.8.2 pretty_midi==0.2.10 mido==1.3.3 setuptools==78.1.1
if ($LASTEXITCODE -ne 0) { throw 'Model dependency installation failed.' }
& $modelPython workers/prepare_models.py
if ($LASTEXITCODE -ne 0) { throw 'Model snapshots are incomplete. See the download error above.' }
& $modelPython workers/prepare_models.py --probe
if ($LASTEXITCODE -ne 0) { throw 'Model runtime validation failed.' }
Write-Host 'SheetSage2 setup complete. Restart the Web UI. The first inference is the hardware smoke test.'
