# ADOS Android GCS

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [altnautica/ADOSAndroidGCS](https://github.com/altnautica/ADOSAndroidGCS) |
| Локальна тека | `fpv-library/repos/ADOSAndroidGCS-ADOS-Android-GCS-Native-Kotlin-ground-co` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs` |
| Зірки (каталог) | 3 |
| Оновлено upstream | 2026-07-27 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

Native Android ground control station for the ADOS drone ecosystem. Built with Kotlin 2.0 and Jetpack Compose for tablets and phones running Android 10+.

_З README.md, без переказу._

## Для чого

ADOS Android GCS — Native Kotlin ground control station for autonomous drones. WebRTC video, MAVLink telemetry, offline maps, agriculture mode.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Інженер радіолінка — у тексті є «mavlink».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: ADOS Android GCS — Native Kotlin ground control station for autonomous drones. WebRTC video, MAVLink telemetry, offline maps, agriculture mode.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `app/`
- `build.gradle.kts`
- `CONTRIBUTING.md`
- `gradle/`
- `gradle.properties`
- `gradlew`
- `gradlew.bat`
- `LICENSE`
- `README.md`
- `settings.gradle.kts`

Типи файлів за вибіркою (16 файлів, глибина до 3): .kts (3), (без суфікса) (3), Markdown (3), .properties (2), .bat (1), JSON (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Build

Requirements: Android Studio Ladybug or later, JDK 17, Android SDK 34.

```bash
git clone https://github.com/altnautica/ADOSAndroidGCS.git
cd ADOSAndroidGCS
./gradlew assembleDebug
```

The debug APK lands in `app/build/outputs/apk/debug/`.

To run tests:

```bash
./gradlew test
```

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../fpv-library/repos/ADOSAndroidGCS-ADOS-Android-GCS-Native-Kotlin-ground-co/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ADOSAndroidGCS-ADOS-Android-GCS-Native-Kotlin-ground-co/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/altnautica__ADOSAndroidGCS.md`.
