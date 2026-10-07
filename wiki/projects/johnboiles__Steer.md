# Steer

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [johnboiles/Steer](https://github.com/johnboiles/Steer) |
| Локальна тека | `Steer-iOS-RC-Car-FPV` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | LGPL |

## Ідея

iOS app for driving a remote controlled car from an iPhone with an IP camera FPV (first-person view) stream.

Originally created by [John Boiles](https://github.com/johnboiles). Source: [johnboiles/Steer](https://github.com/johnboiles/Steer).

_З README.md, без переказу._

## Для чого

iOS app for driving a remote controlled car from an iPhone with an IP camera FPV (first-person view) stream.

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник відеотракту — у тексті є «rtsp».


## Функція

Список із розділу features / можливості в README:

- **FPV video** — RTSP/IP camera stream via FFmpeg/OpenGL ES
- **Dual joystick** — touch-based steering and throttle
- **Accelerometer control** — tilt-to-steer mode
- **UDP car control** — sends commands to the RC car over the network
- **Configuration** — IP address, stream URL, and control settings

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `Classes/`
- `FFMPEG/`
- `Libraries/`
- `main.m`
- `README`
- `README.md`
- `Resources/`
- `ServerTest.c`
- `Steer-Info.plist`
- `Steer.xcodeproj/`
- `Steer_Prefix.pch`

Типи файлів за вибіркою (376 файлів, глибина до 3): C (327), .m (24), .a (7), .png (6), .mode1v3 (3), .pbxuser (3).


## Що треба

### Requirements

- macOS with Xcode (legacy iOS project, circa 2010)
- iOS device or simulator (older SDK; may need project updates for modern Xcode)
- Network-connected RC car with UDP control receiver
- IP camera or RTSP stream for FPV


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Build

1. Open `Steer.xcodeproj` in Xcode on macOS.
2. Select your target device or simulator.
3. Build and run (⌘R).

> **Note:** This project targets legacy iOS APIs (pre-ARC, UIApplicationMain delegate pattern). Building on current Xcode may require SDK and deployment target updates.

## З чого зібрана картка

`catalog.json`, `Steer-iOS-RC-Car-FPV/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/johnboiles__Steer.md`.
