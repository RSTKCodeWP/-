#!/bin/bash

# Цвета для красивого вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Функция для отображения заголовка
show_header() {
    clear
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║        ${GREEN}MailPechkinBot - Меню управления${CYAN}                   ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Функция для паузы
pause() {
    echo ""
    read -p "Нажмите Enter для продолжения..."
}

# Проверка .env файла
check_env() {
    if [ ! -f .env ]; then
        echo -e "${YELLOW}⚠️  Внимание: файл .env не найден!${NC}"
        echo "Создайте файл .env с TELEGRAM_BOT_TOKEN"
        pause
        return 1
    fi
    return 0
}

# 1. Запуск через Poetry
poetry_run() {
    show_header
    echo -e "${CYAN}║        Запуск бота через Poetry${CYAN}                           ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    check_env || return
    
    echo -e "${GREEN}🚀 Запускаю бота...${NC}"
    poetry run python bot.py
    pause
}

# 2. Сборка Docker образа
docker_build() {
    show_header
    echo -e "${CYAN}║        Сборка Docker образа${CYAN}                               ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${BLUE}🔨 Собираю Docker образ...${NC}"
    docker-compose build
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Образ успешно собран!${NC}"
    else
        echo -e "${RED}❌ Ошибка при сборке образа!${NC}"
    fi
    pause
}

# 3. Запуск через Docker Compose
docker_up() {
    show_header
    echo -e "${CYAN}║        Запуск через Docker Compose${CYAN}                        ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    check_env || return
    
    echo -e "${GREEN}🏃 Запускаю контейнер...${NC}"
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Контейнер успешно запущен!${NC}"
        echo -e "${BLUE}📋 Используйте опцию [6] для просмотра логов${NC}"
    else
        echo -e "${RED}❌ Ошибка при запуске контейнера!${NC}"
    fi
    pause
}

# 4. Остановка контейнера
docker_down() {
    show_header
    echo -e "${CYAN}║        Остановка Docker контейнера${CYAN}                        ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${YELLOW}🛑 Останавливаю контейнер...${NC}"
    docker-compose down
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Контейнер остановлен!${NC}"
    else
        echo -e "${RED}❌ Ошибка при остановке контейнера!${NC}"
    fi
    pause
}

# 5. Статус контейнера
docker_status() {
    show_header
    echo -e "${CYAN}║        Статус Docker контейнера${CYAN}                           ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    docker-compose ps
    echo ""
    echo "══════════════════════════════════════════════════════════"
    docker stats --no-stream mailpechkinbot 2>/dev/null
    
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}⚠️  Контейнер не запущен${NC}"
    fi
    pause
}

# 6. Логи контейнера
docker_logs() {
    show_header
    echo -e "${CYAN}║        Логи Docker контейнера${CYAN}                             ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${BLUE}📋 Показываю последние 50 строк логов (Ctrl+C для выхода)...${NC}"
    echo ""
    docker-compose logs --tail=50 -f
    pause
}

# 7. Перезапуск контейнера
docker_restart() {
    show_header
    echo -e "${CYAN}║        Перезапуск Docker контейнера${CYAN}                       ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${BLUE}🔄 Перезапускаю контейнер...${NC}"
    docker-compose restart
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Контейнер перезапущен!${NC}"
    else
        echo -e "${RED}❌ Ошибка при перезапуске контейнера!${NC}"
    fi
    pause
}

# 8. Очистка Docker
docker_clean() {
    show_header
    echo -e "${CYAN}║        Очистка Docker${CYAN}                                     ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${RED}⚠️  ВНИМАНИЕ: Это удалит все остановленные контейнеры и образы!${NC}"
    read -p "Продолжить? (y/n): " confirm
    
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        return
    fi
    
    echo ""
    echo -e "${YELLOW}🧹 Останавливаю контейнеры...${NC}"
    docker-compose down
    
    echo -e "${YELLOW}🧹 Удаляю образы...${NC}"
    docker-compose down --rmi all --volumes
    
    echo -e "${YELLOW}🧹 Очищаю систему...${NC}"
    docker system prune -f
    
    echo ""
    echo -e "${GREEN}✅ Очистка завершена!${NC}"
    pause
}

