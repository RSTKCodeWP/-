@echo off
echo Starting MailPechkinBot with Poetry...
echo.
echo Checking Poetry installation...
poetry --version
if errorlevel 1 (
    echo Poetry is not installed!
    echo Please install Poetry: https://python-poetry.org/docs/#installation
    pause
    exit /b 1
)
echo.
echo Starting bot...
poetry run python bot.py
pause
