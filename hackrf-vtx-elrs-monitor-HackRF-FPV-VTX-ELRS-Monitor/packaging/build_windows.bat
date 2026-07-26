@echo off
REM Build a standalone, self-contained Windows .exe of the HackRF monitor.
REM Bundles the vendored hackrf_*.exe + DLLs (via bootstrap_vendor.py) so the
REM target machine needs nothing installed.
REM
REM   packaging\build_windows.bat   ->  dist\hackrf-monitor-windows.exe
REM
REM Requires: Python 3 on PATH. Run from the repo root or this folder.
setlocal
cd /d "%~dp0\.."

python -m pip install --upgrade pip || goto :err
pip install -r requirements.txt pyinstaller || goto :err

echo ==^> Fetching vendored HackRF binaries
python bootstrap_vendor.py || goto :err

echo ==^> Building standalone .exe
pyinstaller --noconfirm --onefile --name hackrf-monitor-windows ^
  --add-data "vendor/bin;hackrf_tools" ^
  --exclude-module matplotlib --exclude-module tkinter ^
  --exclude-module PyQt5 --exclude-module PySide6 --exclude-module IPython ^
  monitor_app.py || goto :err

echo.
echo ==^> Built: dist\hackrf-monitor-windows.exe
goto :eof

:err
echo BUILD FAILED
exit /b 1
