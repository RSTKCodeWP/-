# Installation Guide — RunCam WiFiLink 2

## Prerequisites

- RunCam WiFiLink 2 with OpenIPC firmware
- MicroSD card (FAT32 formatted, any size)
- Linux PC or macOS with Docker for building
- (Optional) USB-UART adapter for emergency recovery

## Step 1: Build the Divinus Binary

### Option A: Using Docker (recommended)

```bash
git clone https://github.com/RastaDevX/runcam-divinus.git
cd runcam-divinus
chmod +x build.sh
./build.sh all
```

This will:
1. Clone the Divinus source from OpenIPC
2. Apply encoder optimization patches
3. Cross-compile for SSC338Q (star6e target)
4. Place the binary in `./sdcard/divinus`

### Option B: Manual build

```bash
git clone https://github.com/OpenIPC/divinus.git
cd divinus
./build.sh star6e
cp divinus ../runcam-divinus/sdcard/
```

## Step 2: Prepare SD Card

1. Format your MicroSD card as **FAT32**
2. Copy **all files** from the `sdcard/` directory to the SD card root:

```
SD Card Root:
├── autorun.sh
├── install_divinus.sh
├── restore_majestic.sh
├── divinus              ← the compiled binary
├── divinus.yaml
├── S95divinus
└── user.ini
```

**IMPORTANT:** The `divinus` binary must be present. The build step produces it.

## Step 3: Identify Your Sensor

Before flashing, SSH into the camera to check your sensor:

```bash
ssh root@192.168.1.10
# Default password: 12345

fw_printenv sensor
ls /etc/sensors/
```

Common sensors on RunCam WiFiLink 2:
- `imx335` — most common
- `imx415` — higher-end variant

Edit `divinus.yaml` on the SD card if needed:
```yaml
system:
  sensor_config: /etc/sensors/YOUR_SENSOR.bin
```

## Step 4: Flash via SD Card

1. **Power off** the RunCam WiFiLink 2
2. Insert the prepared SD card
3. Power on the camera
4. Wait **30-45 seconds** — the installer runs automatically
5. The camera will reboot with Divinus active

## Step 5: Verify Installation

```bash
ssh root@192.168.1.10

# Check that Divinus is running
ps | grep divinus

# Check logs
logread | grep -i divinus

# Check video stream
# On ground station, you should see video via wfb-ng
```

## Step 6: Verify Video Quality

On your ground station (PixelPilot, QGroundControl, etc.):
- Resolution should be 1024x576
- FPS should be 30
- Bitrate should stay under 700 KB/s (5600 kbps)
- Quality should be noticeably sharper than stock at same bitrate

## Emergency Restore

### Method A: SSH (if network works)

```bash
ssh root@192.168.1.10
sh /mnt/sdcard/restore_majestic.sh
```

### Method B: SD Card restore

If camera boots but Divinus crashes, the `restore_majestic.sh` on SD card
can be triggered manually via SSH or UART.

### Method C: UART Console

Connect USB-UART adapter to RunCam debug pads:
- TX, RX, GND
- Baud rate: 115200

```bash
# macOS
screen /dev/tty.usbserial-* 115200

# Linux
picocom -b 115200 /dev/ttyUSB0
```

Then run:
```bash
sh /mnt/sdcard/restore_majestic.sh
```

### Method D: Full firmware reflash

As last resort, reflash stock OpenIPC firmware via UART + TFTP.
See: https://github.com/OpenIPC/wiki

## Changing Configuration After Install

To modify encoder settings after installation:

```bash
ssh root@192.168.1.10
vi /etc/divinus.yaml

# Restart Divinus to apply changes
/etc/init.d/S95divinus restart
```

## Configuration Options

### Resolution
| Setting | Quality at 5600kbps | Use Case |
|---|---|---|
| 1024x576 | ★★★★★ Excellent | Best quality per pixel |
| 1152x648 | ★★★★☆ Good | Balanced |
| 1280x720 | ★★★☆☆ Acceptable | Maximum resolution |

### GOP (Group of Pictures)
| GOP | Latency Impact | Compression | Recovery |
|---|---|---|---|
| 1 | None (all I-frames) | Poor (high bitrate waste) | Instant |
| 15 | Medium | Good | 0.5s |
| 30 | Low | Best | 1.0s |
| 60 | Lowest | Best | 2.0s |

For FPV with wfb-ng, GOP=30 is recommended. The ground station can request IDR frames for instant recovery.

### Rate Control Mode
| Mode | Description | Best For |
|---|---|---|
| AVBR | Adaptive VBR, smart bit allocation | FPV (recommended) |
| CBR | Constant bitrate, predictable | Stable WiFi link |
| VBR | Variable, may exceed ceiling | Recording |