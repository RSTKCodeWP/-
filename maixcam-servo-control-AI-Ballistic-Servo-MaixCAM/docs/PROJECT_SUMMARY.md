# 🎯 Project Summary

## MaixCAM Advanced Servo Control

**GitHub Repository:** https://github.com/bobberdolle1/maixcam-servo-control

---

## 📦 What's Included

### Main Applications

1. **`advanced_servo_app.py`** - Полнофункциональное приложение
   - Color, Object (YOLO), Motion detection
   - Полное UI с меню и настройками
   - ARM mode, rearm logic, repeat trigger
   - Калибровка цвета через тачскрин
   - Сохранение конфигурации
   - OSD с статусом и таймерами

2. **`simple_servo_app.py`** - Упрощенная версия
   - Только Color и Motion detection
   - Минимальный код для быстрого старта
   - Легко модифицировать
   - Идеально для обучения

3. **`color_servo_app.py`** - Оригинальная версия с улучшениями
   - Детекция цвета с калибровкой
   - Базовый UI
   - Сохранение настроек

4. **`servo_detector_app.py`** - Версия с базовым меню
   - Несколько режимов детекции
   - Простое меню
   - Пресеты цветов

### Utility Scripts

5. **`servo_test.py`** - Тест сервопривода
   - Проверка подключения
   - Тест углов 0° -> 180°
   - Диагностика проблем

6. **`check_pwm_pins.py`** - Проверка PWM пинов
   - Автоматическое тестирование всех PWM пинов
   - Определение рабочих пинов
   - Рекомендации по подключению

7. **`calibrate_color.py`** - Инструмент калибровки цвета
   - Интерактивная калибровка
   - Live preview детекции
   - Сохранение в конфиг

8. **`yellow_servo_control.py`** - Базовая версия для желтого цвета
   - Простейший пример
   - Хорошая отправная точка

### Documentation

9. **`README.md`** - Основная документация
   - Обзор возможностей
   - Требования и подключение
   - Базовое использование

10. **`QUICKSTART.md`** - Быстрый старт
    - Установка за 5 минут
    - Пошаговые инструкции
    - Готовые сценарии

11. **`EXAMPLES.md`** - Примеры использования
    - 10+ реальных сценариев
    - Интеграции (MQTT, HTTP, Database)
    - Оптимизация производительности

12. **`TECHNICAL.md`** - Техническая документация
    - Архитектура системы
    - Алгоритмы детекции
    - Оптимизация и тюнинг
    - Troubleshooting

13. **`config_examples.json`** - Примеры конфигураций
    - Готовые пресеты
    - Описание параметров
    - Советы по настройке

14. **`LICENSE`** - MIT License

15. **`.gitignore`** - Git ignore rules

---

## 🚀 Key Features

### Autonomous Ballistics (v2.5.0)
- ✅ **Mathematical Drop Engine** - Вычисление времени и дистанции полета груза
- ✅ **Auto Ground Speed (Optical Flow)** - Автоматическое измерение скорости земли под камерой
- ✅ **AI Altitude Rangefinder** - Оценка высоты по размеру цели
- ✅ **Standalone Boot** - Запуск прямо при подаче питания без ПК

### Detection Modes
- ✅ **Color Detection** - LAB color space, калибровка, пресеты
- ✅ **Object Detection** - YOLOv8, 80 классов COCO + Custom objects
- ✅ **Motion Detection** - Frame differencing, настраиваемая чувствительность

### Servo Control
- ✅ Настраиваемые углы открытия/закрытия
- ✅ Автоматическое закрытие с таймером
- ✅ ARM/DISARM режим
- ✅ Rearm mode с задержкой
- ✅ Repeat trigger mode
- ✅ Выбор PWM пина

### User Interface
- ✅ Полноэкранный OSD
- ✅ Тачскрин меню
- ✅ Настройки в реальном времени
- ✅ Калибровка цвета
- ✅ Статус и таймеры
- ✅ FPS счетчик

### Configuration
- ✅ JSON конфигурация
- ✅ Сохранение/загрузка настроек
- ✅ Готовые пресеты
- ✅ Backup конфигов

### Optimization
- ✅ Оптимизированная обработка изображений
- ✅ Настраиваемое разрешение камеры
- ✅ Эффективное использование LAB пространства
- ✅ Минимальная задержка детекции

---

## 📊 Performance

| Mode     | Resolution | FPS  | Latency | Accuracy |
|----------|------------|------|---------|----------|
| Color    | 640x480    | ~30  | ~30ms   | High     |
| Color    | 320x240    | ~60  | ~15ms   | Medium   |
| Object   | 640x480    | ~20  | ~50ms   | High     |
| Object   | 320x240    | ~40  | ~25ms   | Medium   |
| Motion   | 640x480    | ~30  | ~30ms   | Medium   |
| Motion   | 320x240    | ~60  | ~15ms   | Medium   |

---

## 🎯 Use Cases

