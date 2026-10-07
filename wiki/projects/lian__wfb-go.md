# wfb-go

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [lian/wfb-go](https://github.com/lian/wfb-go) |
| Локальна тека | `fpv-library/repos/wfb-go-Pure-Go-implementation-of-wfb-ng-for-low` |
| У бібліотеці | keep |
| Категорії каталогу | `link` |
| Зірки (каталог) | 10 |
| Оновлено upstream | 2026-03-11 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

A pure Go implementation of [wfb-ng](https://github.com/svpcom/wfb-ng) (WiFi Broadcast Next Generation), providing low-latency video transmission over WiFi using packet injection and FEC (Forward Error Correction).

_З README.md, без переказу._

## Для чого

Pure Go implementation of wfb-ng for low-latency FPV video over WiFi. Ground station with browser-based video player and stats dashboard.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground station».
- Інженер радіолінка — у тексті є «wfb-ng».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Pure Go implementation of wfb-ng for low-latency FPV video over WiFi. Ground station with browser-based video player and stats dashboard.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `build.sh`
- `cmd/`
- `examples/`
- `go.mod`
- `go.sum`
- `LICENSE`
- `pkg/`
- `README.md`

Типи файлів за вибіркою (103 файлів, глибина до 3): Go (73), Markdown (20), (без суфікса) (2), .key (2), YAML (2), .mod (1).

Фрагмент README про будову:

### How It Works

```
Camera --[UDP/RTP]--> wfb_tx --//--[ RADIO ]--//--> wfb_rx --[UDP/RTP]--> Decoder
                         │                            │
                    [FEC encode]                 [FEC decode]
                    [Encrypt]                    [Decrypt]
                    [Inject]                     [Capture]
```

WiFi cards are put into monitor mode, allowing transmission and reception of raw 802.11 frames without association. This bypasses normal WiFi overhead (ACKs, retries, association) for minimum latency.

## Що треба

### Requirements

- Linux kernel 4.x+ with monitor mode support
- WiFi adapter with monitor mode and packet injection
- Root privileges (for raw sockets and monitor mode)

- Маніфести збірки: Go (go.mod).

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/wfb-go-Pure-Go-implementation-of-wfb-ng-for-low/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/lian__wfb-go.md`.
