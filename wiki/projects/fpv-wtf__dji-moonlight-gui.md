# dji-moonlight-gui

> Картка виставки. Зал: [Окуляри і VRX](../halls/goggles.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [fpv-wtf/dji-moonlight-gui](https://github.com/fpv-wtf/dji-moonlight-gui) |
| Локальна тека | `fpv-library/repos/dji-moonlight-gui` |
| У бібліотеці | keep |
| Категорії каталогу | `goggles` |
| Зірки (каталог) | 41 |
| Оновлено upstream | 2024-01-05 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

Stream games via Moonlight and [fpv.wtf](https://github.com/fpv-wtf) to your DJI FPV Goggles!

The DJI Moonlight project is made up of three parts:

goggle-side app that displays a video stream coming in over USB. Windows app that streams games to the shim via Moonlight and friends. _You are here._ fork of Moonlight Embedded that can stream to the shim. The GUI app uses this internally.

Latency is good, in the 7-14ms range at 120Hz (w/ 5900X + 3080Ti via GeForce Experience).

_З README.md, без переказу._

## Для чого

Stream games via Moonlight and [fpv.wtf](https://github.com/fpv-wtf) to your DJI FPV Goggles!

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «goggles».


## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `assets/`
- `go.mod`
- `go.sum`
- `LICENSE`
- `main.go`
- `media/`
- `README.md`

Типи файлів за вибіркою (15 файлів, глибина до 3): .png (4), CSS (2), (без суфікса) (1), .mod (1), Markdown (1), .sum (1).


## Що треба

- Маніфести збірки: Go (go.mod).

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/dji-moonlight-gui/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/fpv-wtf__dji-moonlight-gui.md`.
