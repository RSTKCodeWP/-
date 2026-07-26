#!/bin/bash

# EFT Helper Bot - Management Script for Linux/Mac
# Author: EFT Helper Team
# Description: Interactive menu for managing the bot

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    clear
    echo "============================================================"
    echo "  EFT Helper Bot - Management Menu"
    echo "============================================================"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

pause() {
    echo ""
    read -p "Press Enter to continue..."
}

# Menu functions
show_menu() {
    print_header
    echo ""
    echo "  [1]  Start bot (Docker)"
    echo "  [2]  Stop bot"
    echo "  [3]  Restart bot"
    echo "  [4]  View logs (real-time)"
    echo "  [5]  View logs (last 50 lines)"
    echo "  [6]  Check status"
    echo "  [7]  Rebuild Docker image"
    echo "  [8]  Update and restart"
    echo "  [9]  Stop and remove containers"
    echo "  [10] View resource usage"
    echo ""
    echo "  [11] Test API connection"
    echo "  [12] Reset Telegram webhook"
    echo "  [13] Backup database"
    echo "  [14] Run local (Poetry)"
    echo "  [15] Install dependencies (Poetry)"
    echo ""
    echo "  [16] Clean Docker cache"
    echo "  [17] View Docker images"
    echo "  [18] Shell into container"
    echo ""
    echo "  [0]  Exit"
    echo ""
    echo "============================================================"
    read -p "Select option: " choice
    echo ""
    
    case $choice in
        1) start_docker ;;
        2) stop_bot ;;
        3) restart_bot ;;
        4) logs_follow ;;
        5) logs_tail ;;
        6) check_status ;;
        7) rebuild_image ;;
        8) update_bot ;;
        9) down_containers ;;
        10) show_stats ;;
        11) test_api ;;
        12) reset_webhook ;;
        13) backup_database ;;
        14) run_local ;;
        15) install_deps ;;
        16) clean_docker ;;
        17) docker_images ;;
        18) shell_container ;;
        0) exit_script ;;
        *) 
            print_error "Invalid option!"
            sleep 2
            show_menu
            ;;
    esac
}

start_docker() {
    print_header
    echo ""
    print_info "Starting bot with Docker Compose..."
    echo ""
    
    if docker-compose up -d; then
        print_success "Bot started!"
    else
        print_error "Failed to start bot!"
    fi
    
    sleep 2
    show_menu
}

stop_bot() {
    print_header
    echo ""
    print_info "Stopping bot..."
    echo ""
    
    if docker-compose stop; then
        print_success "Bot stopped!"
    else
        print_error "Failed to stop bot!"
    fi
    
    sleep 2
    show_menu
}

restart_bot() {
    print_header
    echo ""
    print_info "Restarting bot..."
    echo ""
    
    if docker-compose restart; then
        print_success "Bot restarted!"
    else
        print_error "Failed to restart bot!"
    fi
    
    sleep 2
    show_menu
}

logs_follow() {
    print_header
    echo ""
    print_info "Viewing logs (real-time)"
    print_warning "Press Ctrl+C to stop"
    echo ""
    
    docker-compose logs -f
    pause
    show_menu
}

logs_tail() {
    print_header
    echo ""
    print_info "Last 50 lines of logs"
    echo ""
    
    docker-compose logs --tail=50
    pause
    show_menu
}

check_status() {
    print_header
    echo ""
    print_info "Bot Status"
    echo ""
    docker-compose ps
    echo ""
    echo "============================================================"
    echo "  Health Check"
    echo "============================================================"
    echo ""
    
    if docker inspect eft-helper-bot --format='{{.State.Health.Status}}' 2>/dev/null; then
        print_success "Container is running"
    else
        print_warning "Container not running"
    fi
    
    pause
    show_menu
}

