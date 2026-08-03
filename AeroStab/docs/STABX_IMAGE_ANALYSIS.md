# StabX SD Image — бінарний реверс

Образ: `ZERO-16G-2025-11-01-JR.rar` → `ZERO-16G-2025-11-01-JR.img` (16 GB SD, дата збірки **2025-11-01**)

Архів у репозиторії: `AeroStab/image/ZERO-16G-2025-11-01-JR.rar` (Git LFS, ~1.7 GB)

---

## 1. Розмітка диска

| Розділ | Сектор start | Розмір | Тип | Призначення |
|--------|--------------|--------|-----|-------------|
| p1 | 8192 | 512 MB | FAT32 (bootfs) | `/boot/firmware` — kernel, DTB, `config.txt` |
| p2 | 1056768 | 6.7 GB | ext4 | Корінь Debian, `/home/pilot/start` |
| p3 | 15155200 | 100 MB | ext4 | `/data` — записи польотів (`/data/records`) |

`cmdline.txt`: `root=PARTUUID=abdb6f3a-02 rootfstype=ext4 fsck.repair=yes rootwait quiet splash plymouth.ignore-serial-consoles cfg80211.ieee80211_regdom=UA`

---

## 2. Операційна система

| Параметр | Значення |
|----------|----------|
| Дистрибутив | **Debian 12 (bookworm)** — не Raspberry Pi OS |
| Hostname | `pizero2` |
| Архітектура | aarch64 (Pi Zero 2 W) |
| Desktop | LXDE-pi + **labwc** (Wayland), autologin user **pilot** |
| Додаткові користувачі | `pi` (утиліти expand/partition), `pub` (логи/records bind-mount) |

---

## 3. Ланцюжок запуску

```
@reboot (root crontab)
  └─ /usr/bin/autorun.sh
       ├─ /usr/bin/firmware.sh      # camera.txt → config.txt, reboot if changed
       ├─ /usr/bin/expand.sh       # розширення root (лог → /home/pi/boot.txt)
       ├─ fsck + mount /dev/mmcblk0p3 → /data
       ├─ bind-mount /data/records → /home/pub/records
       └─ exec /home/pilot/start/lserv   # license server :5050
            └─ (async) ./creepy         # flight app :8080, MAVLink UART
```

Паралельно (systemd, `multi-user.target`):

| Сервіс | Скрипт | Роль |
|--------|--------|------|
| `wifi-connect.service` | `/usr/bin/wifi.sh` | WiFi з `data/wifi.txt` (2 рядки: SSID, password) |
| `usb-autostart.service` | `/usr/bin/run_usb.sh` | USB: копіює `wifi.txt` з флешки, підключає |
| `devmon@pilot.service` | `devmon --no-gui` | Автомонтування USB для pilot |
| `shred_logs_and_bt.service` | `/usr/bin/shred.sh` | На старті: shred `/var/log`, bluetooth, bash history |

`creepy` при старті: `systemctl stop/disable getty@ttyAMA0` — звільняє UART0 для MAVLink.

---

## 4. Головні бінарники

| Файл | Розмір | BuildID (sha1) | Роль |
|------|--------|----------------|------|
| `/home/pilot/start/lserv` | 662 KB | c13406e1… | HTTP :**5050** — ліцензія, OTA, WiFi hotspot, Download |
| `/home/pilot/start/creepy` | 464 KB | d658035f… | HTTP :**8080** — оптична навігація, UI, MAVLink |
| `ua-pilot` | (encrypted) | — | Завантажується через Download; `ua-pilot.enc` в `binary/<hash>/` |

Обидва — **ARM64 ELF**, stripped, C++ з **cpp-httplib/0.9**.

### 4.1 lserv (:5050) — HTTP endpoints (з strings)

| Endpoint | Призначення |
|----------|-------------|
| `/ping` | Health check |
| `/buildinfo` | Інфо про білд |
| `/hkey` | Hardware key |
| `/paired`, `/unpair` | Bluetooth pairing |
| `/lock`, `/unlock`, `/getlock` | Блокування SD |
| `/update/*`, `/dlink/*` | OTA оновлення (`lserv.zip`) |
| `/download`, `/crypto/*` | Завантаження зашифрованого `ua-pilot` |
| `/accesspoint`, `/accesspointext` | WiFi hotspot |
| `/wifilist`, `/wifidialog`, `/connectwifi/*`, `/wificonnect` | WiFi provisioning |
| `/settings/*`, `/editable`, `/changed` | Налаштування з сервера |
| `/device/serial`, `/device.txt` | Ідентифікація пристрою |
| `/videoout/*` | Відеовихід |
| `/restoreinet` | Запуск `data/scripts/inet.sh` |

Повідомлення: `Connect, use pizero2:5050 or 10.42.0.1:5050 to access the device.`

### 4.2 creepy (:8080) — HTTP endpoints (з ui.html + strings)

