# Mavlink Ardupilot Telemetry and HD video via LTE (4G):

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [KenLagoni/OpenHD-LTE](https://github.com/KenLagoni/OpenHD-LTE) |
| Локальна тека | `fpv-library/repos/OpenHD-LTE-Mavlink-Ardupilot-Telemetry-and-HD-video` |
| У бібліотеці | keep |
| Категорії каталогу | `link`, `fc` |
| Зірки (каталог) | 71 |
| Оновлено upstream | 2021-12-21 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

### Introduction

This is based on my project [MavlinkGPRS](https://github.com/KenLagoni/MavlinkGPRS) flying with 2G telemetry link, but this time I want to ad HD video streaming also and thus stepping up to 4G (LTE).

The hardware is build from standard components and put together with som 3d-printing to give the camera a "Run-Cam" look.

_З README.md, без переказу._

## Для чого

Mavlink Ardupilot Telemetry and HD video via LTE (4G) with multiple client support

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».
- Розробник відеотракту — у тексті є «rtsp».


## Функція

Список із розділу features / можливості в README:

- Record video up to 1920p30 / 720p60.
- Stream video to groundstation via 4G LTE network. (Lagenchy ~0.7s).
- Output analog video.
- Input Mavlink telermetry for digial OSD using the [OpenHD](https://github.com/OpenHD/Open.HD)
- Camera size: 103x35x28mm (not including antenna).
- Groundstaiton shares video feed via RTSP protocol using the [rtsp-simple-server](https://github.com/aler9/rtsp-simple-server) project.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `air/`
- `build.sh`
- `ground-OpenHD/`
- `ground-VideoRecord/`
- `images/`
- `README.md`
- `src/`
- `update.sh`

Типи файлів за вибіркою (382 файлів, глибина до 3): C (317), shell (19), .xml (14), .png (12), C++ (11), Markdown (3).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### How to Build

Start with the ground pi for recording, since it is needed on the network to install the air side.\
-For instructions on how to create the ground-side SD card see [Here](https://github.com/KenLagoni/OpenHD-LTE/tree/main/ground-VideoRecord)\
-For instructions on how to create the ground-side OpenHD SD card see [Here](https://github.com/KenLagoni/OpenHD-LTE/tree/main/ground-OpenHD)\
-For instructions on how to create the air-side SD card see [Here](https://github.com/KenLagoni/OpenHD-LTE/tree/main/air).

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/OpenHD-LTE-Mavlink-Ardupilot-Telemetry-and-HD-video/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/KenLagoni__OpenHD-LTE.md`.
