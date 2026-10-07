# FPVCamera

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [OpenHD/FPVCamera](https://github.com/OpenHD/FPVCamera) |
| Локальна тека | `fpv-library/repos/FPVCamera-Describe-the-Specifications-for-an-ideal` |
| У бібліотеці | keep |
| Категорії каталогу | `link` |
| Зірки (каталог) | 6 |
| Оновлено upstream | 2021-03-12 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

Describe the Specifications for an ideal digital FPV Camera compatible with OpenHD

_З README.md, без переказу._

## Для чого

Describe the Specifications for an ideal FPV Camera compatible with OpenHD

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Describe the Specifications for an ideal FPV Camera compatible with OpenHD

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `README.md`

Типи файлів за вибіркою (2 файлів, глибина до 3): Markdown (1), JSON (1).


## Що треба

### 3. Latency requirements:

To provide a good user experience, an Ideal OpenHD FPV Camera must fulfill the following requirements:
1. Encode the raw image sensor data as quick as possible with h264/h265 and forward the h264/h265 NALUs via USB without any buffering
2. Use h264/h265 encoding parameters that not only allow the stream to be encoded quickly by the encoder HW, but also allow it to be **decoded quickly and without any buffering**.
3. As a quideline, the minimum requirements are:
   - Configure the stream such that the encoder only produces I or P frames, ideally only I frames. One way to do this is to use the h264 "Baseline" profile
   - Configure the stream such that the decoder knows that no picture re-ordering is possible. One way to do this is to set pic_order_cnt_type to 2
   - Configure the encoder such that the encoding time is not more than 20ms, ideally lower for both 720p60 / 1080p60
### 4. Resolution / Framerate requirements:

To be usable for FPV, the minimum requirements for a live FPV feed are 720p60fps. More expensive configurations like 1080p60 or 720p120 would be nice.
### 4. Size requirements:

The whole unit (image sensor and encoder) shall be as light and small as possible since it is always mounted on an aircraft or "drone"


## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/FPVCamera-Describe-the-Specifications-for-an-ideal/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/OpenHD__FPVCamera.md`.
