# StabX — технічний реверс (з документації Academia Tech)

> Джерела: офіційна Google Doc «Оптична навігація», публічні матеріали Academia Tech,
> тендерна документація, порівняння з AeroStab.
>
> Образ `ZERO-16G-2025-11-01-JR.rar` (1.7 GB) **не розібраний бінарно** — Google Drive quota.
> Реверс нижче — **архітектура, протоколи, поведінка** з відкритої документації.

---

## 1. Що таке StabX

| Параметр | Значення |
|----------|----------|
| Виробник | **Academia Tech** (Україна), [theacademia.tech](https://theacademia.tech) |
| Тип | Закритий софт оптичної одометрії / стабілізації |
| Платформа | Raspberry Pi **Zero 2W** (основна), Pi **5** (потужніша) |
| FC | ArduPilot (Copter / Plane кастомні білди) |
| Режим | **PosHold** без GPS; fallback AltHold / Stabilize |
| Ліцензія | Ключ + Bluetooth-активатор; шифрування; прив'язка до заліза |
| Екосистема | `uapilot.online` — ліцензії, білди, аналіз `.stabx` логів |

**Не плутати з AeroStab** — наш open-source аналог за ідеєю, без ліцензійного сервера.

---

## 2. Апаратна архітектура

```
┌─────────────────────────────────────────────────────────┐
│  Raspberry Pi Zero 2W (+ радіатор 20×20 — критично)     │
│  ┌──────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │ CSI камера│  │ USB камера  │  │ CVBS→USB (ніч)   │   │
│  │ денна    │  │ (Kurbas/    │  │ CaddX 256/640    │   │
│  │ OV5647   │  │  Seek)      │  │                  │   │
│  └────┬─────┘  └──────┬──────┘  └────────┬─────────┘   │
│       └───────────────┴───────────────────┘             │
│                         │ optical flow / DIFF           │
│  GPIO14 TX ─────────────┼──► FC RX (MAVLink2)          │
│  GPIO15 RX ◄────────────┼─── FC TX                     │
│  GND / 5V ◄─────────────┘    (пад Cam або UBEC)         │
│  Composite / HDMI ──► FPV / HereLink (опційно)          │
└─────────────────────────────────────────────────────────┘
```

### Підтримувані камери

| Клас | Моделі |
|------|--------|
| Денні CSI | IMX290-83, IMX219-120, **OV5647-120** |
| Нічні USB | CaddX 256/640, Kurbas 256/640, Seek UAV 256/640 |
| Тепло | LMT2512UI-256 (замовлення) |
| Dual | Денна CSI + нічна USB; перемикання **на старті** (не в польоті) |

### Живлення

- Pi Zero: 5 V з потужного паду FC (Cam pad) — достатньо
- Pi 5: окремий UBEC до **3 A**
- Нічні камери: **6–9 V UBEC**, не від USB Pi
- Тепловізори: пасивний обдув обов'язковий

### UART

| Pi | FC |
|----|-----|
| TX (GPIO14, синій) | RX |
| RX (GPIO15, зелений) | TX |
| GND | GND |

Baud: **230400** (`SERIALx_BAUD = 230`).

---

## 3. Програмна архітектура (висновки з документації)

### 3.1 Два веб-сервіси

| URL | Порт | Призначення |
|-----|------|-------------|
| `http://pizero2:5050` | 5050 | **Provisioning**: ліцензія, вибір білда, Download, Bluetooth MAC |
| `http://pizero2:8080` | 8080 | **Flight UI**: камера, FOV, маска, записи, Map, Inspector |

Hostname: `pizero2` / `pizero2.local` (mDNS).

### 3.2 Життєвий цикл

```
Flash SD image → WiFi (hotspot ASUS_EXT / uapilot / wifi.txt)
    → :5050 активація ключа → Download build
    → :8080 Drone UI → FOV/rotation/mask → Lock SD
    → PosHold arm на FC
```

### 3.3 Білди (хронологія, новіші зверху)

| Білд | Ключові фічі |
|------|--------------|
| `2026-07-08-MASK-V2` | IR-TINY1C; MAVLink messages **to** StabX |
| `2026-06-18-MASK` | Сіткова маска ROI |
| `2026-06-11-HILLS` | Baro level estimator (рельєф) |
| `2026-05-11-RTL-V2` | RTL ±50–200 m / 10 km; мапа польоту |
| `2026-03-16-DUAL-V1` | День+ніч |
| `2026-01-14-FUSE-V2` | GPS fusion; Map; GPS_RAW_INT out |
| `2025-12-18-DIFF-V3` | DIFF трекінг для thermal; `frames_timing` |
| `2025-11-25-DIFF-V2` | Новий UI (Vivaldi); Kurbas256 |

Образ з Drive: **`ZERO-16G-2025-11-01-JR.rar`** — SD 16 GB, ймовірно базовий образ + provisioning.

### 3.4 Алгоритми (інферовано)

| Компонент | Опис |
|-----------|------|
| **Optical flow** | Lucas–Kanade-подібний трекінг feature points між кадрами |
| **DIFF** | Окремий алгоритм для тепловізорів (CaddX/Kurbas/Seek профілі) |
| **Маска** | Сітка 16×N; червона зона ігнорується; <33% ROI |
| **FOV** | Калібрування: 100 см до підлоги, 1 м сітка = 100 см рулетки |
| **Висота** | Баро + lidar validation; Baro level estimator для рельєфу |
| **Yaw** | Compass (рекомендовано) або ExternalNav (optical yaw) |
| **GPS fuse** | Оптична траєкторія + GPS_RAW_INT корекція (білд MASK-V3+) |
| **RTL** | Запис шляху; SmartRTL по траєкторії |

### 3.5 Захист

- Ліцензійний ключ на `uapilot.online`
- Bluetooth-активатор (MAC, не телефон)
- **Lock SD** — запис заблокований після налаштування
- Бінарі зашифровані, прив'язані до hardware
- Стартова точка на Map — зашифрована

---

## 4. MAVLink / ArduPilot інтеграція

### 4.1 Коптер (стандарт)

```ini
VISO_TYPE = 1                    # MAVLink visual odometry
EK3_SRC1_POSXY = 6               # ExternalNav
EK3_SRC1_VELXY = 6
EK3_SRC1_POSZ = 1                # Baro
EK3_SRC1_VELZ = 0
EK3_SRC1_YAW = 1                 # Compass (або 6 без компаса)

GPS1_TYPE = 0
AHRS_GPS_USE = 0
AHRS_GPS_GAIN = 0
FS_GCS_ENABLE = 0

SERIALx_PROTOCOL = 2             # MAVLink2
SERIALx_BAUD = 230               # 230400

ARMING_CHECK = 8256              # RC + System (без GPS)
FRAME_TYPE = 12 або 18           # BetaflightX (пропи на/від камери)

PHLD_BRAKE_ANGLE = 2400
PHLD_BRAKE_RATE = 8
FS_EKF_THRESH = 1.5
```

### 4.2 Повідомлення (інферовано)

| Напрям | Повідомлення | Призначення |
|--------|--------------|-------------|
| StabX → FC | `VISION_POSITION_ESTIMATE` | Позиція для EKF |
| StabX → FC | `VISION_SPEED_ESTIMATE` | Швидкість |
| StabX → FC | `GPS_RAW_INT` | Starlink / fuse GPS (бета) |
| StabX → FC | `GPS_INPUT` | **Літаки** (GPS_TYPE=14) |
| FC → StabX | heartbeat, attitude, baro, rangefinder, GPS_RAW_INT | Висота, fuse, inspector |

### 4.3 Літаки / VTOL

- Кастомна прошивка ArduPlane (без фізичного GPS для старту EKF)
- `GPS_TYPE = 14` (MAVLink GPS)
- `EK3_SRC1_POSXY/VELXY = 3` (GPS) — StabX емулює GPS
- UI: режим надсилання **GPS_INPUT**

### 4.4 Режими польоту

| Режим | Роль |
|-------|------|
| **PosHold** | Основний — StabX активний |
| **AltHold** | Fallback при збої StabX |
| **Stabilize** | Аварійний (Вампір, втрата IMU в AltHold) |
| **RTL / SmartRTL** | Повернення по оптиці |
| **GuidedNoGPS** | Auto-arm через 20 с |

**Важливо:** без валідної StabX PosHold **не армиться**.

---

## 5. Веб-інтерфейс (8080)

| Розділ | Функція |
|--------|---------|
| Drone / Viewport | Прев'ю камери, rotation, FOV grid |
| Маска | 4 квадратики → сітка; <33% червоного в Features box |
| Налаштування | Basic: VideoOutput NTSC/PAL/HDMI |
| Записи | `.stabx` video logs |
| Inspector | MAVLink inspector |
| Map / Live | Стартова точка, live map (Starlink) |
| Features | Чорний ROI-квадрат для перевірки маски |
| frames_timing | Діагностика USB frame drops |

---

## 6. WiFi / provisioning

| Метод | Деталі |
|-------|--------|
| Hotspot | `ASUS_EXT` / `Andrew75` або `uapilot` / `uapilotstab` (**2.4 GHz only**) |
| OTG + wifi.txt | Рядок 1: SSID, рядок 2: password |
| Ethernet OTG | micro-USB OTG + USB-LAN |

---

## 7. Troubleshooting (з документації)

| Симптом | Причина | Фікс |
|---------|---------|------|
| Гойдалка на місці | Невірний FOV | Перекалібрувати сітку 1 м |
| Телепає швидко | Жорсткі PID / EKF | Зменшити P,I; PSC_POSXY_P 0.5–0.8 |
| Повільний знос | Deadzone стіків | RC1_DZ, RC2_DZ = 30–50 |
| Втрата стабу через хв | Живлення Pi / ESC noise | UBEC; конденсатор |
| Крутиться по yaw | Деталь в кадрі | Маска / вужча камера |
| Злітає після зльоту | Невірний rotation | Перевірити стрілку на папері |
| PosHold не арм | StabX не готова | :8080 діагностика |
| Stab завантажилась пізніше | Race at boot | AltHold → PosHold toggle |

---

## 8. Логи та аналіз

1. `:8080` → **Записи** → завантажити `.stabx`
2. `uapilot.online` → ключ → Завантаження
3. Формати: JPEG stream, decorated JPEG, ZIP
4. ZIP → `Flight/report.html`: MAVLink log, кадри, графіки

---

## 9. Порівняння StabX ↔ AeroStab

| Фіча | StabX | AeroStab |
|------|-------|----------|
| Optical flow | ✓ (закритий) | ✓ LK (`estimator.py`) |
| Thermal DIFF | ✓ профілі | ✗ (synthetic PMW only) |
| Dual camera | ✓ DUAL-V1 | ✗ |
| Grid mask | ✓ MASK | ✓ `mask.py` |
| FOV grid 1 m | ✓ | ✓ `show_grid` |
| GPS fusion | ✓ FUSE-V2 | ✓ `gps_fusion.py` |
| RTL path | ✓ RTL-V2 + map | ✓ `rtl_path.py` |
| Baro hills | ✓ HILLS | частково `altitude.auto` |
| Hold on drop | ✓ (implicit) | ✓ `hold_last_on_drop` |
| License server | ✓ :5050 | ✗ |
| BT activation | ✓ | ✗ |
| MAVLink inspector | ✓ | частково health |
| .stabx logs | ✓ proprietary | CSV + `log_analyzer.py` |
| Plane GPS_INPUT | ✓ | ✗ (vision only) |
| Open source | ✗ | ✓ |

---

## 10. Що потрібно для бінарного реверсу образу

Якщо завантажити `ZERO-16G-2025-11-01-JR.rar`:

```bash
# Розпакувати RAR → .img
# Mount partitions
sudo mount -o loop,offset=$((512*122880)) stabx.img /mnt/root  # offset залежить від образу

# Шукати:
/opt/ /home/pi/ /usr/local/bin/
systemctl list-units | grep -i stab
strings /path/to/binary | grep -i mavlink
cat /etc/systemd/system/*.service
```

Очікувані артефакти:
- Бінарний daemon (не Python) або obfuscated Python
- Конфіг у `/etc/` або зашифрований на boot
- nginx/caddy + custom UI (Vivaldi framework з DIFF-V2)
- Зв'язок з `uapilot.online` для OTA

---

## 11. Висновки для розробки AeroStab

Пріоритетні gap'и відносно StabX:

1. **Baro level estimator** — рельєф (HILLS білд)
2. **Thermal DIFF profiles** — окремі пайплайни для CaddX/Kurbas
3. **Dual camera** — day/night switch at boot
4. **GPS_INPUT mode** — для ArduPlane
5. **Flight map** — mosaic + Google Maps overlay
6. **MAVLink inspector** у веб-UI
7. **frames_timing** — USB drop diagnostics
8. **Строгіший arm gate** — PosHold блокується без NAV valid (вже є FLIGHT OK)

---

## Посилання

- Документація: Google Doc «Оптична навігація» (Academia StabX)
- Образ: `ZERO-16G-2025-11-01-JR.rar` (Google Drive)
- Сайт: https://theacademia.tech
- BOM: https://docs.google.com/spreadsheets/d/1EK2ivnruir1vM7jP4dPWfKLPtNHdDFTZSqVXn1FO-Cc

*Документ згенеровано з відкритої документації. Бінарний реверс не виконувався.*
