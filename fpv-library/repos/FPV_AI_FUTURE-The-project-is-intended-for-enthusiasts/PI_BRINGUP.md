# Block-3 — Raspberry Pi 5 bench bring-up

Goal: get the Pi running our code, then run the 3 benches with real hardware and read the logs.
Model: you run each step on the Pi; paste the output/errors back and we debug together.

> **Camera reality check:** the FT640 V2 is an **analog CVBS** thermal camera. The Pi cannot see it
> directly — you need a **CVBS → USB capture dongle** (~$10 "EasyCap"-class, UTV007/STK1160 chipset
> work well on Linux). The Pi sees the dongle as `/dev/video0`. Confirm you have one before the camera step.

---

## 1. Flash Raspberry Pi OS 64-bit (this is "прошить разбери")

A Pi is not flashed like an MCU — you write an OS image to the SD card (or NVMe).

1. On your Mac/PC install **Raspberry Pi Imager** (https://www.raspberrypi.com/software/).
2. Choose device **Raspberry Pi 5**, OS **Raspberry Pi OS (64-bit)** (Bookworm), and your SD card.
3. Click the gear / **Edit Settings** before writing:
   - hostname: `interceptor`
   - enable **SSH** (password auth is fine for the bench)
   - set username `pi` + a password
   - set your Wi-Fi SSID/password + locale
4. **Write**, put the card in the Pi, power on. From your Mac: `ssh pi@interceptor.local` (or the Pi's IP).

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-venv python3-pip git v4l-utils
sudo reboot
```

## 2. Get the code onto the Pi

From your Mac (the project is at `/Volumes/Samsa/ai_v2.0/03-fpv`):

```bash
# from the Mac:
scp -r /Volumes/Samsa/ai_v2.0/03-fpv pi@interceptor.local:~/
```

(or `rsync -av --exclude .venv /Volumes/Samsa/ai_v2.0/03-fpv pi@interceptor.local:~/`)

## 3. Python env + deps (on the Pi)

Pi OS Bookworm blocks system pip (PEP 668), so use a venv:

```bash
cd ~/03-fpv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install numpy scipy opencv-python pyserial pytest      # aarch64 wheels exist; takes a few min
```

**Sanity (no hardware needed) — confirm the code runs on the Pi:**

```bash
cd ~/03-fpv
PYTHONPATH=fpv python -m pytest fpv/fpv_ai/sensor fpv/fpv_ai/betaflight_link/tests -q
```
→ should be all-green. **Send me this output.** If it's green, the software is healthy on the Pi.

## 4. Enable the UART (for talking to the FC over MSP)

```bash
sudo raspi-config
#  3 Interface Options -> I6 Serial Port
#   "login shell over serial?"  -> NO
#   "serial port hardware enabled?" -> YES
sudo reboot
```
The Pi5 primary UART is **`/dev/ttyAMA0`** (GPIO14 = TX pin 8, GPIO15 = RX pin 10). See `firmware/WIRING.md`.

## 5. Run the benches (the actual "let's see how it works")

Each is READ-ONLY / safe (no arming, no RC to the FC). **Paste me the stdout of each.**

```bash
cd ~/03-fpv
source .venv/bin/activate

# (a) CAMERA — find the grabber, then detect a hot target (point FT640 at a soldering iron / kettle)
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext        # send me this so I tune the capture
PYTHONPATH=fpv python -m fpv_ai.sensor.thermal_bench --device /dev/video0 --invert
#   look for: state=LOCKED, a centroid, fps. If black-hot, drop --invert; if letterboxed, add --roi X Y W H

# (b) FC TELEMETRY — wire Pi UART <-> FC MSP UART first (WIRING.md), props OFF
PYTHONPATH=fpv python -m fpv_ai.betaflight_link.msp_bench --port /dev/ttyAMA0 --baud 115200 --field attitude
#   tilt the drone by hand -> roll/pitch should move. "NO MSP RESPONSE" => check wiring + Betaflight Ports MSP

# (c) BOTH together — the whole pipeline on real hardware, shows "what the AI would command", never sends RC
PYTHONPATH=fpv python -m fpv_ai.onboard_openloop --device /dev/video0 --port /dev/ttyAMA0 --invert
```

## 6. What to send me when something doesn't work

- the full bench stdout (and any Python traceback)
- `v4l2-ctl --list-devices` and `v4l2-ctl -d /dev/video0 --list-formats-ext`
- `dmesg | tail -30` right after plugging the grabber (so I see the chipset)
- for MSP: the Betaflight Ports-tab config (which UART has MSP, what baud)

We iterate from there. The FC fork + HW-kill MCU flashing is a SEPARATE, later step — bench the sensors first.
