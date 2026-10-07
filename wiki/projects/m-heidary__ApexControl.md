# ApexControl Ground Station

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [m-heidary/ApexControl](https://github.com/m-heidary/ApexControl) |
| Локальна тека | `fpv-library/repos/ApexControl-ApexControl-Ground-Station-is-a-cross-pl` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `fc` |
| Зірки (каталог) | 2 |
| Оновлено upstream | 2026-06-26 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

ApexControl Ground Station is a cross-platform ground control application built with **.NET MAUI** for monitoring and controlling MAVLink-compatible drones and autopilots.

The project focuses on receiving real-time telemetry, displaying vehicle health, GPS status, flight state, command acknowledgements, and providing basic vehicle commands such as arm, disarm, mode switching, and takeoff.

_З README.md, без переказу._

## Для чого

ApexControl Ground Station is a cross-platform MAVLink ground control application built with .NET MAUI. It provides a responsive dashboard for receiving live drone telemetry, monitoring link health, viewing GPS and flight status, and sending basic vehicle commands such as arm, disarm, mode switching, and takeoff.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `autopilot`, `cross-platform`, `csharp`, `dotnet`, `dotnet-maui`, `drone`, `gcs`, `ground-control-station`, `mavlink`, `mvvm`, `px4`.

## Функція

Список із розділу features / можливості в README:

- Cross-platform UI using .NET MAUI
- Separate mobile and desktop layouts
- MAVLink telemetry listener over UDP
- Heartbeat monitoring
- Link health detection
- GPS status and freshness monitoring
- Position telemetry display
- VFR HUD telemetry support
- Battery telemetry display
- MAVLink command sending
- Command acknowledgement tracking
- Pre-arm and status text display

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `ApexControl/`
- `ApexControl.App/`
- `ApexControl.Core/`
- `ApexControl.sln`
- `README.md`

Типи файлів за вибіркою (54 файлів, глибина до 3): .cs (23), .xaml (8), .csproj (3), .svg (3), .plist (3), JSON (2).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ApexControl-ApexControl-Ground-Station-is-a-cross-pl/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/m-heidary__ApexControl.md`.
