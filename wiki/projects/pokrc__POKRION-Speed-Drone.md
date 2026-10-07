# POKRION — High-Speed Micro Quadcopter Platform

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [pokrc/POKRION-Speed-Drone](https://github.com/pokrc/POKRION-Speed-Drone) |
| Локальна тека | `fpv-library/repos/POKRION-Speed-Drone-Open-high-speed-micro-quadcopter-R-D-pla` |
| У бібліотеці | keep |
| Категорії каталогу | `link`, `fc` |
| Зірки (каталог) | 95 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | CC |

## Ідея

If this platform makes a build or test easier to reproduce, <a href="https://github.com/pokrc/POKRION-Speed-Drone/stargazers">Star it</a> to keep open high-speed micro-drone work discoverable.

**POKRION** is an experimental, high-speed micro quadcopter platform developed by the POK-RC team. It combines lightweight airframe design, aerodynamic fairings, high-power micro motors, digital video, and Blackbox-driven flight-test iteration.

This repository is intended to make the design easier to inspect, reproduce, discuss, and improve. It is an engineering reference—not a certified aircraft, a universal build recipe, or a guarantee of speed, flight time, or structural safety.

> **Current status:** active experimental development. Dimensions, materials, propellers, electronics, and flight-control settings may change between revisions. Always inspect the files and configuration before manufa…

_З README.md, без переказу._

## Для чого

Open high-speed micro quadcopter R&D platform with printable airframe references and reproducible Blackbox flight tests.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «betaflight».


Теми GitHub: `3d-printed-drone`, `3d-printing`, `aerodynamics`, `betaflight`, `blackbox`, `cad`, `drone`, `fpv`, `fpv-drone`, `high-speed-drone`, `micro-drone`, `micro-quadcopter`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Open high-speed micro quadcopter R&D platform with printable airframe references and reproducible Blackbox flight tests.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `3d_printed_parts/`
- `assets/`
- `betaflight_config.txt`
- `carbon_fiber_frame/`
- `CITATION.cff`
- `cnc_motor_mount/`
- `CONTRIBUTING.md`
- `guinness_rules_cn.pdf`
- `guinness_rules_en.pdf`
- `LICENSE.txt`
- `propellers/`
- `README.md`

Типи файлів за вибіркою (24 файлів, глибина до 3): .stl (9), .3mf (3), .txt (2), Markdown (2), .pdf (2), (без суфікса) (2).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Build workflow

1. **Choose a revision.** Record the commit, file names, material, print process, and hardware revision before starting.
2. **Inspect the geometry.** Check wall thickness, clearances, motor-hole pattern, propeller clearance, cooling paths, antenna clearance, and battery retention.
3. **Validate the manufacturing process.** Confirm printer calibration, material drying, layer adhesion, anisotropy, support strategy, and post-processing.
4. **Check the power system.** Verify motor/propeller load, ESC current capability, battery voltage, connector quality, polarity, solder joints, and insulation.
5. **Dry-fit before power.** Confirm that no printed part, fastener, cable, or fairing can contact a motor bell or propeller arc.
6. **Bench test without propellers.** Verify motor order/direction, receiver failsafe, arming logic, current-sensor sanity, video, GPS, and Blackbox logging.
7. **Perform a short controlled flight test.** Use a legal, clear area and a known-good battery and propeller set. Land early if temperature, sound, vibration, or control response is abnormal.
8. **Record evidence.** Save the configuration backup, flight log, battery state, weather, test duration, peak current, motor temperature, and any incident.

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../fpv-library/repos/POKRION-Speed-Drone-Open-high-speed-micro-quadcopter-R-D-pla/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/POKRION-Speed-Drone-Open-high-speed-micro-quadcopter-R-D-pla/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/pokrc__POKRION-Speed-Drone.md`.