| Endpoint | Призначення |
|----------|-------------|
| `/arm` | Arm FC |
| `/stop` | Зупинити автопілот |
| `/calibrate` | Level calibration ArduPilot |
| `/gngp` | GUIDED_NO_GPS mode |
| `/grid` | FOV calibration grid |
| `/camstate` | JSON: cameras, rotation, fov, locked, records_state |
| `/camrotate` | Поточний кут камери |
| `/setcamid/<id>` | Вибір камери |
| `/setrotation/<deg>` | Поворот |
| `/setuserfov/<deg>`, `/testfov/<deg>` | FOV |
| `/setuserposerror/<pct>` | Точність позиції |
| `/setnav/<mode>` | 2=EXTERNAL_NAV, 4=GPS_INPUT |
| `/setrecords/<state>` | Режим запису |
| `/setrecmethod/<m>` | Метод запису |
| `/log`, `/cpu` | Діагностика |
| `/exit` | Shutdown |
| `/dronecam`, `/images/*` | Зображення дрона / камери |
| `/full_camera/` | Повноекранна камера |

UI: `data/res/ui.html` (українська локалізація `ua.txt`), Tailwind, army-green тема.

---

## 5. OTA оновлення (`update.sh`)

```bash
killall lserv creepy ua-pilot
mv images/unzip/ua-pilot.enc → binary/<md5>/ua-pilot.enc
rm data/* (крім records)
mv data/lserv.zip → unzip → chmod +x lserv creepy
reboot
```

---

## 6. WiFi

| Джерело | SSID | Password |
|---------|------|----------|
| `uapilot.nmconnection` (fallback) | `uapilot` | `uapilotstab` |
| `data/wifi.txt` (пріоритет) | 2 рядки з USB/ручного вводу | |
| Hotspot (lserv) | `uapilot` | `uapilotstab` → `10.42.0.1:5050` |

`wifi.sh` → `nmcli device wifi connect`. `inet.sh` — вибір робочого інтерфейсу + DNS fix.

---

## 7. Камера та boot

`firmware.sh` / `cam-conf.sh`: читають `data/camera.txt` або `data/cam-family.txt`, копіюють відповідний `config.txt` з `data/settings/firmware/zero/<camera>/`.

Поточний `config.txt` (boot p1):

```
dtoverlay=imx219
enable_uart=1
dtoverlay=miniuart-bt
force_turbo=1
dtoverlay=vc4-kms-v3d,composite
camera_auto_detect=0
arm_64bit=1
```

UART: GPIO14/15 (miniuart-bt), MAVLink на ttyAMA0 @ **230400** (з документації + поведінка FC).

### RTSP / відео

`data/scripts/rtsp.sh`:
- `mediamtx` (:8554) + `ffmpeg` з `/dev/fb0` → RTSP `rtsp://127.0.0.1:8554/fb0`
- Конфіг: `data/tools/mediamtx.yml`

---

## 8. Записи та дані

| Шлях | Призначення |
|------|-------------|
| `/data/records` | Відео/логи польотів (ext4 p3) |
| `/home/pub/records` | bind-mount → `/data/records` |
| `/data/records/logs-server.txt` | Лог autorun/lserv |
| `/home/pub/records/wifi_log.txt` | Лог wifi-connect |
| `/home/pub/records/usb_script.log` | Лог USB autorun |

Режими запису (з `ua.txt`): Images+logs, Logs only, Nothing, + greyscale variants.

---

## 9. Безпека / антифорензика

- `shred_logs_and_bt.service` — знищення логів і bluetooth config на кожному boot
- `wipe.sh`, `wipe_shutdown.sh` — повне очищення
- `clean.sh` — скидання binary/downloads/settings
- `ua-pilot.enc` — зашифрований основний модуль навігації
- Bluetooth LE scan для ліцензійного ключа (`lescan`, `org/bluez/hci0`)

---

## 10. Порівняння з AeroStab

| Компонент | StabX | AeroStab |
|-----------|-------|----------|
| Мова | C++ (lserv + creepy) | Python |
| Ліцензія | lserv + uapilot.online + BT | Немає (open source) |
| Web UI | creepy :8080 | Flask :8080 + StabX aliases (`/arm`, `/camstate`) |
| Provisioning | lserv :5050 | `aerostab-wifi`, `aerostab-firmware` |
| Arm / calibrate | `/arm`, `/calibrate` | ✅ `/api/arm`, `/api/calibrate` |
| WiFi | `wifi.txt` + USB | ✅ `aerostab-wifi` + systemd |
| Camera boot | `firmware.sh` | ✅ profiles ov5647 / imx219 |
| UART | stop getty@ttyAMA0 | ✅ install_pi.sh |
| Records | ext4 p3 | ⚠️ bind-mount if `/data` exists |
| OTA | lserv.zip encrypted | git / apt |

---

## 11. Як повторити аналіз

```bash
# Розпакувати (локально, не комітити .img)
unrar x AeroStab/image/ZERO-16G-2025-11-01-JR.rar AeroStab/image/extracted/

# Автоматичний звіт
bash AeroStab/scripts/analyze_stabx_image.sh AeroStab/image/ZERO-16G-2025-11-01-JR.rar

# Ручний mount root (offset = 1056768 * 512)
sudo mount -o loop,offset=540016896 image/extracted/ZERO-16G-2025-11-01-JR.img /tmp/stabx-root
strings /tmp/stabx-root/home/pilot/start/lserv | less
```

Див. також: [STABX_REVERSE.md](STABX_REVERSE.md) (архітектура з документації + firmware).
