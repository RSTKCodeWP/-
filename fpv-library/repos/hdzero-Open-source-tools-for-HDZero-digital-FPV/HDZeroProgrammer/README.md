# HDZero Programmer

A native macOS (SwiftUI) app to **flash HDZero gear** — VTX, goggles/VRX, and the ELRS radio —
without the Windows-only vendor tools. It wraps the right flasher per device behind one UI:

| Device | Method | Read / Detect | Verify |
|---|---|---|---|
| **VTX** | bundled **`flashrom`** via a **CH341A** clipped to the SPI flash (runs as root once — macOS asks for your admin password) | ✅ flashrom probe (chip + size) | ✅ flashrom write-verify + standalone Verify |
| **Monitor** | native **CH341 SPI** over IOKit (3 banks: 5680/FPGA/8339) | ✅ JEDEC chip id | ✅ read-back compare |
| **Event VRX** | native **CH341 SPI** over IOKit (2 banks: 5680/FPGA) | ✅ JEDEC chip id | ✅ read-back compare |
| **Radio** (ELRS TX/backpack + STM32) | **esptool** (ESP32/C3) + **XMODEM** (STM32) over USB-serial | ✅ serial-port scan | ✅ esptool MD5 (ESP) · XMODEM checksum (STM32) |
| **Goggle 2** | **CH341A SPI** via the firmware socket + HDZero Programmer cable | ✅ flashrom probe | — *(write deferred, see below)* |

Firmware is fetched from the official catalog at flash time.

## Read / Detect first

Every tab has a **Read / Detect device** button. It confirms the programmer/cable is reaching the
device and reads the flash chip's id/size **before** you commit a write — so a loose clip, an
unpowered device, or a wrong cable shows up immediately instead of mid-flash. After a write, the
CH341 (Monitor/Event VRX) and Radio paths **read the data back / MD5-compare** to confirm the flash
matches the image; flashrom (VTX) verifies as part of the write and offers a standalone **Verify**.

> The native CH341 paths (Monitor/Event VRX/Goggle 2) were hardware-unverified — **Read / Detect** is
> the quickest way to confirm the cable + protocol actually talk to the flash on your hardware.

## Goggle 2 (Read/Detect now, write deferred)

The Goggle 2 flashes over **CH341A SPI** through its firmware socket. This build ships **Read/Detect
only**: connect the HDZero Programmer cable and read the flash chip to identify it safely. **Writing
is intentionally disabled** until the chip and the Goggle 2 firmware image layout are confirmed — a
blind write can brick the goggle.

## Build / run

```bash
./build_app.sh          # compiles, embeds flashrom (+ dylibs), signs (Developer ID),
                        # notarizes, and packages "HDZero Programmer.app" + a .dmg
open "HDZero Programmer.app"
```

`DO_NOTARIZE=0 ./build_app.sh` skips notarization for a quick local build.

Build-time requirements (dev Mac): Xcode toolchain, Homebrew **`flashrom`** and **`dylibbundler`**.
The shipped app is **fully portable** — `flashrom` and its dynamic libraries (`libftdi1`, `libusb`,
`libcrypto`) are embedded in `Contents/Resources/flashrom/`, relinked to `@executable_path`. No
Homebrew/flashrom needed on the target Mac.

## Install

Download the `.dmg` from the repo's [**Releases**](../../releases), drag **HDZero Programmer** to
`/Applications`, and launch. Apple-signed + notarized — no Terminal/`xattr` workaround. Requires
macOS 13 (Ventura) or newer.

> ⚠️ Flashing hardware can brick a device if interrupted or mis-targeted. Use at your own risk; make
> sure you pick the correct firmware for your gear.

## Hardware (VTX via flashrom)

A **CH341A** USB programmer with a SOIC clip on the VTX's SPI flash chip, VTX powered as instructed.
