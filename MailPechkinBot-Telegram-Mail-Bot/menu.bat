@echo off
color 0A
title MailPechkinBot - Management Menu

:menu
cls
echo ===============================================================
echo          MailPechkinBot - Management Menu                   
echo ===============================================================
echo.
echo  [1] Run bot (Poetry)
echo  [2] Build Docker image
echo  [3] Start with Docker Compose
echo  [4] Stop Docker container
echo  [5] Show container status
echo  [6] Show container logs
echo  [7] Restart container
echo  [8] Clean Docker (containers and images)
echo  [9] Install dependencies (Poetry)
echo  [10] Create .env file from example
echo  [11] Bot information
echo  [0] Exit
echo.
echo ===============================================================
set /p choice="Select option: "

if "%choice%"=="1" goto poetry_run
if "%choice%"=="2" goto docker_build
if "%choice%"=="3" goto docker_up
if "%choice%"=="4" goto docker_down
if "%choice%"=="5" goto docker_status
if "%choice%"=="6" goto docker_logs
if "%choice%"=="7" goto docker_restart
if "%choice%"=="8" goto docker_clean
if "%choice%"=="9" goto poetry_install
if "%choice%"=="10" goto create_env
if "%choice%"=="11" goto info
if "%choice%"=="0" goto exit
goto menu

:poetry_run
cls
echo ===============================================================
echo          Run bot with Poetry                           
echo ===============================================================
echo.
if not exist .env (
    echo WARNING: .env file not found!
    echo Create .env file with TELEGRAM_BOT_TOKEN
    echo.
    pause
    goto menu
)
echo Starting bot...
poetry run python bot.py
pause
goto menu

:docker_build
cls
echo ===============================================================
echo          Build Docker image                               
echo ===============================================================
echo.
echo Building Docker image...
docker-compose build
echo.
if %errorlevel% equ 0 (
    echo SUCCESS: Image built!
) else (
    echo ERROR: Build failed!
)
pause
goto menu

:docker_up
cls
echo ===============================================================
echo          Start with Docker Compose                        
echo ===============================================================
echo.
if not exist .env (
    echo WARNING: .env file not found!
    echo Create .env file with TELEGRAM_BOT_TOKEN
    echo.
    pause
    goto menu
)
echo Starting container...
docker-compose up -d
echo.
if %errorlevel% equ 0 (
    echo SUCCESS: Container started!
    echo Use option [6] to view logs
) else (
    echo ERROR: Failed to start container!
)
pause
goto menu

:docker_down
cls
echo ===============================================================
echo          Stop Docker container                        
echo ===============================================================
echo.
echo Stopping container...
docker-compose down
echo.
if %errorlevel% equ 0 (
    echo SUCCESS: Container stopped!
) else (
    echo ERROR: Failed to stop container!
)
pause
goto menu

:docker_status
cls
echo ===============================================================
echo          Docker container status                           
echo ===============================================================
echo.
docker-compose ps
echo.
echo ===============================================================
docker stats --no-stream mailpechkinbot 2>nul
if %errorlevel% neq 0 (
    echo WARNING: Container is not running
)
pause
goto menu

:docker_logs
cls
echo ===============================================================
echo          Docker container logs                             
echo ===============================================================
echo.
echo Showing last 50 lines of logs (Ctrl+C to exit)...
echo.
docker-compose logs --tail=50 -f
pause
goto menu

:docker_restart
cls
echo ===============================================================
echo          Restart Docker container                       
echo ===============================================================
echo.
echo Restarting container...
docker-compose restart
echo.
if %errorlevel% equ 0 (
    echo SUCCESS: Container restarted!
) else (
    echo ERROR: Failed to restart container!
)
pause
goto menu

:docker_clean
cls
echo ===============================================================
echo          Clean Docker                                     
echo ===============================================================
echo.
echo WARNING: This will remove all stopped containers and images!
set /p confirm="Continue? (y/n): "
if /i not "%confirm%"=="y" goto menu
echo.
echo Stopping containers...
docker-compose down
echo Removing images...
docker-compose down --rmi all --volumes
echo Cleaning system...
docker system prune -f
echo.
echo SUCCESS: Cleanup complete!
pause
goto menu

:poetry_install
cls
echo ===============================================================
echo          Install dependencies                             
echo ===============================================================
echo.
echo Checking Poetry installation...
poetry --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Poetry is not installed!
    echo Install Poetry: https://python-poetry.org/docs/#installation
    pause
    goto menu
)
echo.
echo Installing dependencies...
poetry install
echo.
if %errorlevel% equ 0 (
    echo SUCCESS: Dependencies installed!
) else (
    echo ERROR: Failed to install dependencies!
)
pause
goto menu

:create_env
cls
echo ===============================================================
echo          Create .env file                                
echo ===============================================================
echo.
if exist .env (
    echo WARNING: .env file already exists!
    set /p overwrite="Overwrite? (y/n): "
    if /i not "%overwrite%"=="y" goto menu
)
echo.
copy .env.example .env >nul 2>&1
if %errorlevel% equ 0 (
    echo SUCCESS: .env file created from .env.example
    echo.
    echo Edit .env file and add your TELEGRAM_BOT_TOKEN
    echo Get token: https://t.me/BotFather
) else (
    echo ERROR: .env.example file not found!
)
pause
goto menu

:info
cls
echo ===============================================================
echo          MailPechkinBot - Information                        
echo ===============================================================
echo.
echo Telegram bot for temporary email
echo Version: 1.0.0
echo.
echo Requirements:
echo   - Python 3.11+
echo   - Poetry (for local run)
echo   - Docker and Docker Compose (for containerization)
echo.
echo Quick start:
echo   1. Create .env file (option 10)
echo   2. Add TELEGRAM_BOT_TOKEN to .env
echo   3. Run bot (option 1 or 3)
echo.
echo Documentation: README.md
echo Bugs: GitHub Issues
echo.
pause
goto menu

:exit
cls
echo.
echo Goodbye!
timeout /t 2 >nul
exit
