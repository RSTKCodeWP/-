@echo off
REM CoinFlow Bot v3.0 - Docker Quick Start for Windows
REM Author: bobberdolle1

setlocal EnableDelayedExpansion

echo.
echo ========================================
echo   CoinFlow Bot v3.0 - Docker Launcher
echo ========================================
echo.

REM Check Docker
echo [CHECK] Docker status...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running!
    echo.
    echo Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)
echo [OK] Docker is running
echo.

REM Check .env
echo [CHECK] Configuration...
if not exist .env (
    echo [WARN] .env file not found - creating from template
    copy .env.example .env >nul
    echo.
    echo [ACTION REQUIRED] Edit .env file:
    echo   1. Add your TELEGRAM_BOT_TOKEN
    echo   2. Add your ADMIN_IDS
    echo.
    echo Then run this script again.
    echo.
    pause
    exit /b 1
)

findstr /C:"YOUR_TELEGRAM_BOT_TOKEN_HERE" .env >nul
if not errorlevel 1 (
    echo [ERROR] TELEGRAM_BOT_TOKEN not configured!
    echo.
    echo Please edit .env file and add your bot token.
    echo.
    pause
    exit /b 1
)
echo [OK] Configuration found
echo.

REM Create directories
echo [SETUP] Creating directories...
if not exist data mkdir data
if not exist logs mkdir logs
echo [OK] Directories ready
echo.

REM Check Ollama
echo [CHECK] Ollama connection...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [WARN] Ollama not detected on localhost:11434
    echo.
    echo Make sure Ollama is running with qwen3:8b model
    echo.
    set /p "continue=Continue anyway? (y/n): "
    if /i "!continue!" neq "y" exit /b 1
)
echo [OK] Ollama is accessible
echo.

REM Build
echo [BUILD] Building Docker image (this may take 5-10 minutes)...
echo.
docker-compose build

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    echo.
    echo Try: docker-compose build --no-cache
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Build complete
echo.

REM Start
echo [START] Starting CoinFlow Bot...
docker-compose up -d

if errorlevel 1 (
    echo.
    echo [ERROR] Start failed!
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   CoinFlow Bot v3.0 is RUNNING!
echo ========================================
echo.
echo Useful commands:
echo   docker-compose logs -f    - View logs
echo   docker-compose restart    - Restart bot
echo   docker-compose down       - Stop bot
echo   docker-compose ps         - Check status
echo.
echo Logs location: .\logs\coinflow.log
echo Database: .\data\coinflow.db
echo.

timeout /t 5
exit /b 0

:logs
echo.
echo Showing logs (Press Ctrl+C to exit)...
docker-compose logs -f
goto end

:restart
echo.
echo Restarting CoinFlow bot...
docker-compose restart
echo [SUCCESS] Bot restarted
goto end

:clean
echo.
echo [WARNING] This will remove all containers and images!
set /p confirm="Are you sure? (y/n): "
if /i "%confirm%"=="y" (
    docker-compose down --rmi all --volumes
    echo [SUCCESS] Cleanup complete
) else (
    echo Cleanup cancelled
)
goto end

:end
echo.
pause
