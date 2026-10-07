# steam-groundstations

> Картка виставки. Зал: [OpenIPC](../halls/openipc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [sickgreg/steam-groundstations](https://github.com/sickgreg/steam-groundstations) |
| Локальна тека | `fpv-library/repos/steam-groundstations-OpenIPC-Steam-Deck-Groundstation` |
| У бібліотеці | watch |
| Категорії каталогу | `openipc` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-05-01 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

OpenIPC Steam Deck Groundstation

_З README.md, без переказу._

## Для чого

OpenIPC Steam Deck Groundstation

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник відеотракту — у тексті є «openipc».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: OpenIPC Steam Deck Groundstation

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `20240324_140750.mp4`
- `20240328_225825.jpg`
- `adaptive-link/`
- `fpv.sh`
- `gs.key`
- `LICENSE`
- `mangohud/`
- `master.cfg`
- `mavlink-rc.md`
- `mavlink_osd/`
- `README.md`
- `ssc30kq/`
- `vlcsnap-2024-03-24-14h17m30s555.png`
- `wfb-cli.sh`
- `wfb-ng-24.6.19.33116.linux-unknown.tar.gz`

Типи файлів за вибіркою (39 файлів, глибина до 3): (без суфікса) (11), shell (6), Markdown (4), Python (4), .cfg (1), .mp4 (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installing OpenIPC software on camera module

- Setup viable majestic configuration
- Setup viable wfb_ng configuration
### Unlocking Steam Deck & installing dependencies

Set your password using 'passwd'

Unlock 70hz: https://github.com/ryanrudolfoba/SteamDeck-RefreshRateUnlocker

sudo steamos-readonly disable

sudo touch /etc/pacman.d/gnupg/gpg.conf

sudo bash -lic 'echo "keyserver hkps://keyserver.ubuntu.com" >> /etc/pacman.d/gnupg/gpg.conf'

sudo pacman-key --init

sudo pacman-key --populate

sudo pacman-key --populate archlinux

sudo pacman-key --refresh-keys

sudo pacman --sync --noconfirm base-devel glibc linux-api-headers libpcap libsodium python-setuptools python-pip python-pyroute2 python-future python-twisted python-pyserial iw  python-virtualenv net-tools python-msgpack bc linux-neptune-65 linux-neptune-65-headers dkms
#linux-neptune-61 linux-neptune-61-headers replaced 2025-01-22

#build rtl8812au
cd

git clone https://github.com/svpcom/rtl8812au.git

cd rtl8812au

make

sudo ./dkms-install.sh


cd

git clone https://github.com/svpcom/wfb-ng.git

cd wfb-ng

make bdist

cd dist

tar -xvf *

sudo cp -rf etc /

sudo cp -rf usr /

sudo cp -rf lib/systemd/system/* /lib/systemd/system/

sudo systemctl daemon-reload

get default gs.key

wget https://github.com/OpenIPC/steam-groundstations/raw/master/gs.key

sudo mv gs.key /etc/

wget https://github.com/OpenIPC/steam-groundstations/raw/master/master.cfg

sudo mv -rf master.cfg /usr/lib/python3.11/site-packages/wfb_ng/conf/

sudo systemctl start wifibroadcast@gs

sudo systemctl status wifibroadcast@gs
### Streamline usage on Steam Deck

How to add a non-steam game to steam deck: https://www.dexerto.com/tech/how-to-add-non-steam-games-to-steam-deck-2082992/

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/steam-groundstations-OpenIPC-Steam-Deck-Groundstation/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/sickgreg__steam-groundstations.md`.
