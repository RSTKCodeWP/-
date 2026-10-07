# PhotonFlight: Fiber-Optic Autonomous UAV

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [mervinnguyen/photonflight-fiber-optic-drone](https://github.com/mervinnguyen/photonflight-fiber-optic-drone) |
| Локальна тека | `fpv-library/repos/photonflight-fiber-optic-drone-Fiber-optic-tethered-autonomous-quadcopt` |
| У бібліотеці | keep |
| Категорії каталогу | `fiber`, `fc`, `ai` |
| Зірки (каталог) | 4 |
| Оновлено upstream | 2026-07-20 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

PhotonFlight is a **fiber-optic-tethered autonomous quadcopter** designed for operation in **RF-denied or GPS-degraded environments**.

The platform replaces traditional RF telemetry with a **secure bidirectional SFP fiber link**, enabling **low-latency video streaming, real-time telemetry, and reliable command/control communication** between the UAV and ground control station.

The system integrates **ArduPilot flight control, embedded Linux module, onboard AI vision processing, and fiber-optic networking**, demonstrating a complete embedded system spanning hardware, firmware, networking, and autonomy.

_З README.md, без переказу._

## Для чого

Fiber-optic-tethered autonomous quadcopter, integrating ArduPilot flight control, onboard AI vision, and real-time telemetry to a ground station.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Розробник польотного контролера — у тексті є «ardupilot».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Fiber-optic-tethered autonomous quadcopter, integrating ArduPilot flight control, onboard AI vision, and real-time telemetry to a ground station.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `3D Printed Parts/`
- `Ground Station Scripts/`
- `LICENSE`
- `Project Files/`
- `README.md`
- `Vision Tracking pipeline/`

Типи файлів за вибіркою (25 файлів, глибина до 3): .jpg (10), (без суфікса) (3), Markdown (3), .png (3), Python (2), .pdf (2).

Фрагмент README про будову:

### System Architecture

PhotonFlight is composed of several integrated system layers that enable flight control, telemetry transmission, and onboard intelligence.


Each layer performs a specific role in the overall system.

| Layer | Responsibility |
|------|------|
| Ground Control Station | Mission planning, telemetry monitoring, system control |
| Fiber Communication Layer | Secure telemetry and high-bandwidth video transmission |
| Companion Computer | AI inference, video processing, communication bridging |
| Flight Controller | Real-time stabilization, sensor fusion, flight control |
| Motor Control | Direct actuation of propulsion system |


---
### Hardware Architecture

PhotonFlight is built using a combination of **commercial off-the-shelf components and custom fabricated hardware**.

## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/photonflight-fiber-optic-drone-Fiber-optic-tethered-autonomous-quadcopt/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/mervinnguyen__photonflight-fiber-optic-drone.md`.
