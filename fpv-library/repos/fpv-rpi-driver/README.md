# fpv-rpi-driver

# CANLAB dual-VC camera driver for Raspberry Pi 5

Raspberry Pi 5 (RP1 CFE) V4L2 driver for the CANLAB dual virtual-channel
MIPI CSI-2 camera (Efinix Ti60 FPGA source, UYVY, 4-lane, 500 MHz
continuous clock).

- VC0: 1920x1080 UYVY -> /dev/video0
- VC1: 640x480 (default) or 320x240 (`qvga`) UYVY -> /dev/video2

Distributed as source + DKMS: the module is rebuilt automatically on the
target for the running kernel, including after kernel upgrades
(`AUTOINSTALL="yes"`), so no per-kernel binary releases are needed.

## Install

```
sudo apt install -y git
sudo apt install -y --no-install-recommends dkms
git clone <this-repo>
cd canlab-rpi-driver/
sudo ./setup.sh
```

## Boot configuration

Edit `/boot/firmware/config.txt`:

1. Set `camera_auto_detect` to `0`:

```
camera_auto_detect=0
```

2. Add under the `[all]` section:

```
[all]
dtoverlay=canlab-downstream
```

Reboot for changes to take effect.

## dtoverlay options

| default | description                     |
| ------- | ------------------------------- |
|   CAM1  | Use CAM1 port    		    |
|   VGA   | VC1 outputs 640x480 (VGA fw)    |


| option | description                      |
| ------ | -------------------------------- |
| `cam0` | Use CAM0 port instead of CAM1    |
| `qvga` | VC1 outputs 320x240 (QVGA fw)    |

Options can be combined: `dtoverlay=canlab-downstream,cam0,qvga`

The overlay/driver setting must match the firmware actually flashed on
the camera (VGA vs QVGA firmware variants).

## Runtime pipeline setup

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

## Streaming

Both channels must be started together:

```
gst-launch-1.0 \
  v4l2src device=/dev/video0 ! video/x-raw,format=UYVY,width=1920,height=1080 ! xvimagesink \
  v4l2src device=/dev/video2 ! video/x-raw,format=UYVY,width=640,height=480  ! xvimagesink
```

## Uninstall

```
sudo dkms remove canlab-rpi-dkms/1.0.0 --all
sudo rm /boot/firmware/overlays/canlab-downstream.dtbo
# remove the dtoverlay line from config.txt
```
