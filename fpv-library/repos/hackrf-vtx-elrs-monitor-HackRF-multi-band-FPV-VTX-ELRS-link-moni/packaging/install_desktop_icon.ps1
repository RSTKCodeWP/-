# Installs a "HackRF Monitor" shortcut on the Desktop (Windows counterpart of
# install_desktop_icon.sh). Double-clicking it (re)starts the multi-band
# monitor via monitor_launcher.ps1 and opens the dashboard. Safe to re-run;
# replaces any existing shortcut.
#
#   powershell -File packaging\install_desktop_icon.ps1
#
# Uses packaging\hackrf_monitor.ico (committed to the repo) for the icon.
$proj = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'HackRF Monitor.lnk'

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = 'powershell.exe'
$lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$proj\monitor_launcher.ps1`""
$lnk.WorkingDirectory = $proj
$lnk.Description = 'Restart the HackRF multi-band monitor and open the dashboard'
$lnk.WindowStyle = 7  # minimized (the launcher itself runs hidden)

$ico = Join-Path $proj 'packaging\hackrf_monitor.ico'
if (Test-Path $ico) { $lnk.IconLocation = "$ico,0" }

$lnk.Save()
Write-Host "Installed: $lnkPath"
