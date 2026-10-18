$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    python -m pip install uv
    if ($LASTEXITCODE -ne 0) { throw 'uv installation failed' }
    python -m uv sync --frozen
    if ($LASTEXITCODE -ne 0) { throw 'Python dependencies failed' }
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        npm.cmd install
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependencies failed' }
        npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    } finally { Pop-Location }
    Write-Host 'Setup complete. Run scripts/start.ps1, then open http://127.0.0.1:3000/settings'
} finally { Pop-Location }
