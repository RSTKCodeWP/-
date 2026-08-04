# AeroStab — заливка SD-карти (Pi Zero 2W)

Повний комплект для розгортання **без git на Pi**: запис OS → копіювання bundle → перший boot → **http://aerostab.local:8080** → **FLIGHT OK** → PosHold.

---

## Що в цій теці

| Файл | Призначення |
|------|-------------|
| `build.sh` | Збирає `dist/aerostab-sd-bundle.tar.gz` + params + checksum |
| `prepare-sd.sh` | Розпаковує bundle на boot-розділ SD (після Pi Imager) |
| `cloud-init-user-data.example` | Авто-встановлення на першому boot (без SSH) |
| `wifi.txt.example` | Wi-Fi як у StabX (рядок 1 = SSID, рядок 2 = пароль) |
| `STABX-CHECKLIST.md` | Звірка з документацією StabX (Google Drive / образ) |
| `dist/` | Артефакти після `build.sh` |

---

## Швидкий старт (15–20 хв + перший boot)

### 1. Збірка на ПК

```bash
cd AeroStab
bash flash-sd/build.sh
```

### 2. Запис Raspberry Pi OS

1. [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. **Device** → Raspberry Pi Zero 2 W  
3. **OS** → Raspberry Pi OS Lite **(64-bit)**  
4. **Storage** → ваша microSD (16 GB+, Class 10 / A1)  
5. **Edit Settings** (шестерня):

| Параметр | Значення |
|----------|----------|
| Hostname | `aerostab` |
| Username | `pi` (або свій) |
| Password | ваш |
| Wi-Fi | **обов'язково** на першому boot (apt + pip) |
| SSH | увімкнено |
| Locale | `uk_UA.UTF-8` |

6. **Write** → дочекайтесь завершення.

### 3. Bundle на boot-розділ

**Linux / macOS** (SD ще в ПК, змонтований як `bootfs` або `boot`):

```bash
# Авто-встановлення при першому boot (рекомендовано):
sudo bash flash-sd/prepare-sd.sh /media/$USER/bootfs --auto-install

# Або вручну через SSH після boot:
sudo bash flash-sd/prepare-sd.sh /media/$USER/bootfs
```

**Windows:** розпакуйте `flash-sd/dist/aerostab-sd-bundle.tar.gz` у корінь boot-розділу (`D:\` тощо). З'явиться папка `aerostab\`.

### 4. Залізо

- CSI: камера **Frank-S01** (OV5647) — синя сторона стрічки до Ethernet  
- UART: Pi **GPIO14 TX** → FC **RX**, **GPIO15 RX** → FC **TX**, **GND**, **5V** (TELEM2)  
- Живлення Pi: **5 V ≥ 2.5 A** (радіатор 20×20 на Zero 2W — бажано)

### 5. Перший boot Pi

1. Вставте SD, підключіть камеру, живлення.  
2. **З auto-install:** 5–15 хв (apt, pip, reboot).  
3. **Без auto-install:** `ssh pi@aerostab.local` →  
   `sudo bash /boot/firmware/aerostab/install-on-first-boot.sh` → reboot.

### 6. ArduPilot (один раз)

Mission Planner / QGC → завантажити параметри з:

```
flash-sd/dist/ardupilot_aerostab.param
```

Ключове: `SERIAL2` @ **230400**, `EK3_SRC1_POSXY/VELXY = 6` (ExternalNav), `GPS1_TYPE = 0`.

### 7. Налаштування перед польотом

1. Відкрийте **http://aerostab.local:8080**  
2. **Маска ROI** — закрийте ніжки / кабель / край пропів (червона зона < 33% ROI)  
3. **Налаштування** → FOV ≈ **72.4°** (Frank-S01), перевірте сітку 1 м на висоті ~1 м  
4. Дочекайтесь **FLIGHT OK** (усі кроки зелені)  
5. На пульті: режим **PosHold** → **ARM** → стіки в центрі → зліт

Детальна картка польоту: `dist/FLIGHT.md` (роздрукуйте).

---

## Wi-Fi без Imager (як StabX)

**Варіант A — файл на Pi:**

```bash
sudo nano /etc/aerostab/wifi.txt
# рядок 1: SSID
# рядок 2: пароль
sudo aerostab-wifi
```

**Варіант B — USB флешка:** файл `wifi.txt` у корені → вставити в OTG → reboot.

**Варіант C — CLI:**

```bash
sudo aerostab-wifi "MySSID" "password"
```

---

## Перевірка після встановлення

```bash
ssh pi@aerostab.local
sudo systemctl status aerostab
python3 /opt/aerostab/scripts/selfcheck.py --simulate   # без FC
curl -s http://127.0.0.1:8080/api/status | head
```

На Pi з FC: у веб-UI **MAVLink OK**, heartbeat < 3 s.

---

## Типові проблеми

| Симптом | Що робити |
|---------|-----------|
| Немає `aerostab.local` | IP з роутера; перевірте Wi-Fi |
| Перший boot завис | Потрібен інтернет; перевірте Wi-Fi в Imager |
| Немає камери | `aerostab-firmware`; `/etc/aerostab/camera.txt` → `ov5647` |
| MAVLink OFF | TX/RX перехрест; `getty@ttyAMA0` вимкнено інсталятором |
| PosHold не арм | Немає FLIGHT OK — маска, FOV, якість, heartbeat |
| Гойдалка | FOV; `PSC_POSXY_P` 0.5–0.8 (див. StabX troubleshooting) |

Повна звірка з StabX: **`STABX-CHECKLIST.md`**.

---

## Структура після заливки (на Pi)

```
/opt/aerostab/              # додаток
/etc/aerostab/config.yaml   # конфіг
/etc/aerostab/mask.json     # маска ROI
/var/log/aerostab/          # логи (+ rtl_path.json якщо RTL увімкнено)
```

---

## Оновлення

```bash
cd /opt/aerostab && sudo git pull   # якщо клонували з git
# або повторити bundle + install-on-first-boot (видалити /var/lib/aerostab/firstboot.done лише для повної переінсталяції)
```

---

*AeroStab — open-source аналог StabX без ліцензійного сервера :5050. Див. `docs/STABX_REVERSE.md`.*
