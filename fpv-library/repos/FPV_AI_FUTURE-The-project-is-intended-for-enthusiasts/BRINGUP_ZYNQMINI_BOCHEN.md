# Board card — BoChen JingXin «ZYNQ MINI» (XC7Z020) — Block-3 bring-up

Identified from the owner's board photos (2026-07-11). This is the concrete "Zynq Mini" that
`FPGA_MIGRATION_ZYNQ7020_FT640LM.md` and [`BRINGUP.md`](BRINGUP.md) target. This file pins the
board-specific facts (boot, power, ports, pinout) so the generic bring-up becomes turnkey.

## 1. Identity
- **Vendor:** 博宸精芯 (BoChen JingXin).  **Board:** ZYNQ MINI 开发板.  **Rev:** 20240221 / REV B.
- **SoC:** Xilinx **XC7Z020-CLG400** (silk `…ABX2445`; label `IC: 7Z020`).
- **DDR3** (Micron), **QSPI flash** (Winbond), **24C02** EEPROM, **0.96" OLED**, USB-JTAG/UART bridge (FTDI).

## 2. Power & boot (physical, owner-only)
- **Power: 5 V via Type-C ONLY** (silk: 仅支持5V TYPE-C供电). Do not feed other rails.
- **Boot mode DIP** (`BOOT`, 2-pos; silk note: 数字侧=1, ON侧=0):
  | Mode | DIP |
  |---|---|
  | JTAG | 00 |
  | QSPI | 10 |
  | **SD card** | **11** |
  → For our SD bring-up set **SDCARD = 11**.

## 3. Ports (what the board gives / does NOT give)
| Port | Note |
|---|---|
| microSD (`SD0`) | boot medium |
| HDMI | **OUT only** — for the operator overlay. **No video input on this board.** |
| Dual RJ45 GigE | one PS (`ETH PS`), one PL (`ETH PL`) |
| USB-C ×3 (bottom) | `JTAG`, `USB` (the single PS USB 2.0 OTG), `UART` |
| `EXT IO 3.3V` header | PL bank I/O at 3.3 V — **the wiring point for the flight ingest (BT.656) + IMU SPI** |

**Consequence for ingest:** there is no camera/video input and only one PS USB. Two paths:
- **Bench (software) path:** FT640→MS2107(CVBS→USB)→the PS `USB` port (USB-C→USB-A OTG adapter, host mode
  in the Linux image; grabber may need a powered hub — board is 5 V-only). Runs the Python seeker on
  the ARM, non-real-time. **Yields the same numbers a PC gives — see §5, prefer the PC for measurement.**
- **Flight (hardware) path — this board's real job:** FT640→TVP5150/ADV7280(CVBS→BT.656)→**EXT IO pins→PL**.
  The RTL frontend (`rtl/bt656_rx.v` …) already ingests exactly this. See `BRINGUP.md` §1–3.

## 4. EXT IO 3.3V header — pinout (transcribed from the REV-B silk photo)
LVCMOS33 PL I/O. Two columns, top→bottom. **Verify against the vendor silk/pinout before committing a
pin assignment** (photo transcription; the second `P15` below is a likely read artifact):

```
 V5.0  GND      W14  Y14      P19  V20
 P15   U15      P15* V16      P18  U20
 V15   W15      R16  U18      N18  T20
 V17   U17      T16  Y17      N20  P20
 Y18   V18      W16  R17      GND  GND
 Y19   W18      R18  W20      V3.3 V3.3
 W19   U19
 N17   U14
```
Use for the flight ingest: 8× BT.656 data + PCLK (→ `bt656_rx.v`), I²C SCL/SDA (decoder config), and
SPI (SCLK/MOSI/MISO/CS + an ext-clock out) for the ICM-42688-P IMU. Assign in a board XDC once wired.

## 5. Bring-up order (honest, two decoupled tracks)
1. **Seeker-on-real-thermal MEASUREMENT — do on a PC/Mac now, not on this board.** FT640→MS2107→
   `real_ingest --source 0/dev/video0`. Same Python, 10 minutes, first honest detect/lock/σ numbers.
   This board is the wrong tool for that job (bare FPGA board, single PS USB, minimal rootfs).
2. **This board = PL bring-up (its purpose).** Port is **co-sim green here** (`PYTHONPATH=fpv python3 -m
   pytest fpga -q` → 40 pass). Next, on a **Vivado box** (Vivado not on this Mac):
   - export XSA / get the vendor board files (needs the vendor resource pack — QR on the board label);
   - regenerate golden vectors: `PYTHONPATH=fpv python3 -m fpga.ref_model.golden_vectors --out fpga/ref_model/vectors --frames 120`;
   - integrate the RTL top-level + write the board **XDC** from §4, synthesize, verify OFF==bit-exact vs the Python golden.
3. Wire the CVBS→BT.656 decoder to the EXT IO pins (§4) and run the frontend on live FT640.

## 6. What blocks progress right now
- Vendor **resource pack** (SD image / XSA / board files / pin map) — scan the QR on the board label or
  the vendor store. Needed for both a PetaLinux image and the correct DDR/MIO/USB config.
- A **Vivado** machine (this Mac has iverilog+clang for co-sim, but not Vivado for synthesis/P&R).
- Decoder part (TVP5150/ADV7280) for the flight ingest (BOM gap).
