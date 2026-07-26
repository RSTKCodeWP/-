# Backend for the "HackRF Monitor" desktop shortcut (Windows counterpart of
# monitor_launcher.sh). (Re)starts the monitor — killing any running instance
# and sweep first — then opens the dashboard in the browser.
param([int]$Port = 8080)

$proj = Split-Path -Parent $MyInvocation.MyCommand.Path

# Kill any running webapp (python -m hackrf_api webapp) and sweep — the radio
# is single-user.
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
  Where-Object { $_.CommandLine -match 'hackrf_api\s+webapp' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-Process hackrf_sweep -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

# Prefer the project venv's python if it exists.
$py = Join-Path $proj '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

$p = Start-Process -PassThru -WindowStyle Hidden -FilePath $py `
       -ArgumentList @('-m','hackrf_api','webapp','--port',$Port) -WorkingDirectory $proj
$p.Id | Out-File -Encoding ascii (Join-Path $proj '.monitor.pid')

# Wait until the web app answers (up to ~10 s), then open the dashboard.
# Use 127.0.0.1, not localhost: on Windows "localhost" resolves to IPv6 ::1
# first, but the webapp binds IPv4 only, so a localhost probe/open hangs.
$url = "http://127.0.0.1:$Port/"
for ($i = 0; $i -lt 20; $i++) {
  try {
    Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1 | Out-Null
    Start-Process $url
    exit 0
  } catch {
    Start-Sleep -Milliseconds 500
  }
}

Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.MessageBox]::Show(
  "Monitor did not come up on $url - check that Python and the HackRF tools are installed (see README).",
  'HackRF Monitor failed to start') | Out-Null
exit 1