rebuild_image() {
    print_header
    echo ""
    print_info "Rebuilding Docker image..."
    echo ""
    
    docker-compose down
    
    if docker-compose build --no-cache; then
        print_success "Image rebuilt!"
        echo ""
        read -p "Start bot? (y/n): " start_choice
        if [[ "$start_choice" == "y" ]] || [[ "$start_choice" == "Y" ]]; then
            docker-compose up -d
            print_success "Bot started!"
        fi
    else
        print_error "Failed to rebuild image!"
    fi
    
    sleep 2
    show_menu
}

update_bot() {
    print_header
    echo ""
    print_info "Updating and restarting bot..."
    echo ""
    
    print_info "Stopping bot..."
    docker-compose down
    echo ""
    
    print_info "Rebuilding image..."
    docker-compose build
    echo ""
    
    print_info "Starting bot..."
    docker-compose up -d
    echo ""
    
    print_success "Update complete!"
    sleep 2
    show_menu
}

down_containers() {
    print_header
    echo ""
    print_warning "WARNING: This will stop the bot and remove containers."
    print_info "Data and logs will be preserved."
    echo ""
    read -p "Continue? (y/n): " down_choice
    
    if [[ "$down_choice" == "y" ]] || [[ "$down_choice" == "Y" ]]; then
        docker-compose down
        print_success "Containers removed!"
    fi
    
    sleep 2
    show_menu
}

show_stats() {
    print_header
    echo ""
    print_info "Resource Usage"
    echo ""
    
    docker stats --no-stream eft-helper-bot
    pause
    show_menu
}

test_api() {
    print_header
    echo ""
    print_info "Testing API Connection..."
    echo ""
    
    poetry run python scripts/test_quests_api.py
    pause
    show_menu
}

reset_webhook() {
    print_header
    echo ""
    print_info "Resetting Telegram Webhook..."
    echo ""
    
    poetry run python scripts/reset_webhook.py
    pause
    show_menu
}

backup_database() {
    print_header
    echo ""
    print_info "Creating Database Backup..."
    echo ""
    
    mkdir -p backup
    timestamp=$(date +"%Y%m%d_%H%M%S")
    cp data/eft_helper.db backup/eft_helper_${timestamp}.db
    
    print_success "Backup created: backup/eft_helper_${timestamp}.db"
    pause
    show_menu
}

run_local() {
    print_header
    echo ""
    print_info "Running bot locally with Poetry..."
    echo ""
    
    print_info "Stopping Docker bot first..."
    docker-compose stop
    echo ""
    
    print_info "Starting local bot..."
    poetry run python main.py
    pause
    show_menu
}

install_deps() {
    print_header
    echo ""
    print_info "Installing dependencies with Poetry..."
    echo ""
    
    if poetry install; then
        print_success "Dependencies installed!"
    else
        print_error "Failed to install dependencies!"
    fi
    
    sleep 2
    show_menu
}

clean_docker() {
    print_header
    echo ""
    print_info "This will remove:"
    echo "  - Stopped containers"
    echo "  - Unused networks"
    echo "  - Dangling images"
    echo "  - Build cache"
    echo ""
    read -p "Continue? (y/n): " clean_choice
    
    if [[ "$clean_choice" == "y" ]] || [[ "$clean_choice" == "Y" ]]; then
        docker system prune -f
        print_success "Cache cleaned!"
    fi
    
    sleep 2
    show_menu
}

docker_images() {
    print_header
    echo ""
    print_info "Docker Images"
    echo ""
    
    docker images | grep -E "efthelper|REPOSITORY"
    pause
    show_menu
}

shell_container() {
    print_header
    echo ""
    print_info "Opening shell in container..."
    echo ""
    
    docker-compose exec eft-helper-bot bash
    show_menu
}

exit_script() {
    clear
    echo ""
    print_success "Thank you for using EFT Helper Bot Management Tool!"
    echo ""
    sleep 1
    exit 0
}

# Main
main() {
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed!"
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed!"
        exit 1
    fi
    
    # Show menu
    show_menu
}

# Run main
main

