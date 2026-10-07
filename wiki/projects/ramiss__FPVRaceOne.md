# FPVRaceOne

> Картка виставки. Зал: [Інструменти](../halls/tools.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [ramiss/FPVRaceOne](https://github.com/ramiss/FPVRaceOne) |
| Локальна тека | `fpv-library/repos/FPVRaceOne-A-personal-FPV-race-timing-solution-that` |
| У бібліотеці | keep |
| Категорії каталогу | `tools` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-07-31 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

**Personal FPV Lap Timer**

A single node personal lap timing solution for 5.8 GHz FPV drones that can be networked to other units (8 total) for multi-pilot racing. Perfect for personal race or practice sessions with one unit (indoor and large scale) up to MultiGP race events with multiple units. No additional networking hardware required — just plug in a USB power, connect over wifi, calibrate, and fly.

**Up to 8 devices can wirelessly network with each other to act as a single multi-node lap timer (no additional hardware or software needed)** — one device is set to master mode and acts as race director with up to 7 additional clients. Manually connect clients or have the master automatically recruit clients in range.  Master can see all pilot times and control the race, while single pilots can remain logged into their device and see all other racer times - or initiate individual pract…

_З README.md, без переказу._

## Для чого

A personal FPV race timing solution that can be networked with others. Fly solo. Race together!

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

Теми GitHub: `fpv`, `fpv-drones`, `fpv-racing`, `lap-timer`, `timer`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: A personal FPV race timing solution that can be networked with others. Fly solo. Race together!

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `case/`
- `CHANGELOG.md`
- `data/`
- `docs/`
- `electron/`
- `lib/`
- `LICENSE`
- `partitions_two_ota_XIAO_ESP32_C6.csv`
- `platformio.ini`
- `QUICKSTART.md`
- `README.md`
- `Schematic/`
- `screenshots/`
- `scripts/`
- `src/`
- `SVG/`
- `targets/`

Типи файлів за вибіркою (107 файлів, глибина до 3): .png (30), C (22), C++ (19), Markdown (8), JavaScript (5), .jpg (4).

Фрагмент README про будову:

### How It Works

FPVRaceOne uses an RX5808 video receiver module to monitor your drone's video transmitter RSSI (signal strength). As you fly through the timing gate:

1. **Approach** — RSSI rises above the Enter threshold → crossing begins
2. **Peak** — RSSI peaks when you're closest to the gate
3. **Exit** — RSSI falls below the Exit threshold → lap time recorded

**Note that FPVRaceOne has an automatic calibration wizard to take the guess work out of setting the RSSI values (see below)**

```
RSSI  │     /\
      │    /  \
      │   /    \     ← Single clean peak
Enter ├──/──────\───
      │ /        \
Exit  ├/──────────\─
      └─────────────── Time
```

The time between consecutive peaks is your lap time. The signal processing pipeline is tuned with sensible defaults out of the box, with a single Pipeline Smoothing slider for fine-tuning the balance between responsiveness and noise rejection.

---

## Що треба

- Маніфести збірки: PlatformIO (platformio.ini).

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## Супутні документи в теці

- [`docs/FEATURES.md`](../../fpv-library/repos/FPVRaceOne-A-personal-FPV-race-timing-solution-that/docs/FEATURES.md)
- [`docs/GETTING_STARTED.md`](../../fpv-library/repos/FPVRaceOne-A-personal-FPV-race-timing-solution-that/docs/GETTING_STARTED.md)
- [`docs/USER_GUIDE.md`](../../fpv-library/repos/FPVRaceOne-A-personal-FPV-race-timing-solution-that/docs/USER_GUIDE.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/FPVRaceOne-A-personal-FPV-race-timing-solution-that/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/ramiss__FPVRaceOne.md`.
