# Frequency Hopping Radio Videolink Anti‑Interference Radio Drone Image Link (FH‑VLink)

> Картка виставки. Зал: [Радіо](../halls/radio.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [flyspark015/NexusLink](https://github.com/flyspark015/NexusLink) |
| Локальна тека | `fpv-library/repos/NexusLink-NexusLink-is-a-long-range-dual-role-TX-R` |
| У бібліотеці | keep |
| Категорії каталогу | `radio`, `elrs` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2025-10-29 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

**Long‑Range, Frequency‑Hopping, Dual‑Role Digital Link for FPV Drones**

> One system that handles **control** *and* **video/data**, with **adaptive frequency‑hopping** across modular RF bands. Designed for long‑range FPV, anti‑jam robustness, and developer extensibility.

_З README.md, без переказу._

## Для чого

NexusLink is a long-range, dual-role TX/RX for FPV that carries low-latency H.265 video and a deterministic control link over adaptive frequency-hopping across modular bands (Sub-GHz/1.3/2.4/5.8 GHz). It auto-avoids interference, supports CRSF/MAVLink, AES-GCM security, and region profiles.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Інженер радіолінка — у тексті є «elrs».
- Розробник відеотракту — у тексті є «h.265».


## Функція

Список із розділу features / можливості в README:

- **Dual‑Role**: Each unit can **transmit & receive**; supports **TDD** framing for simultaneous video downlink + control uplink.
- **Adaptive FHSS**: Fast frequency hopping for control; **channel‑agile** OFDM for video with blacklist/whitelist and DFS‑aware scanning.
- **Multi‑Band** (modular): Pluggable RF “BandPacks” covering **Sub‑GHz**, **1.2–1.3 GHz**, **2.4 GHz**, **5.1–5.9 GHz**, with roadmap to **6 GHz**.
- **Anti‑Jam Suite**: fast hop reseeding, interference maps, notch filters,
- **Low Latency Video**: Target **≤35 ms** 720p60; **≤90 ms** 1080p60 (encoder + PHY + jitter buffer).
- **ELRS/CRSF Friendly**: Native CRSF serial bridge; supports passthrough to FC.
- **Secure**: Mutual auth, per‑session keys, **AES‑GCM** stream encryption.
- **Telemetry & Mavlink**: bidirectional data pipe; OSD overlay hooks.
- **Open SDK**: C/C++/Python APIs; message schemas; logging and RF diagnostics.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `README.md`

Типи файлів за вибіркою (2 файлів, глибина до 3): Markdown (1), JSON (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 16) Developer Quickstart (Draft)

```bash
# 1) Build containers
make containers

# 2) Build SDR kernels & drivers
./tools/build_sdr.sh

# 3) Build firmware (ctrl + vid)
make -C firmware all TARGET=au
make -C firmware all TARGET=gu

# 4) Ground UI
cd software/ground-app && npm i && npm run dev

# 5) Pairing (dev keys)
./tools/pair --gu usb0 --au usb1 --region IN_WPC
```

---

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/NexusLink-NexusLink-is-a-long-range-dual-role-TX-R/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/flyspark015__NexusLink.md`.
