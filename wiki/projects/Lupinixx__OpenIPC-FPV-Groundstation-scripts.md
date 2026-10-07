# PixelPilot Drone Scripts

> Картка виставки. Зал: [OpenIPC](../halls/openipc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [Lupinixx/OpenIPC-FPV-Groundstation-scripts](https://github.com/Lupinixx/OpenIPC-FPV-Groundstation-scripts) |
| Локальна тека | `fpv-library/repos/OpenIPC-FPV-Groundstation-scripts` |
| У бібліотеці | keep |
| Категорії каталогу | `openipc` |
| Зірки (каталог) | 2 |
| Оновлено upstream | 2026-06-04 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

Easy-to-use scripts for setting up and updating your FPV drone camera with [PixelPilot](https://github.com/OpenIPC/PixelPilot_rk). Just connect your groundstation to the drone and run the script you need — everything else is handled automatically.

_З README.md, без переказу._

## Для чого

Easy-to-use scripts for setting up and updating your FPV drone camera with [PixelPilot](https://github.com/OpenIPC/PixelPilot_rk). Just connect your groundstation to the drone and run the script you need — everything else is handled automatically.

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник відеотракту — у тексті є «openipc».


## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `drone_firstboot.sh`
- `drone_install_apfpv.sh`
- `drone_install_waybeam_venc.sh`
- `drone_install_wfbng.sh`
- `firmware_download_apfpv.sh`
- `firmware_download_wfbng.sh`
- `gs_drone_proxy.sh`
- `helpers/`
- `README.md`
- `untested/`

Типи файлів за вибіркою (12 файлів, глибина до 3): shell (10), Markdown (1), JSON (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### `drone_install_apfpv.sh` — Flash APFPV firmware to the drone

Sends the previously downloaded APFPV firmware to the drone and installs it.
The drone will reboot automatically when done.

> Run **Download APFPV firmware** first to download the firmware.

---
### `drone_install_wfbng.sh` — Flash WFB-NG firmware to the drone

Sends the previously downloaded WFB-NG firmware to the drone and installs it.
The drone will reboot automatically when done.

> Run **Download WFB-NG firmware** first to download the firmware.

---
### `drone_firstboot.sh` — Complete first-time setup on the drone

Runs the initial setup on the drone after a fresh firmware install. You only
need this the first time after flashing new firmware. Progress is shown live
in the PixelPilot console.

---
### `drone_install_waybeam_venc.sh` — Install Waybeam (venc) on the drone

Replaces the default majestic camera software with
[Waybeam](https://github.com/OpenIPC/waybeam_venc) on a Star6E-based drone.
Waybeam is a modern, actively maintained alternative that provides better
performance and configuration options.

What the script does:
- Downloads the latest Waybeam release and the required Star6E SoC libraries directly from GitHub
- Downloads the Waybeam `S99mountSD` helper script and installs it to `/etc/init.d/S99mountSD`
- Stops majestic, any running waybeam, and msposd on the drone to free up bandwidth
- Temporarily boosts the uplink MCS index and FEC ratio for faster file transfer, then restores them afterwards
- Uploads the waybeam binary, json_cli, regscan, init script, SoC libs, and a fresh default config
- Includes `libmi_ive.so` and `libmi_rgn.so` in the uploaded Star6E library set
- Configures the video output automatically based on the drone's IP address:
  - `10.5.0.10` (WFB-NG) → `unix://rtp_local`
  - `192.168.0.10` (APFPV) → `udp://192.168.0.10:5600`
- Removes majestic and reboots the drone

An internet connection on the groundstation is required to download the release files.

---
### `untested/drone_install_waybeam_wfb_ng.sh` — Install waybeam_wfb_ng (experimental)

Installs Waybeam WFB-NG mode on both drone and groundstation using provided
`link_controller` and `gs_supervisor` artifacts.

What the script does:
- Accepts either local files or URLs for `link_controller` and `gs_supervisor`
- Uploads and launches a drone-side installer that switches the vehicle to `S99wfb`
- Installs `gs_supervisor` on the groundstation with generated config in `/etc/waybeam/gs_supervisor.json`
- Disables legacy GS `wifibroadcast` / `adaptive-link` services and starts `/etc/init.d/S99waybeam-wfb-ng`

Required artifacts are not auto-discovered and must be provided via env vars:
- `WAYBEAM_LINK_CONTROLLER` or `WAYBEAM_LINK_CONTROLLER_URL`
- `WAYBEAM_GS_SUPERVISOR` or `WAYBEAM_GS_SUPERVISOR_URL`

> **Important:** This script is in `untested/` and may disrupt link behavior immediately after switching services.

---

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/OpenIPC-FPV-Groundstation-scripts/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/Lupinixx__OpenIPC-FPV-Groundstation-scripts.md`.
