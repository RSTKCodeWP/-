# 🎯 MaixCAM WildTrap

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RSTKCodeWP/maixcam-wildtrap](https://github.com/RSTKCodeWP/maixcam-wildtrap) |
| Локальна тека | `maixcam-wildtrap-AI-Camera-Trap-MaixCAM` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

**AI-Powered Camera Trap for Wildlife Monitoring & Security**

Production-ready application for MaixCAM with automatic detection, capture, and notifications.

_З README.md, без переказу._

## Для чого

**AI-Powered Camera Trap for Wildlife Monitoring & Security**

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Список із розділу features / можливості в README:

- **Motion Detection** - Energy-efficient frame differencing
- **AI Detection** - YOLOv8 object recognition (80 classes)
- **Hybrid Mode** ⭐ - Motion trigger → AI verification (recommended)
- **Scheduled Mode** - Timelapse capture at intervals
- **Photo** - Single high-quality image
- **Burst** - Series of 3/5/10 photos
- **Video** - Record 5/10/15/30 second clips
- **Timelapse** - Periodic capture during detection
- 🎯 **Object Filtering** - Target specific animals/people
- 🤖 **Servo Control** - Trigger food dispensers or physical traps via PWM
- 🖼️ **On-Device Gallery** - Browse and view captures directly on the touchscreen
- 🚨 **External Trigger** - Support for secondary GPIO output (Light/Alarm)

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `docs/`
- `LICENSE`
- `maixcam-wildtrap-v1.6.0.zip`
- `README.md`
- `src/`

Типи файлів за вибіркою (16 файлів, глибина до 3): Markdown (10), (без суфікса) (2), Python (2), .zip (1), JSON (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

#### 1. Installation

```bash
# Download release
wget https://github.com/bobberdolle1/maixcam-wildtrap/releases/download/v1.6.0/maixcam-wildtrap-v1.6.0.zip
unzip maixcam-wildtrap-v1.6.0.zip

# Copy files to MaixCAM
scp src/* root@<MAIXCAM_IP>:/root/
```

## Супутні документи в теці

- [`docs/.github-info.md`](../../maixcam-wildtrap-AI-Camera-Trap-MaixCAM/docs/.github-info.md)
- [`docs/CHANGELOG.md`](../../maixcam-wildtrap-AI-Camera-Trap-MaixCAM/docs/CHANGELOG.md)
- [`docs/DELIVERY_SUMMARY.md`](../../maixcam-wildtrap-AI-Camera-Trap-MaixCAM/docs/DELIVERY_SUMMARY.md)
- [`docs/EXAMPLES.md`](../../maixcam-wildtrap-AI-Camera-Trap-MaixCAM/docs/EXAMPLES.md)
- [`docs/FINAL_SUMMARY.md`](../../maixcam-wildtrap-AI-Camera-Trap-MaixCAM/docs/FINAL_SUMMARY.md)
- [`docs/PROJECT_INFO.md`](../../maixcam-wildtrap-AI-Camera-Trap-MaixCAM/docs/PROJECT_INFO.md)
- [`docs/QUICKSTART.md`](../../maixcam-wildtrap-AI-Camera-Trap-MaixCAM/docs/QUICKSTART.md)
- [`docs/RELEASE_NOTES.md`](../../maixcam-wildtrap-AI-Camera-Trap-MaixCAM/docs/RELEASE_NOTES.md)
- [`docs/START_HERE.md`](../../maixcam-wildtrap-AI-Camera-Trap-MaixCAM/docs/START_HERE.md)

## З чого зібрана картка

`catalog.json`, `maixcam-wildtrap-AI-Camera-Trap-MaixCAM/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RSTKCodeWP__maixcam-wildtrap.md`.
