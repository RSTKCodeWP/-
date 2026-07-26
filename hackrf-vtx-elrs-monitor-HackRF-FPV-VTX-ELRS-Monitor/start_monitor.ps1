# Starts the HackRF multi-band monitor (VTX 5 GHz + 2.4/900 MHz ELRS) in the
# background and opens the dashboard. The HackRF can only be used by one process
# at a time, so this first stops any running sweep.
#
#   .\start_monitor.ps1            # on :8080
#   .\start_monitor.ps1 -Port 9000
#
param([int]$Port = 8080)

$proj = Split-Path -Parent $MyInvocation.MyCommand.Path

Get-Process hackrf_sweep -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 400

$p = Start-Process -PassThru -WindowStyle Hidden -FilePath 'python' `
       -ArgumentList @('-m','hackrf_api','webapp','--port',$Port) -WorkingDirectory $proj
$p.Id | Out-File -Encoding ascii (Join-Path $proj '.monitor.pid')

Start-Sleep -Seconds 3
$url = "http://localhost:$Port/"
Start-Process $url
Write-Host "Multi-band monitor started (pid $($p.Id)) -> $url"
Write-Host "Quick checks:  python -m hackrf_api vtx   |   python -m hackrf_api elrs"
Write-Host "Stop:          Get-Content .monitor.pid | Stop-Process"
