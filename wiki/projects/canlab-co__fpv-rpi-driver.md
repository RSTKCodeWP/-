# fpv-rpi-driver

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [canlab-co/fpv-rpi-driver](https://github.com/canlab-co/fpv-rpi-driver) |
| Локальна тека | `fpv-library/repos/fpv-rpi-driver` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

У джерелах цього репозиторію цього немає.

## Для чого

У джерелах цього репозиторію цього немає.

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `canlab-downstream-overlay.dts`
- `canlab.c`
- `dkms.conf`
- `dkms.postinst`
- `LICENSE`
- `Makefile`
- `README.md`
- `setup-dualvc.sh`
- `setup.sh`

Типи файлів за вибіркою (10 файлів, глибина до 3): shell (2), (без суфікса) (2), .conf (1), .postinst (1), C (1), Markdown (1).


## Що треба

- Маніфести збірки: Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Install

```
sudo apt install -y git
sudo apt install -y --no-install-recommends dkms
git clone <this-repo>
cd canlab-rpi-driver/
sudo ./setup.sh
```
### Runtime pipeline setup

After boot, configure the media pipeline (links + formats) before
streaming:

```
./setup-dualvc.sh vga     # or: qvga, or run without args for a prompt
```

Verify the driver probed:

```
dmesg | grep canlab
# canlab 11-001a: CANLAB(downstream) 2-VC: VC0 1920x1080(pad0/ch0) + VC1 ...
```
### Uninstall

```
sudo dkms remove canlab-rpi-dkms/1.0.0 --all
sudo rm /boot/firmware/overlays/canlab-downstream.dtbo
# remove the dtoverlay line from config.txt
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/fpv-rpi-driver/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/canlab-co__fpv-rpi-driver.md`.
