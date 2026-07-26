# 🚀 Quick Start Guide - CoinFlow v2.0

Get your CoinFlow bot running in 5 minutes!

[English](#english) | [Русский](#русский)

---

<a name="english"></a>

## 🇬🇧 English

### Prerequisites

- Python 3.11+
- Poetry (dependency manager)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Installation (Without Docker)

### 1. Clone & Install

```bash
git clone https://github.com/bobberdolle1/CoinFlow.git
cd CoinFlow
poetry install
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and add your bot token:
```env
TELEGRAM_BOT_TOKEN='your_token_from_botfather'
```

### 3. Run

```bash
poetry run python main.py
```

That's it! Your bot is now running! 🎉

## Docker (Alternative)

Prefer Docker? Even easier:

```bash
# 1. Clone
git clone https://github.com/bobberdolle1/CoinFlow.git
cd CoinFlow

# 2. Configure
cp .env.example .env
# Edit .env with your token

# 3. Run
docker-compose up -d
```

## First Steps

1. **Start the bot** in Telegram: `/start`
2. **Select your language**: English or Русский
3. **Try a conversion**: Click "⚡ Quick Convert"
4. **Explore features**:
   - 📊 Rate Charts
   - 🔮 Rate Forecast
   - ⚖️ Compare Rates
   - 🧮 Calculator
   - And more!

## Common Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize/restart bot |
| `/help` | Show help |
| `/stats` | Your usage statistics |
| `/history` | Conversion history |
| `/favorites` | Manage favorites |

## Inline Mode

Type in any chat:
```
@your_bot_username 100 USD to EUR
```
Get instant results!

## Troubleshooting

### Module not found
```bash
poetry install
```

### Bot not responding
- Check bot token in `.env`
- Verify internet connection
- Check logs: `tail -f coinflow.log`

### Permission errors
```bash
chmod +x main.py
```

## Configuration

Customize in `.env`:

```env
# Cache duration (seconds)
CACHE_TTL_SECONDS=60

# Alert check interval (minutes)  
ALERT_CHECK_INTERVAL=5

# Chart quality
CHART_DPI=150

# Logging
LOG_LEVEL=INFO
```

### Next Steps

- Read [README.md](README.md) for full documentation
- Check [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) if upgrading from v1.0
- Explore [docs/](docs/) for detailed guides

### Need Help?

- 📖 [Full Documentation](README.md)
- 🐳 [Docker Guide](docs/DOCKER_GUIDE.md)
- 🚀 [Deployment Guide](docs/DEPLOYMENT.md)
- 🐛 [GitHub Issues](https://github.com/bobberdolle1/CoinFlow/issues)

---

<a name="русский"></a>

## 🇷🇺 Русский

### Требования

- Python 3.11+
- Poetry (менеджер зависимостей)
- Токен Telegram-бота от [@BotFather](https://t.me/BotFather)

### Установка (без Docker)

#### 1. Клонирование и установка

```bash
git clone https://github.com/bobberdolle1/CoinFlow.git
cd CoinFlow
poetry install
```

#### 2. Настройка

```bash
cp .env.example .env
```

Отредактируйте `.env` и добавьте токен:
```env
TELEGRAM_BOT_TOKEN='ваш_токен_от_botfather'
```

#### 3. Запуск

```bash
poetry run python main.py
```

Вот и всё! Бот запущен! 🎉

### Docker (альтернатива)

Предпочитаете Docker? Ещё проще:

```bash
# 1. Клонирование
git clone https://github.com/bobberdolle1/CoinFlow.git
cd CoinFlow

# 2. Настройка
cp .env.example .env
# Отредактируйте .env с вашим токеном

# 3. Запуск
docker-compose up -d
```

### Первые шаги

1. **Запустите бота** в Telegram: `/start`
2. **Выберите язык**: English или Русский
3. **Попробуйте конвертацию**: Нажмите "⚡ Быстрая конвертация"
4. **Изучите функции**:
   - 📊 Графики курсов
   - 🔮 Прогноз курса
   - ⚖️ Сравнение курсов
   - 🧮 Калькулятор
   - И многое другое!

### Основные команды

| Команда | Описание |
|---------|-------------|
| `/start` | Инициализация/перезапуск бота |
| `/help` | Показать помощь |
| `/stats` | Статистика использования |
| `/history` | История конвертаций |
| `/favorites` | Управление избранным |

### Inline-режим

Напишите в любом чате:
```
@имя_вашего_бота 100 USD to EUR
```
Получите мгновенный результат!

### Решение проблем

#### Модуль не найден
```bash
poetry install
```

#### Бот не отвечает
- Проверьте токен в `.env`
- Проверьте интернет-соединение
- Просмотрите логи: `tail -f coinflow.log`

### Настройка

Настройте в `.env`:

```env
# Длительность кэша (секунды)
CACHE_TTL_SECONDS=60

# Интервал проверки алертов (минуты)  
ALERT_CHECK_INTERVAL=5

# Качество графиков
CHART_DPI=150

# Логирование
LOG_LEVEL=INFO
```

### Дальнейшие шаги

- Прочтите [README.md](README.md) для полной документации
- Просмотрите [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) при обновлении с v1.0
- Изучите [docs/](docs/) для подробных гайдов

### Нужна помощь?

- 📖 [Полная документация](README.md)
- 🐳 [Гайд по Docker](docs/DOCKER_GUIDE.md)
- 🚀 [Гайд по деплою](docs/DEPLOYMENT.md)
- 🐛 [GitHub Issues](https://github.com/bobberdolle1/CoinFlow/issues)

---

**Enjoy CoinFlow v2.0! 🪙✨**
