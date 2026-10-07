# IMPORTANT

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [fpv-wtf/msp-osd](https://github.com/fpv-wtf/msp-osd) |
| Локальна тека | `fpv-library/repos/msp-osd-MSP-DisplayPort-OSD` |
| У бібліотеці | keep |
| Категорії каталогу | `osd`, `fc`, `goggles` |
| Зірки (каталог) | 262 |
| Оновлено upstream | 2024-12-02 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

As of msp-osd v0.12+, the required font format has now changed for the goggles and the OSD Overlay tool.  Support for .bin font file format has been removed in favour of .png font file format. See the 'Fonts' section and the 'Overlaying OSD on DVR' sections further below for clarification.

_З README.md, без переказу._

## Для чого

MSP DisplayPort OSD

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «goggles».
- Розробник польотного контролера — у тексті є «betaflight».


Теми GitHub: `ardupilot`, `arduplane`, `betaflight`, `displayport`, `dji`, `fpv`, `inav`, `msp`, `osd`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: MSP DisplayPort OSD

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `bold.png`
- `config/`
- `dictionaries/`
- `docs/`
- `FAKEHD.md`
- `fonts/`
- `ipk/`
- `jni/`
- `libshims/`
- `LICENSE`
- `Makefile`
- `Makefile.dji`
- `Makefile.unix`
- `README.md`

Типи файлів за вибіркою (124 файлів, глибина до 3): C (50), .png (43), (без суфікса) (13), JSON (9), Markdown (2), .mk (2).


## Що треба

- Маніфести збірки: Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Easy Installation

* Install WTFOS from https://fpv.wtf. WTFOS must be installed on both the goggles and each AU/Vista.
* Install the msp-osd package on each device using WTFOS.
* Reboot.
### Flight Controller Setup

* Ensure that the correct UART is set to use MSP
* Enable MSP DisplayPort
### Custom Build Installation (Goggles)

There's a slightly different process for V1 vs V2 Goggles, they renamed some bits between the two.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/msp-osd-MSP-DisplayPort-OSD/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/fpv-wtf__msp-osd.md`.
