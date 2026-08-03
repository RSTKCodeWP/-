# Звірка AeroStab ↔ StabX (документація + образ SD)

Джерела StabX:
- Google Doc «Оптична навігація» (Academia Tech) — узагальнено в `docs/STABX_REVERSE.md`
- Образ `ZERO-16G-2025-11-01-JR.rar` — `docs/STABX_IMAGE_ANALYSIS.md`
- BOM: https://docs.google.com/spreadsheets/d/1EK2ivnruir1vM7jP4dPWfKLPtNHdDFTZSqVXn1FO-Cc
- ArduPlane STABX FW: https://drive.google.com/drive/folders/1YqU0y8PFPoRYXT9zpu3KWSGH_ifB57I1

Легенда: ✅ реалізовано · ⚠️ частково · ❌ немає (свідомо / не в scope) · 🔒 закрито в StabX

---

## Апаратура

| Вимога StabX | AeroStab | Статус |
|--------------|----------|--------|
| Pi Zero 2W + радіатор | Підтримується | ✅ |
| CSI OV5647-120 (Frank-S01) | `deploy/settings/firmware/zero/ov5647/` | ✅ |
| CSI IMX219 | Профіль є, за замовч. **ov5647** | ⚠️ |
| UART GPIO14/15 @ 230400 | `install_pi.sh`, `ardupilot_aerostab.param` | ✅ |
| disable getty@ttyAMA0 | `install_pi.sh` | ✅ |
| Живлення 5V з FC Cam pad | Документовано `docs/WIRE.md` | ✅ |
| Нічні USB / thermal / dual cam | — | ❌ |

---

## MAVLink / ArduPilot (коптер)

| Параметр StabX | AeroStab `ardupilot_aerostab.param` | Статус |
|----------------|-------------------------------------|--------|
| `VISO_TYPE=1` | так | ✅ |
| `EK3_SRC1_POSXY/VELXY=6` | так | ✅ |
| `EK3_SRC1_POSZ=1` (baro) | так | ✅ |
| `EK3_SRC1_YAW=1` (compass) | так | ✅ |
| `GPS1_TYPE=0` | так | ✅ |
| `SERIALx_BAUD=230` | SERIAL2 @ 230400 | ✅ |
| `FRAME_TYPE=12` | так | ✅ |
| `PHLD_BRAKE_*`, `FS_EKF_THRESH` | так | ✅ |
| `ARMING_CHECK` без GPS | 8775 (строгіший, +VISION) | ✅ |
| `VISION_POSITION_ESTIMATE` out | `mavlink_bridge.send_odometry` | ✅ |
| `GPS_INPUT` (літаки) | — | ❌ |
| Arm/calibrate з веб-UI | Прибрано — **arm лише з RC** | ⚠️ навмисно |

---

## Алгоритми навігації

| Фіча StabX | AeroStab | Статус |
|------------|----------|--------|
| Optical flow LK | `estimator.py` | ✅ |
| Маска сітка 16×12, <33% ROI | `mask.py`, `max_roi_fill: 0.33` | ✅ |
| FOV сітка 1 m | `show_grid`, веб FOV | ✅ |
| Warmup перед NAV valid | `quality.nav_valid_warmup_s` | ✅ |
| HOLD LAST при втраті текстури | `quality_gate.py`, `hold_last_on_drop` | ✅ |
| Висота baro / rangefinder / auto | `altitude.source: auto` | ✅ |
| Baro level estimator (рельєф HILLS) | лише baro_relative | ⚠️ |
| Thermal DIFF | — | ❌ |
| GPS fusion FUSE-V2 | `gps_fusion.py` (off за замовч.) | ⚠️ |
| RTL path RTL-V2 | `rtl_path.py` (off за замовч.) | ⚠️ |

---

## Веб-інтерфейс (:8080)

| StabX creepy | AeroStab | Статус |
|--------------|----------|--------|
| Прев'ю камери + overlay | MJPEG `/video.mjpg` | ✅ |
| Маска ROI | веб canvas 16×12 | ✅ |
| FOV / rotation | налаштування camera | ✅ |
| FLIGHT OK / діагностика | health + fly steps | ✅ |
| `/arm`, `/calibrate` | **немає** — безпека | ⚠️ |
| Записи `.stabx` | CSV `log_csv` (off) | ⚠️ |
| MAVLink Inspector | health checks | ⚠️ |
| Map / Live | — | ❌ |
| frames_timing USB | — | ❌ |

---

## Provisioning / WiFi

| StabX | AeroStab | Статус |
|-------|----------|--------|
| lserv :5050 ліцензія/OTA | немає | 🔒 не потрібно |
| Hotspot `uapilot`/`uapilotstab` | NM через `aerostab-wifi` | ⚠️ |
| `wifi.txt` 2 рядки | `/etc/aerostab/wifi.txt` + USB | ✅ |
| USB autorun wifi | `aerostab-usb-wifi.service` | ✅ |
| Hostname `pizero2` | `aerostab` (+ mDNS) | ⚠️ інше ім'я |

---

## Boot / SD

| StabX образ | AeroStab flash-sd | Статус |
|-------------|-------------------|--------|
| Один .img Debian 12 | Pi OS Lite + bundle | ⚠️ інший підхід |
| autorun.sh @reboot | `aerostab-firstboot` + cloud-init | ✅ |
| `firmware.sh` camera.txt | `aerostab-firmware` | ✅ |
| Розділ `/data` records | `/var/log/aerostab` (+ opt `/data`) | ⚠️ |
| Lock SD / шифрування | — | ❌ |

---

## Режими польоту (з документації StabX)

| Режим | Рекомендація StabX | AeroStab |
|-------|---------------------|----------|
| **PosHold** | основний | ✅ FLIGHT OK → arm з RC |
| **AltHold** | fallback без текстури | ✅ документовано FLIGHT.md |
| **Stabilize** | аварійний | ✅ документовано |
| Arm без валідної навігації | блокується StabX | ✅ FLIGHT OK gate |

**Ручне зсування борту:** лише **до ARM** (disarm). У PosHold armed FC утримує точку — не штовхати.

---

## Troubleshooting (з Google Doc StabX)

| Симптом | StabX фікс | AeroStab |
|---------|------------|----------|
| Гойдалка | FOV, PID | FOV у UI; `PSC_POSXY_P` у param |
| Телепорт | зменшити P,I | `EK3_*_NSE` у param |
| Deadzone стіків | RC1/2_DZ 30–50 | RC1/2_DZ=40 у param |
| Yaw крутиться | маска | маска ROI |
| Зліт криво | rotation | `camera.rotation_deg` |
| PosHold не арм | :8080 діагностика | FLIGHT OK + health |
| Stab пізно завантажився | AltHold→PosHold toggle | `aerostab.service` After=network |

---

## Висновок для заливки SD

Для **коптера + Frank-S01 + Matek/ArduPilot PosHold** AeroStab покриває **критичний шлях StabX**:

1. UART MAVLink vision @ 230400  
2. Маска + FOV + warmup + HOLD LAST  
3. FLIGHT OK перед arm  
4. Wi-Fi provisioning (wifi.txt)  
5. Авто-install з SD bundle  

**Не покрито** (не блокує hover): ліцензія :5050, thermal DIFF, dual cam, plane GPS_INPUT, .stabx logs, flight map.

Перед польотом: пройдіть чеклист у `flash-sd/README.md` §7 і `FLIGHT.md`.
