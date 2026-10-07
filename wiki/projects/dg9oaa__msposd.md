# MSPOSD

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [dg9oaa/msposd](https://github.com/dg9oaa/msposd) |
| Локальна тека | `fpv-library/repos/msposd-OpenIPC-implementation-of-MSP-Displaypor` |
| У бібліотеці | keep |
| Категорії каталогу | `osd`, `fc`, `openipc` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2025-05-20 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

A tool for drawing betaflight/inav/ardupilot MSP Display Port OSD over OpenIPC video stream.

**Click the image below to watch a video sample:**

**Support for two font sizes.** (on FullHD mode only!) set --matrix  to a value 11 or higher, each value represents a template to be used to map the OSD config. #!/bin/sh cp /etc/wfb.conf /etc/wfb.conf_before_safeboot cp /etc/majestic.yaml /etc/majestic.yaml_before_safeboot cp /etc/wfb.conf_safeboot /etc/wfb.conf cp /etc/majestic.yaml_safeboot /etc/majestic.yaml reboot echo "Custom Message... &L04 &F22 CPU:&C &B temp:&T\n Line 2 with more data" >/tmp/MSPOSD.msg will show three lines of text, each with different color and size. Unicode font characters can be specified with hexadecimal escape sequences in a C string literal. ```xEF\x80\x92 some battery``` will show battery symbol if present in the ttf font file used.

_З README.md, без переказу._

## Для чого

OpenIPC implementation of MSP Displayport OSD for INAV/Betaflight/ArduPilot

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «betaflight».
- Розробник відеотракту — у тексті є «openipc».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: OpenIPC implementation of MSP Displayport OSD for INAV/Betaflight/ArduPilot

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `bmp/`
- `build.sh`
- `build_rockchip.sh`
- `compat.c`
- `develepment_notes.txt`
- `fonts/`
- `HowToSimulateInFlightMSPData.txt`
- `libpng/`
- `LICENSE`
- `Makefile`
- `mavlink/`
- `msposd.c`
- `msposd.h`
- `msposd_x`
- `osd/`
- `osd.c`
- `osd.h`
- `pics/`
- `README.md`
- `run_desktop.sh`
- `safeboot.sh`
- `sdk/`

Типи файлів за вибіркою (605 файлів, глибина до 3): C (572), .png (14), (без суфікса) (7), shell (4), .txt (2), Markdown (1).


## Що треба

- Маніфести збірки: Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Usage Example:

```
msposd  --master /dev/ttyS2 --baudrate 115200 -c 7 -c 9 -osd -r 20 --ahi 1 -v
```
Read on  UART2 with baudrade 115200 and listen for value changes of RC channel 7 and channel 9 that come from the Remote Control via Flight Controller.
Every time the value is changed with more than 5% the bash script ```channels.sh {Channel} {Value}``` will be started with the provided parameters.  
Forward MSP to UDP port 14555 so that it can be handled by wfb-ng and sent to the ground.
Draw an Artificial Horizon Indicator (AHI) Ladder with color-coded vertical steps.
The refresh rate of the OSD is limited to 20 frames per second, depending on the Flight Controller and MSP DisplayPort implementation, usually ranging between 12 and 17 frames per second.

Font files for each Flight Controller firmware have two versions—one for 720p and one for 1080p resolutions. They should be named **font_hd.png** and **font.png** respectively, and saved in the **/usr/bin** folder on the camera.
They vary depending on the Flight Controller, so choose the appropriate pair.
The program will read from /etc/majestic.yaml and will select the type of font to use based on the video resolution configured there.
### To install:

Copy msposd for the architecture you need on the cam.  
Prebuild binaries for x86, SigmaStar, Goke and Hisilicon are at release/ folder.  
**For SigmaStar** based SoC (ssc338q, sc30kq) :
```
curl -L -o /usr/bin/msposd https://github.com/OpenIPC/msposd/releases/download/latest/msposd_star6e  
chmod 755 /usr/bin/msposd
```

___Since Nov 2024___ Program automatically selects the appropriate font file for the FC software used.  
font_inav.png/font_inav_hd.png | font_btfl.png/font_btfl_hd.png | font_ardu.png/font_ardu_hd.png files must be present in ```/usr/share/fonts/```


**To skip the autodetect, you can copy only the font files for the FC software you plan to use**  
**For INAV**:
```
mkdir /usr/share/fonts
curl -k -L -o /usr/share/fonts/font.png https://raw.githubusercontent.com/openipc/msposd/main/fonts/font_inav.png
curl -k -L -o /usr/share/fonts/font_hd.png https://raw.githubusercontent.com/openipc/msposd/main/fonts/font_inav_hd.png
```

**For Betaflight**: 
```
mkdir /usr/share/fonts
curl -k -L -o /usr/share/fonts/font.png https://raw.githubusercontent.com/openipc/msposd/main/fonts/font_btfl.png
curl -k -L -o /usr/share/fonts/font_hd.png https://raw.githubusercontent.com/openipc/msposd/main/fonts/font_btfl_hd.png
```

**For Ardupilot**:  
Set  
```SERIALx_PROTOCOL = 42``` replace x with the UART number.  
```OSD_TYPE = 5```  
To use betaflight fonts, set ```MSP_OPTIONS = 5``` and copy fonts for betaflight as shown above.
If you prefer to use ardupilot "native" fonts (more icons), then set ```MSP_OPTIONS = 0``` and copy the fonts below.
```
mkdir /usr/share/fonts
curl -k -L -o /usr/share/fonts/font.png https://raw.githubusercontent.com/openipc/msposd/main/fonts/font_ardu.png
curl -k -L -o /usr/share/fonts/font_hd.png https://raw.githubusercontent.com/openipc/msposd/main/fonts/font_ardu_hd.png
```

Start msposd or reference it in OpenIPC boot scripts.
### To install on Goke/HiSilicon camera

```
curl -L -o /usr/bin/msposd curl -L -o /usr/bin/msposd https://github.com/OpenIPC/msposd/releases/download/latest/msposd_goke 
#or
curl -L -o /usr/bin/msposd curl -L -o /usr/bin/msposd https://github.com/OpenIPC/msposd/releases/download/latest/msposd_hisi 
chmod 755 /usr/bin/msposd
#Download an additional driver for Region Module
curl -k -L -o /lib/modules/4.9.37/goke/gk7205v200_rgn.ko https://github.com/OpenIPC/firmware/raw/89ded200eba00726930b8307ddaf573ac449f076/general/package/goke-osdrv-gk7205v200/files/kmod/gk7205v200_rgn.ko
sed -i "s!#insmod gk7205v200_rgn.ko!insmod gk7205v200_rgn.ko!g" "/usr/bin/load_goke"
reboot
```
On lower-end cameras like gk7205v200/v210 the OSD will work only in 1280x720 mode!

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/msposd-OpenIPC-implementation-of-MSP-Displaypor/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/dg9oaa__msposd.md`.
