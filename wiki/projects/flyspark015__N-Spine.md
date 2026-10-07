# Tethered 10″ FPV Drone — complete build report (100 m prototype → 200 m)

> Картка виставки. Зал: [Оптика і трос](../halls/fiber.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [flyspark015/N-Spine](https://github.com/flyspark015/N-Spine) |
| Локальна тека | `fpv-library/repos/N-Spine-High-voltage-360-400-VDC-ground-to-air-t` |
| У бібліотеці | keep |
| Категорії каталогу | `fiber` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2025-11-10 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

I’m not going to sugarcoat this: a 10″ quad on a 4-in-1 **80 A / 6 S ESC** is hungry. Pushing **low voltage** up a long tether is wasted heat. The way this actually works at 100–200 m is a **high-voltage DC bus on the tether**, a **lightweight HV→LV DC/DC on the airframe**, and **single-mode fiber** for data. Here’s the plan that closes electrically and mechanically—with sources.

_З README.md, без переказу._

## Для чого

High-voltage (360–400 VDC) ground-to-air tether + single-mode fiber link for 10″ FPV drones. Onboard isolated 24 V bus, buffer-battery failover, and a 100–200 m lightweight hybrid cable (power ±, 1×SMF). Safety-first architecture, BOM, wiring, and test plans.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: High-voltage (360–400 VDC) ground-to-air tether + single-mode fiber link for 10″ FPV drones. Onboard isolated 24 V bus, buffer-battery failover, and a 100–200 m lightweight hybrid cable (power ±, 1×SMF). Safety-first architecture, BOM, wiring, and test plans.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `more.md`
- `README.md`

Типи файлів за вибіркою (3 файлів, глибина до 3): Markdown (2), JSON (1).

Фрагмент README про будову:

### 2) System architecture that actually closes

```
230 VAC mains
  → RCCB/MCB → EMI line filter
  → PFC front-end → regulated ~360 VDC HV bus (ground)
  → Tether (Gore RCN9166: +HV, –HV, single-mode fiber)
  → Airframe: HV→LV bus converter (≈384→24 V)
  → 6S rail to 4-in-1 80A ESC + avionics
  → Data: 1000BASE-LX (1310 nm) SFP over the same SMF
```

* **Ground HV source:** **TDK-Lambda PF-A** PFC modules convert AC→**regulated 360 VDC**. Models: **PF500A-360** (504–756 W) and **PF1000A-360** (1008–1512 W). Can parallel for more power. ([TDK Product][2])
* **Airframe DC/DC (lightweight):** **Vicor BCM6123 (K=1/16)** runs from **260–410 VDC** primary and outputs an isolated, ratiometric **~24 V** secondary, **up to 62.5 A**, in a **61 × 25 × 7 mm, ~41 g** package—this is why it’s used in UAV bus architectures. ([Vicorpower][3])
* **Heavier fallback (still valid):** **TDK-Lambda PH1200A280-24**, **200–425 VDC in → 24 V / 50 A**, 1.2 kW. ([mouser.com][4])
* **Data over fiber:** Use **1000BASE-LX SFPs (1310 nm, 10 km on 9/125 SMF)** and tiny SFP media converters (e.g., TP-Link **MC220L**). LX matches Gore’s **single-mode** fiber. ([img-en.fs.com][5])

---

## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 10) What you can build this week (realistic milestones)

* **Days 1–3:** PF500A-360 → 10 m tether → BCM6123 → dummy load. Validate temps and the LX link. ([TDK Product][2])
* **Days 4–7:** 100 m RCN9166, add OR-FET/inrush, start tethered hovers ≤ 800 W. ([Gore][1])
* **Next:** upgrade to ≥1 kW PF-A, integrate motorized reel + FORJ, extend to 200 m. ([TDK Product][2])

---

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/N-Spine-High-voltage-360-400-VDC-ground-to-air-t/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/flyspark015__N-Spine.md`.