1. **Automatic Pet Feeder** - Кормушка для питомцев
2. **Color Sorting** - Сортировка по цвету
3. **Motion Security** - Система безопасности
4. **People Counter** - Счетчик посетителей
5. **Automatic Door** - Автоматическая дверь
6. **Gesture Control** - Управление жестами
7. **Wildlife Camera** - Камера для дикой природы
8. **Quality Control** - Контроль качества
9. **Parking Monitor** - Мониторинг парковки
10. **Interactive Art** - Интерактивное искусство

---

## 🛠 Technical Stack

### Hardware
- **MaixCAM** (1st gen with screen)
- **Servo** SG90 or compatible
- **Power** 5V 2A recommended

### Software
- **MaixPy** - Python framework for MaixCAM
- **YOLOv8** - Object detection model
- **LAB Color Space** - Robust color detection
- **PWM Control** - Servo control

### Algorithms
- **Blob Detection** - Color blob finding
- **Frame Differencing** - Motion detection
- **Neural Network** - YOLO object detection
- **State Machine** - Servo control logic

---

## 📈 Project Stats

- **Total Files:** 15
- **Lines of Code:** ~2000+
- **Documentation:** 4 comprehensive guides
- **Examples:** 10+ real-world scenarios
- **Presets:** 8 color presets, 7 config presets
- **Supported Objects:** 80 COCO classes

---

## 🔧 Installation Methods

### Method 1: MaixVision (Recommended)
```bash
1. Connect to MaixCAM (10.144.30.1)
2. Open advanced_servo_app.py
3. Press F5 to run
```

### Method 2: SSH
```bash
scp advanced_servo_app.py root@10.144.30.1:/root/
ssh root@10.144.30.1
python3 /root/advanced_servo_app.py
```

### Method 3: Git Clone
```bash
ssh root@10.144.30.1
cd /root
git clone https://github.com/bobberdolle1/maixcam-servo-control.git
cd maixcam-servo-control
python3 advanced_servo_app.py
```

---

## 🎓 Learning Path

### Beginner
1. Start with `servo_test.py` - Test hardware
2. Try `simple_servo_app.py` - Basic functionality
3. Read `QUICKSTART.md` - Quick start guide

### Intermediate
1. Use `advanced_servo_app.py` - Full features
2. Experiment with `calibrate_color.py` - Color tuning
3. Read `EXAMPLES.md` - Real-world scenarios

### Advanced
1. Read `TECHNICAL.md` - Deep dive
2. Modify code for custom use cases
3. Integrate with external systems (MQTT, HTTP)

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- [ ] Additional detection modes (face, QR code)
- [ ] Multi-servo support
- [ ] Web interface
- [ ] Mobile app control
- [ ] Cloud integration
- [ ] Machine learning model training
- [ ] More language support

---

## 📞 Support

- **GitHub Issues:** https://github.com/bobberdolle1/maixcam-servo-control/issues
- **Documentation:** See README.md, QUICKSTART.md, TECHNICAL.md
- **Examples:** See EXAMPLES.md

---

## 📝 License

MIT License - See LICENSE file

---

## 🙏 Acknowledgments

- **Sipeed** - MaixCAM hardware and MaixPy framework
- **Ultralytics** - YOLOv8 model
- **Community** - Testing and feedback

---

## 🎉 Quick Start Command

```bash
# Test servo
python3 servo_test.py

# Check PWM pins
python3 check_pwm_pins.py

# Run simple app
python3 simple_servo_app.py

# Run full app
python3 advanced_servo_app.py

# Calibrate color
python3 calibrate_color.py
```

---

## 📦 Repository Structure

```
maixcam-servo-control/
├── advanced_servo_app.py      # Main application
├── simple_servo_app.py         # Simple version
├── color_servo_app.py          # Color detection version
├── servo_detector_app.py       # Multi-mode version
├── yellow_servo_control.py     # Basic yellow detection
├── servo_test.py               # Hardware test
├── check_pwm_pins.py           # PWM pin checker
├── calibrate_color.py          # Color calibration tool
├── README.md                   # Main documentation
├── QUICKSTART.md               # Quick start guide
├── EXAMPLES.md                 # Usage examples
├── TECHNICAL.md                # Technical documentation
├── PROJECT_SUMMARY.md          # This file
├── config_examples.json        # Configuration examples
├── LICENSE                     # MIT License
└── .gitignore                  # Git ignore rules
```

---

## 🚀 Next Steps

1. **Test Hardware**
   ```bash
   python3 servo_test.py
   python3 check_pwm_pins.py
   ```

2. **Try Simple Version**
   ```bash
   python3 simple_servo_app.py
   ```

3. **Use Full Version**
   ```bash
   python3 advanced_servo_app.py
   ```

4. **Customize**
   - Edit config in `/root/advanced_servo_config.json`
   - Or use in-app settings menu

5. **Explore**
   - Read EXAMPLES.md for ideas
   - Read TECHNICAL.md for optimization

---

**Enjoy building with MaixCAM! 🎉**

Repository: https://github.com/bobberdolle1/maixcam-servo-control
