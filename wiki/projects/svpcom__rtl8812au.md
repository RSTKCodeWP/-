# svpcom/rtl8812au

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [svpcom/rtl8812au](https://github.com/svpcom/rtl8812au) |
| Локальна тека | `fpv-library/repos/rtl8812au-Patched-rtl88xxau-drivers-for-wfb-ng` |
| У бібліотеці | keep |
| Категорії каталогу | `link` |
| Зірки (каталог) | 157 |
| Оновлено upstream | 2026-07-28 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

Patched rtl88xxau drivers for wfb-ng

_З поля description у catalog.json. Окремого вступу в README немає._

## Для чого

Patched rtl88xxau drivers for wfb-ng

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Інженер радіолінка — у тексті є «wfb-ng».


Теми GitHub: `packet-injection`, `rtl8812au`, `wifibroadcast`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Patched rtl88xxau drivers for wfb-ng

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `core/`
- `dkms-install.sh`
- `dkms-remove.sh`
- `dkms.conf`
- `documents/`
- `hal/`
- `include/`
- `Kconfig`
- `LICENSE`
- `Makefile`
- `os_dep/`
- `platform/`
- `README.md`
- `realtek_88XXau.conf`
- `Realtek_Changelog.txt`
- `tools/`

Типи файлів за вибіркою (520 файлів, глибина до 3): C (463), .pdf (26), .conf (5), (без суфікса) (4), .txt (3), .zip (3).


## Що треба

- Маніфести збірки: Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation of Driver

In order to install the driver open a terminal in the directory with the source code and execute the following command:
```
$ sudo ./dkms-install.sh
```
### Build / Install with Make

For building & installing the driver with 'make' use
```
$ make
$ make install
```
### Download / Build / Install

Download
```
$ git clone -b v5.2.20 https://github.com/svpcom/rtl8812au.git
$ cd rtl*
```
Package / Build dependencies (Kali)
```
$ apt-get install build-essential
$ apt-get install bc
$ apt-get install libelf-dev
$ apt-get install linux-headers-`uname -r`
```
For Raspberry (RPI 2/3) you will need kernel sources
```
$ wget "https://raw.githubusercontent.com/notro/rpi-source/master/rpi-source" -O /usr/bin/rpi-source
$ chmod 755 /usr/bin/rpi-source
$ rpi-source 
```
Then you need to download and compile the driver on the RPI
```
$ git clone https://github.com/aircrack-ng/rtl8812au -b v5.2.20
$ cd rtl*
$ make
$ cp 8812au.ko /lib/modules/`uname -r`/kernel/drivers/net/wireless
$ depmod -a
$ modprobe 88XXau
```
then run this step to change platform in Makefile, For RPI 2/3:
```
$ sed -i 's/CONFIG_PLATFORM_I386_PC = y/CONFIG_PLATFORM_I386_PC = n/g' Makefile
$ sed -i 's/CONFIG_PLATFORM_ARM_RPI = n/CONFIG_PLATFORM_ARM_RPI = y/g' Makefile
```
But for RPI 3 B+ you will need to run those below
which builds the ARM64 arch driver:
```
$ sed -i 's/CONFIG_PLATFORM_I386_PC = y/CONFIG_PLATFORM_I386_PC = n/g' Makefile
$ sed -i 's/CONFIG_PLATFORM_ARM64_RPI = n/CONFIG_PLATFORM_ARM64_RPI = y/g' Makefile
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/rtl8812au-Patched-rtl88xxau-drivers-for-wfb-ng/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/svpcom__rtl8812au.md`.
