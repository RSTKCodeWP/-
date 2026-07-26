# 🎯 MaixCAM WildTrap

[![Release](https://img.shields.io/github/v/release/bobberdolle1/maixcam-wildtrap)](https://github.com/bobberdolle1/maixcam-wildtrap/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.x-blue.svg)](https://www.python.org/)
[![MaixPy](https://img.shields.io/badge/MaixPy-4.x-green.svg)](https://wiki.sipeed.com/maixpy)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-nano-orange.svg)](https://github.com/ultralytics/ultralytics)

**AI-Powered Camera Trap for Wildlife Monitoring & Security**

Production-ready application for MaixCAM with automatic detection, capture, and notifications.

[English](#english) | [Русский](#русский)

---

<a name="english"></a>
## 🇬🇧 English

### Features

#### Detection Modes
- **Motion Detection** - Energy-efficient frame differencing
- **AI Detection** - YOLOv8 object recognition (80 classes)
- **Hybrid Mode** ⭐ - Motion trigger → AI verification (recommended)
- **Scheduled Mode** - Timelapse capture at intervals

#### Capture Modes
- **Photo** - Single high-quality image
- **Burst** - Series of 3/5/10 photos
- **Video** - Record 5/10/15/30 second clips
- **Timelapse** - Periodic capture during detection

#### Smart Features
- 🎯 **Object Filtering** - Target specific animals/people
- 🤖 **Servo Control** - Trigger food dispensers or physical traps via PWM
- 🖼️ **On-Device Gallery** - Browse and view captures directly on the touchscreen
- 🚨 **External Trigger** - Support for secondary GPIO output (Light/Alarm)
- 🌙 **Night Mode** - Automatic brightness/contrast enhancement
- 📊 **Metadata Logging** - JSON + CSV detection history
- 🔔 **Notifications** - Telegram Bot + HTTP Webhook
- 💾 **Auto-Cleanup** - Manage storage limits automatically
- ⚡ **Energy Saving** - Optimized detection pipeline
- 📱 **Touchscreen UI** - 3-page settings menu and OSD (supports 552x368)

---

### Quick Start

#### 1. Installation

```bash
# Download release
wget https://github.com/bobberdolle1/maixcam-wildtrap/releases/download/v1.6.0/maixcam-wildtrap-v1.6.0.zip
unzip maixcam-wildtrap-v1.6.0.zip

# Copy files to MaixCAM
scp src/* root@<MAIXCAM_IP>:/root/
```
# SSH into MaixCAM
ssh root@<MAIXCAM_IP>

# Create directories
mkdir -p /root/wildtrap/{captures,logs,temp}
```

#### 2. Configuration

Edit `src/wildtrap_config.json`:

```json
{
  "detection_mode": "hybrid",
  "capture_mode": "burst",
  "target_objects": ["dog", "cat", "bird", "person"],
  "confidence_threshold": 0.6,
  "cooldown_seconds": 30,
  "telegram_enabled": true,
  "telegram_bot_token": "YOUR_BOT_TOKEN",
  "telegram_chat_id": "YOUR_CHAT_ID",
  "armed": true
}
```

#### 3. Run

```bash
python3 src/wildtrap_app.py
```

**See [QUICKSTART.md](QUICKSTART.md) for detailed 5-minute setup guide.**

---

### Configuration Guide

#### Detection Settings

| Parameter | Values | Description |
|-----------|--------|-------------|
| `detection_mode` | motion / ai / hybrid / scheduled | Detection method |
| `motion_sensitivity` | 20-100 | Motion detection threshold |
| `confidence_threshold` | 0.3-0.9 | AI confidence minimum |
| `min_object_size` | pixels | Filter small detections |
| `cooldown_seconds` | seconds | Delay between captures |

#### Target Objects

Available COCO classes:
- **Animals**: dog, cat, bird, horse, cow, sheep, bear, elephant, zebra, giraffe, deer
- **People**: person
- **Vehicles**: car, truck, motorcycle, bus

#### Camera Settings

| Parameter | Values | Description |
|-----------|--------|-------------|
| `camera_width` | 320/640/1280/1920 | Resolution width |
| `camera_height` | 240/480/720/1080 | Resolution height |
| `night_mode` | true/false | Auto brightness boost |
| `jpeg_quality` | 1-100 | Compression quality |

#### Telegram Notifications

1. Create bot with [@BotFather](https://t.me/botfather)
2. Get bot token
3. Get your chat ID from [@userinfobot](https://t.me/userinfobot)
4. Configure in `src/wildtrap_config.json`

---

### Example Configurations

#### Wildlife Monitoring (Day)
```json
{
  "detection_mode": "hybrid",
  "capture_mode": "burst",
  "burst_count": 5,
  "target_objects": ["dog", "cat", "bird", "deer", "bear"],
  "confidence_threshold": 0.7,
  "cooldown_seconds": 60,
  "night_mode": false
}
```

#### Security Camera (24/7)
```json
{
  "detection_mode": "hybrid",
  "capture_mode": "video",
  "video_duration": 15,
  "target_objects": ["person", "car"],
  "confidence_threshold": 0.8,
  "cooldown_seconds": 30,
  "night_mode": true
}
```

#### Bird Watching
```json
{
  "detection_mode": "ai",
  "capture_mode": "burst",
  "burst_count": 10,
  "target_objects": ["bird"],
  "confidence_threshold": 0.6,
  "cooldown_seconds": 10
}
```

**See [EXAMPLES.md](EXAMPLES.md) for 8 complete real-world configurations.**

---

### File Structure

```
/root/wildtrap/
├── src/                  # Application source code
│   ├── wildtrap_app.py   # Main application
│   ├── wildtrap_config.json # Configuration
│   └── simple_wildtrap.py # Educational version
├── docs/                 # Documentation files
├── captures/             # Saved photos/videos
│   ├── 20260510_143022_dog_0.87.jpg
│   └── ...
└── logs/
    └── detections.csv    # Detection history
```

---

### Documentation

- **[docs/START_HERE.md](docs/START_HERE.md)** - Navigation guide
- **[docs/QUICKSTART.md](docs/QUICKSTART.md)** - 5-minute setup
- **[docs/EXAMPLES.md](docs/EXAMPLES.md)** - 8 real-world configurations
- **[docs/PROJECT_INFO.md](docs/PROJECT_INFO.md)** - Technical architecture
- **[docs/CHANGELOG.md](docs/CHANGELOG.md)** - Version history

---

### Performance

| Mode | FPS | Power | Accuracy |
|------|-----|-------|----------|
| Motion | ~30 | Low | Medium |
| AI | ~20 | High | High |
| Hybrid | ~25 | Medium | High |
| Scheduled | Variable | Very Low | N/A |

---

### Troubleshooting

#### Camera Not Initializing
```bash
ls /dev/video*
systemctl restart camera
```

#### AI Model Not Found
```bash
cd /root/models
wget https://github.com/sipeed/MaixPy/releases/download/v4.0.0/yolov8n.mud
```

#### No Detections
- Check `"armed": true` in config
- Lower `confidence_threshold` to 0.5
- Verify `target_objects` includes what you're testing
- Check lighting conditions

---

### Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

See [PROJECT_INFO.md](PROJECT_INFO.md) for architecture details.

---

### License

MIT License - Free for personal and commercial use. See [LICENSE](LICENSE) for details.

---

### Support

- **Issues**: [GitHub Issues](https://github.com/bobberdolle1/maixcam-wildtrap/issues)
- **MaixPy Docs**: https://wiki.sipeed.com/maixpy
- **Community**: https://maixhub.com

---

### Credits

Built with:
- [MaixPy](https://github.com/sipeed/MaixPy) - Python framework for MaixCAM
- [YOLOv8](https://github.com/ultralytics/ultralytics) - Object detection
- MaixCAM by [Sipeed](https://www.sipeed.com/)

---

<a name="русский"></a>
## 🇷🇺 Русский

### Возможности

#### Режимы детекции
- **Motion Detection** - Энергоэффективное определение движения
- **AI Detection** - Распознавание объектов YOLOv8 (80 классов)
- **Hybrid Mode** ⭐ - Движение → AI проверка (рекомендуется)
- **Scheduled Mode** - Таймлапс съемка по расписанию

#### Режимы съемки
- **Photo** - Одиночное фото высокого качества
- **Burst** - Серия из 3/5/10 фотографий
- **Video** - Запись видео 5/10/15/30 секунд
- **Timelapse** - Периодическая съемка при детекции

#### Умные функции
- 🎯 **Фильтрация объектов** - Выбор конкретных животных/людей
- 🤖 **Управление сервоприводом** - Управление ловушками или кормушками через PWM
- 🖼️ **Галерея на устройстве** - Просмотр снимков прямо на сенсорном экране
- 🚨 **Внешний триггер** - Поддержка GPIO выхода для света или сирены
- 🌙 **Ночной режим** - Автоматическое улучшение яркости/контраста
- 📊 **Логирование метаданных** - JSON + CSV история детекций
- 🔔 **Уведомления** - Telegram Bot + HTTP Webhook
- 💾 **Авто-очистка** - Автоматическое управление хранилищем
- ⚡ **Энергосбережение** - Оптимизированный pipeline детекции
- 📱 **Сенсорный UI** - Меню из 3-х страниц и OSD (поддерживает 552x368)

---

### Быстрый старт

#### 1. Установка

```bash
# Скачать релиз
wget https://github.com/bobberdolle1/maixcam-wildtrap/releases/download/v1.6.0/maixcam-wildtrap-v1.6.0.zip
unzip maixcam-wildtrap-v1.6.0.zip

# Копировать файлы на MaixCAM
scp src/* root@<IP_MAIXCAM>:/root/
```
# Подключиться по SSH
ssh root@<IP_MAIXCAM>

# Создать директории
mkdir -p /root/wildtrap/{captures,logs,temp}
```

#### 2. Настройка

Редактировать `src/wildtrap_config.json`:

```json
{
  "detection_mode": "hybrid",
  "capture_mode": "burst",
  "target_objects": ["dog", "cat", "bird", "person"],
  "confidence_threshold": 0.6,
  "cooldown_seconds": 30,
  "telegram_enabled": true,
  "telegram_bot_token": "ВАШ_ТОКЕН_БОТА",
  "telegram_chat_id": "ВАШ_CHAT_ID",
  "armed": true
}
```

#### 3. Запуск

```bash
python3 src/wildtrap_app.py
```

**См. [QUICKSTART.md](QUICKSTART.md) для подробной инструкции за 5 минут.**

---

### Руководство по настройке

#### Параметры детекции

| Параметр | Значения | Описание |
|----------|----------|----------|
| `detection_mode` | motion / ai / hybrid / scheduled | Метод детекции |
| `motion_sensitivity` | 20-100 | Порог чувствительности движения |
| `confidence_threshold` | 0.3-0.9 | Минимальная уверенность AI |
| `min_object_size` | пиксели | Фильтр мелких объектов |
| `cooldown_seconds` | секунды | Задержка между съемками |

#### Целевые объекты

Доступные COCO классы:
- **Животные**: dog, cat, bird, horse, cow, sheep, bear, elephant, zebra, giraffe, deer
- **Люди**: person
- **Транспорт**: car, truck, motorcycle, bus

#### Настройки камеры

| Параметр | Значения | Описание |
|----------|----------|----------|
| `camera_width` | 320/640/1280/1920 | Ширина разрешения |
| `camera_height` | 240/480/720/1080 | Высота разрешения |
| `night_mode` | true/false | Авто-усиление яркости |
| `jpeg_quality` | 1-100 | Качество сжатия |

#### Уведомления Telegram

1. Создать бота через [@BotFather](https://t.me/botfather)
2. Получить токен бота
3. Узнать свой chat ID через [@userinfobot](https://t.me/userinfobot)
4. Настроить в `src/wildtrap_config.json`

---

### Примеры конфигураций

#### Мониторинг дикой природы (день)
```json
{
  "detection_mode": "hybrid",
  "capture_mode": "burst",
  "burst_count": 5,
  "target_objects": ["dog", "cat", "bird", "deer", "bear"],
  "confidence_threshold": 0.7,
  "cooldown_seconds": 60,
  "night_mode": false
}
```

#### Охранная камера (24/7)
```json
{
  "detection_mode": "hybrid",
  "capture_mode": "video",
  "video_duration": 15,
  "target_objects": ["person", "car"],
  "confidence_threshold": 0.8,
  "cooldown_seconds": 30,
  "night_mode": true
}
```

#### Наблюдение за птицами
```json
{
  "detection_mode": "ai",
  "capture_mode": "burst",
  "burst_count": 10,
  "target_objects": ["bird"],
  "confidence_threshold": 0.6,
  "cooldown_seconds": 10
}
```

**См. [EXAMPLES.md](EXAMPLES.md) для 8 полных реальных конфигураций.**

---

### Структура файлов

```
/root/wildtrap/
├── captures/              # Сохраненные фото/видео
│   ├── 20260510_143022_dog_0.87.jpg
│   ├── 20260510_143022_dog_0.87.json
│   └── ...
├── logs/
│   └── detections.csv    # История детекций
└── temp/                 # Временные файлы
```

---

### Документация

- **[START_HERE.md](START_HERE.md)** - Навигация по проекту
- **[QUICKSTART.md](QUICKSTART.md)** - Установка за 5 минут
- **[EXAMPLES.md](EXAMPLES.md)** - 8 реальных конфигураций
- **[PROJECT_INFO.md](PROJECT_INFO.md)** - Техническая архитектура
- **[CHANGELOG.md](CHANGELOG.md)** - История версий

---

### Производительность

| Режим | FPS | Энергия | Точность |
|-------|-----|---------|----------|
| Motion | ~30 | Низкая | Средняя |
| AI | ~20 | Высокая | Высокая |
| Hybrid | ~25 | Средняя | Высокая |
| Scheduled | Переменная | Очень низкая | N/A |

---

### Решение проблем

#### Камера не инициализируется
```bash
ls /dev/video*
systemctl restart camera
```

#### AI модель не найдена
```bash
cd /root/models
wget https://github.com/sipeed/MaixPy/releases/download/v4.0.0/yolov8n.mud
```

#### Нет детекций
- Проверить `"armed": true` в конфиге
- Снизить `confidence_threshold` до 0.5
- Проверить что `target_objects` включает тестируемый объект
- Проверить условия освещения

---

### Участие в разработке

Приветствуются вклады! Пожалуйста:
1. Сделайте fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Отправьте pull request

См. [PROJECT_INFO.md](PROJECT_INFO.md) для деталей архитектуры.

---

### Лицензия

MIT License - Свободно для личного и коммерческого использования. См. [LICENSE](LICENSE) для деталей.

---

### Поддержка

- **Issues**: [GitHub Issues](https://github.com/bobberdolle1/maixcam-wildtrap/issues)
- **MaixPy Docs**: https://wiki.sipeed.com/maixpy
- **Сообщество**: https://maixhub.com

---

### Благодарности

Создано с использованием:
- [MaixPy](https://github.com/sipeed/MaixPy) - Python фреймворк для MaixCAM
- [YOLOv8](https://github.com/ultralytics/ultralytics) - Детекция объектов
- MaixCAM от [Sipeed](https://www.sipeed.com/)

---

**Made with ❤️ for wildlife enthusiasts and makers**

**Сделано с ❤️ для любителей дикой природы и мейкеров**
