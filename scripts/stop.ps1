$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $projectRoot 'data\processes.json'
if (!(Test-Path -LiteralPath $pidPath)) { throw 'No saved service process IDs. Stop manually started terminals directly.' }
$savedPids = Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json
foreach ($service in @('backend', 'frontend')) {
    $servicePid = $savedPids.$service
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$servicePid" -ErrorAction SilentlyContinue
    if (!$process) { continue }
    $ownedBackend = $service -eq 'backend' -and $process.ExecutablePath -eq (Join-Path $projectRoot '.venv\Scripts\python.exe') -and $process.CommandLine.Contains('backend.main:app')
    $ownedFrontend = $service -eq 'frontend' -and $process.CommandLine.Contains((Join-Path $projectRoot 'frontend\node_modules\next\dist\bin\next'))
    if ($ownedBackend -or $ownedFrontend) {
        Stop-Process -Id $servicePid
        Write-Host "Stopped $service ($servicePid). Any active task will be marked interrupted on restart."
    } else { Write-Warning "PID $servicePid no longer matches this project's $service; left untouched." }
}
