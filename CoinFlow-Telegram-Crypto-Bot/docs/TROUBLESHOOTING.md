# 🔧 Troubleshooting Guide

**Languages:** [English](#english) | [Русский](#russian)

Common issues and solutions for CoinFlow Bot.

---

<a name="english"></a>
## 📖 English Version

## 🔨 Installation Issues

### ModuleNotFoundError: No module named 'sqlalchemy'

**Solution:**
```bash
poetry install
```

### Poetry not found

**Solution:**
```bash
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Python version mismatch (3.11+ required)

**Solution:**
```bash
python3 --version  # Check version
sudo apt install python3.11  # Ubuntu
```

---

## ⚡ Runtime Errors

### Bot not responding to commands

**Check 1: Token configured?**
```bash
cat .env | grep TELEGRAM_BOT_TOKEN
```

**Check 2: Bot running?**
```bash
ps aux | grep python
```

### ImportError: cannot import name 'engine'

**Solution:** Update to latest version:
```bash
git pull origin main
poetry install
```

---

## 💾 Database Issues

### Database locked

**Solution:**
```bash
# Stop bot
sudo systemctl stop coinflow  # or kill process

# Remove lock
rm data/coinflow.db-lock

# Restart
sudo systemctl start coinflow
```

### Database corrupted

**Solution:**
```bash
# Backup old DB
mv data/coinflow.db data/coinflow.db.backup

# Bot will create new DB on start
poetry run python main.py
```

---

## 🌐 API & Network Issues

### Rate limit exceeded

**Problem:** Too many requests to exchange APIs.

**Solution:** Wait 1-2 minutes, bot has 60-second cache.

### Connection timeout

**Solution:**
```bash
# Check internet connection
ping google.com

# Check DNS
nslookup api.binance.com
```

---

## 🐳 Docker Issues

### Container won't start

**Solution:**
```bash
# Check logs
docker-compose logs

# Rebuild
docker-compose up -d --build
```

### Permission denied

**Linux solution:**
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Port already in use

**Solution:**
```bash
# Find process
sudo lsof -i :8080

# Kill process
sudo kill -9 <PID>
```

---

## 🚀 Performance Issues

### High memory usage

**Solution:**
```bash
# Check usage
docker stats coinflow-bot

# Restart bot
docker-compose restart
```

### Slow responses

**Possible causes:**
- API rate limits
- Network issues
- High load

**Solution:** Check logs for errors:
```bash
docker-compose logs | grep ERROR
```

---

## 📝 Common Commands

### Check bot status
```bash
# Systemd
sudo systemctl status coinflow

# Docker
docker ps | grep coinflow
```

### View logs
```bash
# Systemd
sudo journalctl -u coinflow -f

# Docker
docker-compose logs -f
```

### Restart bot
```bash
# Systemd
sudo systemctl restart coinflow

# Docker
docker-compose restart
```

---

## 🆘 Still Having Issues?

1. Check full logs for error details
2. Verify .env configuration
3. Ensure all dependencies installed
4. Try fresh install in clean directory
5. Open issue on [GitHub](https://github.com/bobberdolle1/CoinFlow/issues)

---

## 📚 See Also

- [Docker Guide](./DOCKER_GUIDE.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Quick Start](../QUICK_START.md)

---
---

<a name="russian"></a>
## 📖 Русская версия

# 🔧 Руководство по решению проблем

Типичные проблемы и решения для CoinFlow Bot.

## 🔨 Проблемы установки

### ModuleNotFoundError: No module named 'sqlalchemy'

**Решение:**
```bash
poetry install
```

### Poetry не найден

**Решение:**
```bash
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Несоответствие версии Python (требуется 3.11+)

**Решение:**
```bash
python3 --version  # Проверить версию
sudo apt install python3.11  # Ubuntu
```

---

## ⚡ Ошибки во время выполнения

### Бот не отвечает на команды

**Проверка 1: Токен настроен?**
```bash
cat .env | grep TELEGRAM_BOT_TOKEN
```

**Проверка 2: Бот запущен?**
```bash
ps aux | grep python
```

### ImportError: cannot import name 'engine'

**Решение:** Обновиться до последней версии:
```bash
git pull origin main
poetry install
```

---

## 💾 Проблемы с базой данных

### База данных заблокирована

**Решение:**
```bash
# Остановить бота
sudo systemctl stop coinflow  # или завершить процесс

# Удалить блокировку
rm data/coinflow.db-lock

# Перезапустить
sudo systemctl start coinflow
```

### База данных повреждена

**Решение:**
```bash
# Создать резервную копию старой БД
mv data/coinflow.db data/coinflow.db.backup

# Бот создаст новую БД при запуске
poetry run python main.py
```

---

## 🌐 Проблемы с API и сетью

### Превышен лимит запросов

**Проблема:** Слишком много запросов к API бирж.

**Решение:** Подождите 1-2 минуты, у бота есть 60-секундный кеш.

### Таймаут соединения

**Решение:**
```bash
# Проверить интернет-соединение
ping google.com

# Проверить DNS
nslookup api.binance.com
```

---

## 🐳 Проблемы Docker

### Контейнер не запускается

**Решение:**
```bash
# Проверить логи
docker-compose logs

# Пересобрать
docker-compose up -d --build
```

### Отказано в доступе

**Решение для Linux:**
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Порт уже используется

**Решение:**
```bash
# Найти процесс
sudo lsof -i :8080

# Завершить процесс
sudo kill -9 <PID>
```

---

## 🚀 Проблемы производительности

### Высокое использование памяти

**Решение:**
```bash
# Проверить использование
docker stats coinflow-bot

# Перезапустить бота
docker-compose restart
```

### Медленные ответы

**Возможные причины:**
- Лимиты API
- Проблемы с сетью
- Высокая нагрузка

**Решение:** Проверить логи на наличие ошибок:
```bash
docker-compose logs | grep ERROR
```

---

## 📝 Часто используемые команды

### Проверить статус бота
```bash
# Systemd
sudo systemctl status coinflow

# Docker
docker ps | grep coinflow
```

### Просмотр логов
```bash
# Systemd
sudo journalctl -u coinflow -f

# Docker
docker-compose logs -f
```

### Перезапустить бота
```bash
# Systemd
sudo systemctl restart coinflow

# Docker
docker-compose restart
```

---

## 🆘 Все еще есть проблемы?

1. Проверьте полные логи для получения деталей об ошибке
2. Проверьте конфигурацию .env
3. Убедитесь, что все зависимости установлены
4. Попробуйте свежую установку в чистой директории
5. Откройте issue на [GitHub](https://github.com/bobberdolle1/CoinFlow/issues)

---

## 📚 См. также

- [Руководство по Docker](./DOCKER_GUIDE.md)
- [Руководство по развертыванию](./DEPLOYMENT.md)
- [Быстрый старт](../QUICK_START.md)