# 9. Установка зависимостей
poetry_install() {
    show_header
    echo -e "${CYAN}║        Установка зависимостей${CYAN}                             ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${BLUE}📦 Проверяю установку Poetry...${NC}"
    if ! command -v poetry &> /dev/null; then
        echo -e "${RED}❌ Poetry не установлен!${NC}"
        echo -e "${BLUE}📖 Установите Poetry: https://python-poetry.org/docs/#installation${NC}"
        pause
        return
    fi
    
    echo ""
    echo -e "${BLUE}📦 Устанавливаю зависимости...${NC}"
    poetry install
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Зависимости установлены!${NC}"
    else
        echo -e "${RED}❌ Ошибка при установке зависимостей!${NC}"
    fi
    pause
}

# 10. Создание .env файла
create_env() {
    show_header
    echo -e "${CYAN}║        Создание .env файла${CYAN}                                ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    if [ -f .env ]; then
        echo -e "${YELLOW}⚠️  Файл .env уже существует!${NC}"
        read -p "Перезаписать? (y/n): " overwrite
        if [ "$overwrite" != "y" ] && [ "$overwrite" != "Y" ]; then
            return
        fi
    fi
    
    echo ""
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ Файл .env создан из .env.example${NC}"
        echo ""
        echo -e "${BLUE}📝 Отредактируйте файл .env и добавьте ваш TELEGRAM_BOT_TOKEN${NC}"
        echo -e "${PURPLE}💡 Получить токен: https://t.me/BotFather${NC}"
    else
        echo -e "${RED}❌ Ошибка: файл .env.example не найден!${NC}"
    fi
    pause
}

# 11. Информация о боте
show_info() {
    show_header
    echo -e "${CYAN}║        MailPechkinBot - Информация${CYAN}                        ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}📧 Telegram-бот для работы с временной почтой${NC}"
    echo -e "${BLUE}🔧 Версия: 1.0.0${NC}"
    echo ""
    echo -e "${YELLOW}📋 Требования:${NC}"
    echo "  • Python 3.11+"
    echo "  • Poetry (для локального запуска)"
    echo "  • Docker и Docker Compose (для контейнеризации)"
    echo ""
    echo -e "${PURPLE}🚀 Быстрый старт:${NC}"
    echo "  1. Создайте .env файл (опция 10)"
    echo "  2. Добавьте TELEGRAM_BOT_TOKEN в .env"
    echo "  3. Запустите бота (опция 1 или 3)"
    echo ""
    echo -e "${CYAN}📖 Документация: README.md${NC}"
    echo -e "${CYAN}🐛 Баги: GitHub Issues${NC}"
    echo ""
    pause
}

# Главное меню
main_menu() {
    while true; do
        show_header
        echo -e " ${GREEN}[1]${NC} 🚀 Запустить бота (Poetry)"
        echo -e " ${GREEN}[2]${NC} 🐳 Собрать Docker образ"
        echo -e " ${GREEN}[3]${NC} 🏃 Запустить через Docker Compose"
        echo -e " ${GREEN}[4]${NC} 🛑 Остановить Docker контейнер"
        echo -e " ${GREEN}[5]${NC} 📊 Показать статус контейнера"
        echo -e " ${GREEN}[6]${NC} 📋 Показать логи контейнера"
        echo -e " ${GREEN}[7]${NC} 🔄 Перезапустить контейнер"
        echo -e " ${GREEN}[8]${NC} 🧹 Очистить Docker (контейнеры и образы)"
        echo -e " ${GREEN}[9]${NC} 📦 Установить зависимости (Poetry)"
        echo -e " ${GREEN}[10]${NC} 🔧 Создать .env файл из примера"
        echo -e " ${GREEN}[11]${NC} ℹ️  Информация о боте"
        echo -e " ${RED}[0]${NC} ❌ Выход"
        echo ""
        echo "══════════════════════════════════════════════════════════"
        read -p "Выберите опцию: " choice
        
        case $choice in
            1) poetry_run ;;
            2) docker_build ;;
            3) docker_up ;;
            4) docker_down ;;
            5) docker_status ;;
            6) docker_logs ;;
            7) docker_restart ;;
            8) docker_clean ;;
            9) poetry_install ;;
            10) create_env ;;
            11) show_info ;;
            0) 
                clear
                echo ""
                echo -e "${GREEN}👋 До свидания!${NC}"
                sleep 1
                exit 0
                ;;
            *) 
                echo -e "${RED}❌ Неверная опция!${NC}"
                sleep 1
                ;;
        esac
    done
}

# Запуск главного меню
main_menu
