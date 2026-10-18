$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$nextPath = Join-Path $projectRoot 'frontend\node_modules\next\dist\bin\next'
if (!(Test-Path -LiteralPath $pythonPath) -or !(Test-Path -LiteralPath $nextPath)) { throw 'Run scripts/setup.ps1 first.' }
if (!(Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\.next\BUILD_ID'))) { throw 'Run npm.cmd run build in frontend first.' }
foreach ($port in @(3000, 8000)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "Port $port is already in use. Existing service was not changed." }
}
$dataPath = Join-Path $projectRoot 'data'
New-Item -ItemType Directory -Force -Path $dataPath | Out-Null
$backend = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000', '--workers', '1') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dataPath 'backend.log') -RedirectStandardError (Join-Path $dataPath 'backend-error.log')
try {
    $nodePath = (Get-Command node.exe).Source
    $frontend = Start-Process -FilePath $nodePath -ArgumentList @(('"' + $nextPath + '"'), 'start', '--hostname', '127.0.0.1', '--port', '3000') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dataPath 'frontend.log') -RedirectStandardError (Join-Path $dataPath 'frontend-error.log')
    @{ backend = $backend.Id; frontend = $frontend.Id } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $dataPath 'processes.json') -Encoding utf8
    Write-Host 'SaiTan AI: http://127.0.0.1:3000'
    Write-Host 'Settings: http://127.0.0.1:3000/settings'
    Write-Host 'API docs: http://127.0.0.1:8000/docs'
} catch {
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
    throw
}
