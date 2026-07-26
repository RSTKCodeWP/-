# 📚 CoinFlow Bot Documentation

**Languages:** [English](#english) | [Русский](#russian)

Complete documentation for deploying and managing CoinFlow Bot.

---

<a name="english"></a>
## 📖 English Version

## 📖 Documentation Index

### Getting Started
- [Quick Start Guide](QUICK_START.md) - Setup and first run
- [Docker Guide](DOCKER_GUIDE.md) - Docker deployment (recommended)

### Reference
- [API Reference](API_REFERENCE.md) - Commands, services, database
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues

### Project Info
- [Changelog](CHANGELOG.md) - Version history
- [Main README](../README.md) - Project overview

---

## 🚀 Quick Deploy

### Docker (Recommended)

**Windows:**
```cmd
docker-run.bat
```

**Linux/Mac:**
```bash
chmod +x docker-run.sh
./docker-run.sh
```

### Manual

```bash
# Clone and install
git clone https://github.com/bobberdolle1/CoinFlow.git
cd CoinFlow
poetry install

# Configure
cp .env.example .env
# Edit .env and add TELEGRAM_BOT_TOKEN

# Run
poetry run python main.py
```

---

## 📋 Available Guides

| Guide | Description |
|-------|-------------|
| [Quick Start](QUICK_START.md) | Installation and configuration |
| [Docker Guide](DOCKER_GUIDE.md) | Docker deployment with Ollama |
| [API Reference](API_REFERENCE.md) | Bot commands and services |
| [Troubleshooting](TROUBLESHOOTING.md) | Solutions to common problems |
| [Changelog](CHANGELOG.md) | What's new in each version |

---

## 🆘 Need Help?

1. Check [Troubleshooting Guide](TROUBLESHOOTING.md)
2. Review [Docker Guide](DOCKER_GUIDE.md) for Docker issues
3. See [API Reference](API_REFERENCE.md) for commands
4. Open issue on [GitHub](https://github.com/bobberdolle1/CoinFlow/issues)

---

**Made with ❤️ for the community**

---
---

<a name="russian"></a>
## 📖 Русская версия

# 📚 Документация CoinFlow Bot

Полная документация по развертыванию и управлению ботом CoinFlow.

## 📖 Содержание документации

### Начало работы
- [Быстрый старт](QUICK_START.md) - Установка и настройка
- [Руководство Docker](DOCKER_GUIDE.md) - Развертывание Docker (рекомендуется)

### Справка
- [API документация](API_REFERENCE.md) - Команды, сервисы, БД
- [Решение проблем](TROUBLESHOOTING.md) - Типичные проблемы

### Информация о проекте
- [История изменений](CHANGELOG.md) - История версий
- [Основной README](../README.md) - Обзор проекта

---

## 🚀 Быстрое развертывание

### Docker (Рекомендуется)

**Windows:**
```cmd
docker-run.bat
```

**Linux/Mac:**
```bash
chmod +x docker-run.sh
./docker-run.sh
```

### Вручную

```bash
# Клонировать и установить
git clone https://github.com/bobberdolle1/CoinFlow.git
cd CoinFlow
poetry install

# Настроить
cp .env.example .env
# Отредактировать .env и добавить TELEGRAM_BOT_TOKEN

# Запустить
poetry run python main.py
```

---

## 📋 Доступные руководства

| Руководство | Описание |
|-------------|----------|
| [Быстрый старт](QUICK_START.md) | Установка и настройка |
| [Docker](DOCKER_GUIDE.md) | Развертывание с Ollama |
| [API](API_REFERENCE.md) | Команды и сервисы бота |
| [Решение проблем](TROUBLESHOOTING.md) | Решения типичных проблем |
| [История изменений](CHANGELOG.md) | Что нового в версиях |

---

## 🆘 Нужна помощь?

1. Проверьте [Решение проблем](TROUBLESHOOTING.md)
2. Просмотрите [Руководство по Docker](DOCKER_GUIDE.md)
3. См. [API документацию](API_REFERENCE.md)
4. Откройте issue на [GitHub](https://github.com/bobberdolle1/CoinFlow/issues)

---

**Сделано с ❤️ для сообщества**
