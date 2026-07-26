# PixelPilot Drone Scripts

Easy-to-use scripts for setting up and updating your FPV drone camera with
[PixelPilot](https://github.com/OpenIPC/PixelPilot_rk). Just connect your
groundstation to the drone and run the script you need — everything else is
handled automatically.


## Getting the scripts onto your groundstation

The easiest way to copy these scripts is to connect your groundstation to your
PC using **gadget mode**.

### Step 1 — Enable gadget mode

1. Hold the **Left** button on your groundstation while powering it on.
2. Keep holding until the device finishes booting into gadget mode.
3. Connect the groundstation to your PC with a USB cable via the Type-C port.

Once connected, your PC will detect the groundstation in two ways:
- As a **USB drive** (the DVR storage) — shows up in your file manager like a USB stick.
- As a **network device** — the groundstation is reachable at `192.168.5.1`.

### Step 2 — Copy the scripts

**Option A — File manager (easiest)**

Open your file manager. The DVR storage will appear as a removable drive.
Open it and navigate to the `scripts` folder (create it if it doesn't exist).
Copy all the `.sh` files from this folder into it, and also copy the `helpers/` folder — most scripts depend on it.

**Option B — SFTP**

Upload the scripts to /media/dvr/scripts

That's it! The scripts are immediately available in the **Actions menu** in PixelPilot — no reboot needed.

---

## What each script does

### `firmware_download_apfpv.sh` — Download APFPV firmware

Downloads the latest APFPV firmware from the internet and saves it on your
groundstation so you can flash it to the drone later. Run this whenever you
want to update to a newer firmware version.

---

### `firmware_download_wfbng.sh` — Download WFB-NG firmware

Same as above but for WFB-NG firmware. Downloads and saves the latest version
to your groundstation ready for flashing.

---

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

### `gs_drone_proxy.sh` — Expose drone HTTP+SSH via GS ports

Creates TCP proxies on the groundstation so your PC/Laptop/Phone can access drone services
through the groundstation.

Default mapping:
- `http://<groundstation-lan-ip>:1080` -> `http://<drone-ip>:80`
- `ssh root@<groundstation-lan-ip> -p 1022` -> `<drone-ip>:22`

The script auto-detects drone mode:
- WFB-NG drone: `10.5.0.10`
- APFPV drone: `192.168.0.10`

Running it again is safe; if the proxy is already running, it will report the active mapping.

---

### `untested/replace_runcam_bootloader_with_OpenIPC.sh` — Replace Runcam bootloader

Replaces the factory bootloader on a Runcam unit with the OpenIPC bootloader.
You only need to do this once on a brand-new Runcam camera before installing
OpenIPC firmware for the first time. The script downloads the bootloader
automatically — an internet connection is required.

> **Important:** Do not power off the drone while this script is running. Only run this if you know you need it.

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

