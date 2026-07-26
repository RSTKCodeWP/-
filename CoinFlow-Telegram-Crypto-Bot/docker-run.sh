#!/bin/bash

# CoinFlow Bot - Docker Runner for Linux/Mac
# This script helps you run CoinFlow bot using Docker

set -e

echo "========================================"
echo "  CoinFlow Bot v2.0 - Docker Runner"
echo "========================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed"

# Check Docker
echo "[CHECK] Docker status..."
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}[ERROR]${NC} Docker is not running!"
    echo ""
    echo "Please start Docker and try again."
    echo ""
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Docker is running"
echo ""

# Check .env
echo "[CHECK] Configuration..."
if [ ! -f .env ]; then
    echo -e "${YELLOW}[WARN]${NC} .env file not found - creating from template"
    cp .env.example .env
    echo ""
    echo "[ACTION REQUIRED] Edit .env file:"
    echo "  1. Add your TELEGRAM_BOT_TOKEN"
    echo "  2. Add your ADMIN_IDS"
    echo ""
    echo "Then run this script again."
    echo ""
    exit 1
fi

if grep -q "YOUR_TELEGRAM_BOT_TOKEN_HERE" .env; then
    echo -e "${RED}[ERROR]${NC} TELEGRAM_BOT_TOKEN not configured!"
    echo ""
    echo "Please edit .env file and add your bot token."
    echo ""
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Configuration found"
echo ""

# Create directories
echo "[SETUP] Creating directories..."
mkdir -p data logs
echo -e "${GREEN}[OK]${NC} Directories ready"
echo ""

# Check Ollama
echo "[CHECK] Ollama connection..."
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "${YELLOW}[WARN]${NC} Ollama not detected on localhost:11434"
    echo ""
    echo "Make sure Ollama is running with qwen3:8b model"
    echo ""
    read -p "Continue anyway? (y/n): " continue
    if [ "$continue" != "y" ] && [ "$continue" != "Y" ]; then
        exit 1
    fi
else
    echo -e "${GREEN}[OK]${NC} Ollama is accessible"
fi
echo ""

# Build
echo "[BUILD] Building Docker image (this may take 5-10 minutes)..."
echo ""
if ! docker-compose build; then
    echo ""
    echo -e "${RED}[ERROR]${NC} Build failed!"
    echo ""
    echo "Try: docker-compose build --no-cache"
    echo ""
    exit 1
fi

echo ""
echo -e "${GREEN}[OK]${NC} Build complete"
echo ""

# Start
echo "[START] Starting CoinFlow Bot..."
if ! docker-compose up -d; then
    echo ""
    echo -e "${RED}[ERROR]${NC} Start failed!"
    echo ""
    exit 1
fi

echo ""
echo "========================================"
echo "  CoinFlow Bot v3.0 is RUNNING!"
echo "========================================"
echo ""
echo "Useful commands:"
echo "  docker-compose logs -f    - View logs"
echo "  docker-compose restart    - Restart bot"
echo "  docker-compose down       - Stop bot"
echo "  docker-compose ps         - Check status"
echo ""
echo "Logs location: ./logs/coinflow.log"
echo "Database: ./data/coinflow.db"
echo ""

sleep 3

# Function to display menu
show_menu() {
    echo ""
    echo "What would you like to do?"
    echo ""
    echo "1. Build and start the bot"
    echo "2. Stop the bot"
    echo "3. View logs"
    echo "4. Restart the bot"
    echo "5. Remove containers and images"
    echo "6. Exit"
    echo ""
    read -p "Enter your choice (1-6): " choice
    echo ""
}

# Function to build and start
build_start() {
    echo "Building and starting CoinFlow bot..."
    docker-compose up -d --build
    if [ $? -eq 0 ]; then
        echo ""
        echo "[SUCCESS] Bot is now running!"
        echo "Use 'docker-compose logs -f' to view logs"
    else
        echo "[ERROR] Failed to start the bot"
        exit 1
    fi
}

# Function to stop
stop_bot() {
    echo "Stopping CoinFlow bot..."
    docker-compose down
    echo "[SUCCESS] Bot stopped"
}

# Function to view logs
view_logs() {
    echo "Showing logs (Press Ctrl+C to exit)..."
    docker-compose logs -f
}

# Function to restart
restart_bot() {
    echo "Restarting CoinFlow bot..."
    docker-compose restart
    echo "[SUCCESS] Bot restarted"
}

# Function to clean
clean_all() {
    echo "[WARNING] This will remove all containers and images!"
    read -p "Are you sure? (y/n): " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        docker-compose down --rmi all --volumes
        echo "[SUCCESS] Cleanup complete"
    else
        echo "Cleanup cancelled"
    fi
}

# Main loop
while true; do
    show_menu
    case $choice in
        1)
            build_start
            break
            ;;
        2)
            stop_bot
            break
            ;;
        3)
            view_logs
            break
            ;;
        4)
            restart_bot
            break
            ;;
        5)
            clean_all
            break
            ;;
        6)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid choice! Please enter 1-6"
            ;;
    esac
done
