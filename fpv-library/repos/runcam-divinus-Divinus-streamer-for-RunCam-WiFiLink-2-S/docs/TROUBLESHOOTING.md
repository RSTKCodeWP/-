# Troubleshooting

## Camera does not boot after install

Connect via UART (115200 baud) and run:
```bash
sh /mnt/sdcard/restore_majestic.sh
reboot
```

## No video stream

```bash
killall -9 majestic 2>/dev/null
/etc/init.d/S95divinus restart
logread | grep -i divinus
```

Check sensor: `fw_printenv sensor`

## Low video quality

Verify divinus.yaml settings:
- codec: H.265
- mode: AVBR
- resolution: 1024x576
- bitrate: 5600
- maxBitrate: 6000
- profile: HP
- gop: 30
- minQp: 20, maxQp: 42

## Majestic conflict

```bash
mv /etc/init.d/S95majestic /etc/init.d/S95majestic.disabled
killall -9 majestic
/etc/init.d/S95divinus restart
```

## High latency

```bash
cat /proc/mi_modules/mi_venc/mi_venc0 | grep fps
```

Ensure no B-frames. Lower resolution if CPU overloaded.

## Thermal throttling

```bash
cat /sys/class/thermal/thermal_zone0/temp
# Should be below 85000 (85C)
```

## Stream freezes periodically

- Check temperature (thermal throttling)
- Ensure SD card recording is disabled during streaming
- Verify GOP is 30 (not higher)

## Debug commands

```bash
uname -a
fw_printenv sensor
cat /proc/mi_modules/mi_venc/mi_venc0
cat /proc/mi_modules/mi_sensor/mi_sensor0
cat /proc/mi_modules/mi_vpe/mi_vpe0
cat /sys/class/thermal/thermal_zone0/temp
ps | grep -E "divinus|majestic|wfb"
ifconfig
logread | tail -50
dmesg | tail -50
cat /mnt/sdcard/install.log
```

## Common install.log errors

- `Read-only file system` → Run: `mount -o remount,rw /`
- `Permission denied` → Run: `chmod +x /usr/bin/divinus`
- `install_divinus.sh not found` → Check: `mount | grep sdcard`

## Getting help

Open an issue at https://github.com/RastaDevX/runcam-divinus/issues

Include: install.log, `uname -a`, sensor type, symptoms.