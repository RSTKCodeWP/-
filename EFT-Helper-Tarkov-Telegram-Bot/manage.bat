@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

:: EFT Helper Bot - Management Script for Windows
:: Author: EFT Helper Team
:: Description: Interactive menu for managing the bot

title EFT Helper Bot - Management Tool

:menu
cls
echo ============================================================
echo   EFT Helper Bot - Management Menu
echo ============================================================
echo.
echo   [1]  Start bot (Docker)
echo   [2]  Stop bot
echo   [3]  Restart bot
echo   [4]  View logs (real-time)
echo   [5]  View logs (last 50 lines)
echo   [6]  Check status
echo   [7]  Rebuild Docker image
echo   [8]  Update and restart
echo   [9]  Stop and remove containers
echo   [10] View resource usage
echo.
echo   [11] Test API connection
echo   [12] Reset Telegram webhook
echo   [13] Backup database
echo   [14] Run local (Poetry)
echo   [15] Install dependencies (Poetry)
echo.
echo   [16] Clean Docker cache
echo   [17] View Docker images
echo   [18] Shell into container
echo.
echo   [0]  Exit
echo.
echo ============================================================
set /p choice="Select option: "

if "%choice%"=="1" goto start_docker
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto restart
if "%choice%"=="4" goto logs_follow
if "%choice%"=="5" goto logs_tail
if "%choice%"=="6" goto status
if "%choice%"=="7" goto rebuild
if "%choice%"=="8" goto update
if "%choice%"=="9" goto down
if "%choice%"=="10" goto stats
if "%choice%"=="11" goto test_api
if "%choice%"=="12" goto reset_webhook
if "%choice%"=="13" goto backup
if "%choice%"=="14" goto run_local
if "%choice%"=="15" goto install_deps
if "%choice%"=="16" goto clean_docker
if "%choice%"=="17" goto docker_images
if "%choice%"=="18" goto shell
if "%choice%"=="0" goto exit_script

echo Invalid option!
timeout /t 2 > nul
goto menu

:start_docker
cls
echo ============================================================
echo   Starting bot with Docker Compose...
echo ============================================================
echo.
docker-compose up -d
echo.
echo Bot started!
echo.
timeout /t 3 > nul
goto menu

:stop
cls
echo ============================================================
echo   Stopping bot...
echo ============================================================
echo.
docker-compose stop
echo.
echo Bot stopped!
echo.
timeout /t 2 > nul
goto menu

:restart
cls
echo ============================================================
echo   Restarting bot...
echo ============================================================
echo.
docker-compose restart
echo.
echo Bot restarted!
echo.
timeout /t 2 > nul
goto menu

:logs_follow
cls
echo ============================================================
echo   Viewing logs (real-time)
echo   Press Ctrl+C to stop
echo ============================================================
echo.
docker-compose logs -f
pause
goto menu

:logs_tail
cls
echo ============================================================
echo   Last 50 lines of logs
echo ============================================================
echo.
docker-compose logs --tail=50
echo.
pause
goto menu

:status
cls
echo ============================================================
echo   Bot Status
echo ============================================================
echo.
docker-compose ps
echo.
echo ============================================================
echo   Health Check
echo ============================================================
echo.
docker inspect eft-helper-bot --format="{{.State.Health.Status}}" 2>nul
if errorlevel 1 echo Container not running
echo.
pause
goto menu

:rebuild
cls
echo ============================================================
echo   Rebuilding Docker image...
echo ============================================================
echo.
docker-compose down
docker-compose build --no-cache
echo.
echo Image rebuilt!
echo.
echo Start bot? (Y/N)
set /p start_choice=
if /i "%start_choice%"=="Y" (
    docker-compose up -d
    echo Bot started!
)
timeout /t 2 > nul
goto menu

:update
cls
echo ============================================================
echo   Updating and restarting bot...
echo ============================================================
echo.
echo Stopping bot...
docker-compose down
echo.
echo Rebuilding image...
docker-compose build
echo.
echo Starting bot...
docker-compose up -d
echo.
echo Update complete!
echo.
timeout /t 3 > nul
goto menu

:down
cls
echo ============================================================
echo   Stopping and removing containers...
echo ============================================================
echo.
echo WARNING: This will stop the bot and remove containers.
echo Data and logs will be preserved.
echo.
echo Continue? (Y/N)
set /p down_choice=
if /i "%down_choice%"=="Y" (
    docker-compose down
    echo.
    echo Containers removed!
)
timeout /t 2 > nul
goto menu

:stats
cls
echo ============================================================
echo   Resource Usage
echo ============================================================
echo.
docker stats --no-stream eft-helper-bot
echo.
pause
goto menu

:test_api
cls
echo ============================================================
echo   Testing API Connection...
echo ============================================================
echo.
poetry run python scripts/test_quests_api.py
echo.
pause
goto menu

:reset_webhook
cls
echo ============================================================
echo   Resetting Telegram Webhook...
echo ============================================================
echo.
poetry run python scripts/reset_webhook.py
echo.
pause
goto menu

:backup
cls
echo ============================================================
echo   Creating Database Backup...
echo ============================================================
echo.
if not exist "backup" mkdir backup
set timestamp=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set timestamp=%timestamp: =0%
copy data\eft_helper.db backup\eft_helper_%timestamp%.db
echo.
echo Backup created: backup\eft_helper_%timestamp%.db
echo.
pause
goto menu

:run_local
cls
echo ============================================================
echo   Running bot locally with Poetry...
echo ============================================================
echo.
echo Stopping Docker bot first...
docker-compose stop
echo.
echo Starting local bot...
poetry run python main.py
pause
goto menu

:install_deps
cls
echo ============================================================
echo   Installing dependencies with Poetry...
echo ============================================================
echo.
poetry install
echo.
echo Dependencies installed!
echo.
timeout /t 2 > nul
goto menu

:clean_docker
cls
echo ============================================================
echo   Cleaning Docker Cache...
echo ============================================================
echo.
echo This will remove:
echo - Stopped containers
echo - Unused networks
echo - Dangling images
echo - Build cache
echo.
echo Continue? (Y/N)
set /p clean_choice=
if /i "%clean_choice%"=="Y" (
    docker system prune -f
    echo.
    echo Cache cleaned!
)
timeout /t 2 > nul
goto menu

:docker_images
cls
echo ============================================================
echo   Docker Images
echo ============================================================
echo.
docker images | findstr "efthelper\|REPOSITORY"
echo.
pause
goto menu

:shell
cls
echo ============================================================
echo   Opening shell in container...
echo ============================================================
echo.
docker-compose exec eft-helper-bot bash
goto menu

:exit_script
cls
echo.
echo Thank you for using EFT Helper Bot Management Tool!
echo.
timeout /t 2 > nul
exit /b 0

