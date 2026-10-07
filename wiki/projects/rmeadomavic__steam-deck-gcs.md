# Steam Deck Ground Control Station

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [rmeadomavic/steam-deck-gcs](https://github.com/rmeadomavic/steam-deck-gcs) |
| Локальна тека | `fpv-library/repos/steam-deck-gcs-Steam-Deck-as-a-portable-drone-GCS-with` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `radio`, `elrs` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-07-19 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

Turn your Steam Deck into a portable drone ground control station using ExpressLRS MAVLink telemetry.

This guide covers setting up **QGroundControl** and **Mission Planner** on a Steam Deck with a **RadioMaster Nomad** ELRS module as a standalone MAVLink radio — no RC transmitter needed.

_З README.md, без переказу._

## Для чого

Steam Deck as a portable drone GCS with RadioMaster Nomad ELRS, QGroundControl, and Mission Planner

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Інженер радіолінка — у тексті є «expresslrs».


Теми GitHub: `drone`, `expresslrs`, `gcs`, `mavlink`, `mavproxy`, `mission-planner`, `qgroundcontrol`, `steam-deck`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Steam Deck as a portable drone GCS with RadioMaster Nomad ELRS, QGroundControl, and Mission Planner

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `config/`
- `install.sh`
- `LICENSE`
- `README.md`
- `scripts/`

Типи файлів за вибіркою (11 файлів, глибина до 3): (без суфікса) (5), shell (1), Markdown (1), JSON (1), .desktop (1), YAML (1).

Фрагмент README про будову:

### Architecture

```
┌─────────────────┐     USB-C      ┌──────────────┐    ELRS 2.4GHz    ┌──────────────┐
│   Steam Deck    │◄──────────────►│  RadioMaster │◄─────────────────►│   Aircraft   │
│                 │   Serial/MAV    │    Nomad     │    + 868/915MHz   │              │
│  QGC / MP       │   460800 baud  │              │    Gemini Link    │  FC + ELRS   │
│  MAVProxy       │                │  XT30◄──LiPo │                   │  Receiver    │
└─────────────────┘                └──────────────┘                   └──────────────┘
```

## Що треба

### Firmware Requirements

- ELRS TX + RX firmware: **3.5.0** or newer
- TX Backpack firmware: **1.5.0** or newer (if using WiFi method)
- ArduPilot: any recent version with MAVLink support


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 1. Install GCS Software

```bash
# Run the install script (does everything)
./install.sh
```

Or manually:

```bash
# QGroundControl (easy, works immediately)
flatpak install -y --user flathub org.mavlink.qgroundcontrol

# Mission Planner (requires Nix for mono)
# First: sudo chown -R $USER /nix
curl -L https://nixos.org/nix/install | bash -s -- --no-daemon
. ~/.nix-profile/etc/profile.d/nix.sh
nix-env -iA nixpkgs.mono
# Then extract Mission Planner
mkdir -p ~/.local/share/mission-planner
unzip MissionPlanner-latest.zip -d ~/.local/share/mission-planner/
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/steam-deck-gcs-Steam-Deck-as-a-portable-drone-GCS-with/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/rmeadomavic__steam-deck-gcs.md`.
