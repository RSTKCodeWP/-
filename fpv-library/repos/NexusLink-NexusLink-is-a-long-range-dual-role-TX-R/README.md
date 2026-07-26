# Frequency Hopping Radio Videolink Anti‑Interference Radio Drone Image Link (FH‑VLink)

**Long‑Range, Frequency‑Hopping, Dual‑Role Digital Link for FPV Drones**

> One system that handles **control** *and* **video/data**, with **adaptive frequency‑hopping** across modular RF bands. Designed for long‑range FPV, anti‑jam robustness, and developer extensibility.

## Branding & Naming

* **Official product name**: Frequency Hopping Radio Videolink Anti‑Interference Radio Drone Image Link
* **Short name (working)**: **FH‑VLink**
  (easy to use in firmware IDs, SKUs, silk screens. If you prefer another alias, we can change everywhere in one pass.)
* **Sub‑modules**: **FH‑CTRL** (control), **FH‑VID** (video/data)
* **Example model codes**:

  * **FS‑FH‑VLINK‑AU‑24** → Air Unit, 2.4 GHz BandPack
  * **FS‑FH‑VLINK‑GU‑58** → Ground Unit, 5.8 GHz BandPack

---

## 1) Project Overview

**FH‑VLink** (Frequency‑Hopping Long‑Range) is a modular, SDR‑based link that acts as **TX and RX** on both ends (Air Unit ↔ Ground Unit). It carries:

* **Control/Telemetry**: deterministic, low‑latency CRSF‑class link.
* **Digital Video/Data**: low‑latency H.265/H.264 video with COFDM/OFDM PHY.

Core design goals:

* **Long range**, **resilience to interference/jamming**, **multi‑band agility**, **developer‑friendly**, and **legally configurable per region**.

> ⚠️ Regulatory note: RF bands, power, and channelization must be configured to the **local authority** (e.g., WPC (India), ETSI (EU), FCC (US)). FH‑VLink ships with region **profiles**; end‑users must select a compliant profile.

---

## 2) Key Capabilities

* **Dual‑Role**: Each unit can **transmit & receive**; supports **TDD** framing for simultaneous video downlink + control uplink.
* **Adaptive FHSS**: Fast frequency hopping for control; **channel‑agile** OFDM for video with blacklist/whitelist and DFS‑aware scanning.
* **Multi‑Band** (modular): Pluggable RF “BandPacks” covering **Sub‑GHz**, **1.2–1.3 GHz**, **2.4 GHz**, **5.1–5.9 GHz**, with roadmap to **6 GHz**.
* **Anti‑Jam Suite**: fast hop reseeding, interference maps, notch filters,
  interleaved FEC, optional antenna diversity/beamforming.
* **Low Latency Video**: Target **≤35 ms** 720p60; **≤90 ms** 1080p60 (encoder + PHY + jitter buffer).
* **ELRS/CRSF Friendly**: Native CRSF serial bridge; supports passthrough to FC.
* **Secure**: Mutual auth, per‑session keys, **AES‑GCM** stream encryption.
* **Telemetry & Mavlink**: bidirectional data pipe; OSD overlay hooks.
* **Open SDK**: C/C++/Python APIs; message schemas; logging and RF diagnostics.

---

## 3) System Architecture

### 3.1 Top‑Level

```
[Controller] ⇄ [Ground Unit (GU)]  ⇄  (Air Link)  ⇄  [Air Unit (AU)] ⇄ [Flight Controller / Camera]
```

* **GU**: Receives video, transmits control/telemetry. Optional HDMI/USB‑UVC out.
* **AU**: Transmits video, receives control/telemetry. CSI/HDMI‑in from camera/VTX encoder.

### 3.2 Functional Blocks

* **SDR Transceiver**: 70 MHz–6 GHz coverage (e.g., AD936x‑class / LMS7002M‑class).
* **RF Front‑Ends (per BandPack)**: PA, LNA, filters/duplexers, T/R switching.
* **Clocking**: Low‑jitter TCXO/OCXO; shared 10 MHz ref; GPSDO optional.
* **Baseband**: SoC/MPU (e.g., CM4/RK356x) running PHY/MAC and codecs.
* **Video**: H.265/H.264 HW encoder/decoder; CSI‑2/HDMI I/O; OSD overlay.
* **Security**: TPM/SE for key store; ECDH handshake; AES‑GCM stream.
* **I/O**: UARTs (CRSF/Mavlink), USB‑C, Ethernet (optional), GPIO.

### 3.3 Duplexing & Framing (TDD)

* **Superframe** example (10 ms):

  * **DL (Video/Data)**: 8.5 ms
  * **UL (Control/Telem)**: 1.0 ms
  * **Guard/Hop**: 0.5 ms for retune/HW settle
* **Hop sequence**: PRN seeded by link key + time; both ends derive same schedule.

---

## 4) RF Bands & BandPacks

> **BandPacks** are swappable RF front‑end modules. Each includes PA/LNA/Filters matched to a band.

| BandPack              |            Typical Range* | Example Use         | Notes                                                            |
| --------------------- | ------------------------: | ------------------- | ---------------------------------------------------------------- |
| **SUBG‑900**          | 902–928 MHz / 863–870 MHz | Control long‑range  | Excellent penetration; lower video capacity; ELRS‑class control. |
| **L‑BAND‑1.3**        |               1.2–1.3 GHz | Mixed video/control | Popular for LR video (region‑specific constraints apply).        |
| **S‑BAND‑2.4**        |               2.4–2.5 GHz | Primary video       | Good balance of bandwidth and range; crowded but agile.          |
| **C‑BAND‑5.8**        |               5.1–5.9 GHz | High‑rate video     | Shorter range; high bandwidth; DFS awareness.                    |
| **U‑NII‑6** (roadmap) |               5.9–7.1 GHz | Alt video           | Region‑dependent availability.                                   |

*Range depends on EIRP, antennas, terrain/LOS, modulation/coding.

**Per‑Region Profiles** (examples): `IN_WPC`, `EU_ETSI`, `US_FCC` → limits for channels, EIRP, DFS, duty cycle, hop rate, dwell time.

---

## 5) PHY/MAC Design

### 5.1 Control Link (FH‑CTRL)

* **Modulations**: LoRa/FLRC/GFSK selectable, adaptive.
* **FHSS**: Fast (≥5–50 hops/s), per‑superframe hopping; blacklist noisy channels.
* **Throughput**: 25–500 kbps (configurable), **1–8 ms** command slots.
* **Error protection**: Interleaving + convolutional/LDPC FEC.
* **Interfaces**: CRSF serial to FC; Mavlink passthrough; SBUS fallback.

### 5.2 Video/Data Link (FH‑VID)

* **Waveform**: COFDM/OFDM with adaptive MCS (QPSK → 64‑QAM), 5–40 MHz BW.
* **Channel Agility**: mid‑frame retune disallowed; per‑frame channel switch with guard.
* **FEC**: LDPC + interleaver; **ARQ‑lite** for key I‑frames only.
* **Bitrate Targets**: 5–25 Mbps payload typical; scalable.
* **MIMO**: 1×1 base; 2×2 optional with antenna diversity/beamforming.

### 5.3 Hopping & Interference Maps

* Periodic **RF survey** builds a heat‑map; channels scored and blacklisted.
* Hop table derived as: `channels = sort_by(score) -> take N -> PRN_shuffle(seed)`.
* Guard time enforces LO settle + PA/Filter switch.

---

## 6) Security & Pairing

* **Pairing**: ECDH (Curve25519) key agreement; signed firmware; device identity in SE/TPM.
* **Crypto**: AES‑256‑GCM per stream; rolling nonce; replay protection.
* **Lockouts**: Region profile + hop table integrity checks.

---

## 7) Performance Targets (Rev‑A)

| Metric                    | Target                                                              |
| ------------------------- | ------------------------------------------------------------------- |
| Control latency (cmd→act) | **≤12 ms** (typical), hard cap 20 ms                                |
| Video glass‑to‑glass      | **≤35 ms** @ 720p60; **≤90 ms** @ 1080p60                           |
| Control range*            | 20–50 km LOS (Sub‑GHz)                                              |
| Video range*              | 10–20 km LOS (2.4 GHz), 5–10 km LOS (5.8 GHz)                       |
| Jamming resilience        | Maintains control under wideband noise + ≥50% channel loss via FHSS |

*Estimates; vary by EIRP, antennas, terrain, MCS.

---

## 8) Hardware Specification (Initial)

### 8.1 Common

* **Transceiver**: SDR (70 MHz–6 GHz), 56 MHz inst. BW
* **Clock**: 0.5 ppm TCXO; ext 10 MHz in/out; GNSS timing (option)
* **MCU/SoC**: Compute Module (e.g., CM4/RK3566) + **ESP32‑S3** for UI/peripherals
* **Video I/O**: CSI‑2 (2/4‑lane), HDMI‑in (AU), HDMI‑out/USB‑UVC (GU)
* **Storage**: µSD (video record on GU/AU), eMMC for OS
* **I/O**: 2×UART, 1×CAN, 1×ETH (opt), 2×USB‑C, GPIO, I²C, SPI
* **Antenna**: 2× MMCX/SMA per BandPack (diversity/MIMO)
* **Enclosure**: aluminum + finned heatsink; IP54 (GU), IP52 (AU)

### 8.2 RF Front‑End per BandPack

* **PA**: 27–36 dBm (band‑dependent; region‑limited)
* **LNA**: NF ≤1.5 dB (target), gain 15–22 dB
* **Filters**: SAW/BPF per band; switchable notch for co‑site interference
* **Switching**: High‑power T/R switch; fast LO/themally managed

### 8.3 Power

* **Input**: 7–25 V DC (AU), 9–26 V (GU); reverse‑polarity + surge protection
* **Consumption** (typical): AU 6–12 W (video on); GU 5–10 W
* **Thermals**: active fan (PWM) on AU; passive + optional fan on GU; thermal foldback

---

## 9) Software & Firmware

* **OS**: Linux for SoC; FreeRTOS/ESP‑IDF for ESP32‑S3
* **Stacks**: PHY/MAC in userland with RT priorities; kernel drivers for SDR
* **Encoders**: H.265/H.264 HW; CBR/VBR and GOP tuning for low latency
* **APIs**: gRPC/Proto for control, Python/C++ SDKs
* **Ground App**: Cross‑platform UI (RF map, channel stats, bitrate, OSD overlay)
* **Failsafe**: CRSF failsafe injection; programmable RTH triggers; link quality guards
* **Logging**: pcap‑like RF logs, video QoS stats, GPS/RSSI/Link budget per hop
* **Update**: A/B OTA, signed images

---

## 10) Interfaces (Flight Stack & Peripherals)

* **CRSF (ELRS‑compatible)** bridge; 400–1000 Hz rates
* **Mavlink** over UART/Ethernet/USB
* **DJI/Analog camera** via HDMI/CSI‑2; UVC for PC ingest
* **SBUS** fallback output
* **GPIO**: arming, record trigger, fan, status LEDs

---

## 11) Antennas

* **SUB‑GHz**: ¼‑wave whip or cross‑polarized Yagi (GU)
* **1.3 GHz**: CP patch (AU) + helical/Yagi (GU)
* **2.4/5.8 GHz**: CP pagoda/patch (AU), high‑gain panel/dish (GU)
* **Diversity/MIMO**: spatially separated ports; optional **stacked CP**

---

## 12) Manufacturing & Test

* **Factory Cal**: TX power flatness per band, RX gain/NF, LO leakage, EVM
* **Self‑Test**: loopback paths + attenuator
* **End‑of‑Line**: BER/FER under multipath emulator; thermal ramp; soak tests
* **Docs**: test scripts, golden units, calibration blobs per BandPack

---

## 13) Roadmap

* **R0**: RF bring‑up on 2.4/5.8, basic FH‑CTRL @ Sub‑GHz (Weeks 0–8)
* **R1**: Low‑lat H.265 720p60 @ 2.4 GHz; control over Sub‑GHz; unified TDD (Weeks 9–16)
* **R2**: 1080p60, MIMO 2×2 option; antenna diversity; security hardening (Weeks 17–26)
* **R3**: 1.3 GHz BandPack, auto band‑failover, GU recorder app (Weeks 27–36)
* **R4**: 6 GHz exploration, beamforming panel (GU), SDK GA (Weeks 37–48)

---

## 14) Open Risks & Questions

* **Regulatory**: 1.3 GHz availability varies; ensure profile lock + geofencing.
* **Latency vs Hopping**: retune guards must not blow glass‑to‑glass budgets.
* **Thermals**: AU PA dissipation at high duty cycles.
* **Co‑site Interference**: with GPS, OSD, digital FC noise on AU.
* **Multipath in urban**: need robust interleaver + pilot tone design.

---

## 15) Repository Structure

```
FH-VLink/
├─ firmware/
│  ├─ fh-ctrl/           # control PHY/MAC
│  ├─ fh-vid/            # video PHY/MAC
│  ├─ hal/               # SDR + RF FE drivers
│  ├─ crypto/            # auth/encryption
│  └─ boot/              # secure boot + updater
├─ software/
│  ├─ ground-app/        # UI + recorder + OSD overlay
│  ├─ air-daemon/        # camera ingest + encoder + link mgr
│  └─ sdk/               # C++/Python APIs
├─ hardware/
│  ├─ au/                # Air Unit schematics + PCB
│  ├─ gu/                # Ground Unit schematics + PCB
│  └─ bandpacks/         # RF FE modules (subg, 1.3, 2.4, 5.8)
├─ docs/
│  ├─ specs/
│  ├─ rf-plans/
│  └─ compliance/
└─ README.md             # this file
```

---

## 16) Developer Quickstart (Draft)

```bash
# 1) Build containers
make containers

# 2) Build SDR kernels & drivers
./tools/build_sdr.sh

# 3) Build firmware (ctrl + vid)
make -C firmware all TARGET=au
make -C firmware all TARGET=gu

# 4) Ground UI
cd software/ground-app && npm i && npm run dev

# 5) Pairing (dev keys)
./tools/pair --gu usb0 --au usb1 --region IN_WPC
```

---

## 17) Compliance & Region Profiles

* Provide JSON profiles with: channels, BW, hop rate, dwell, max EIRP, DFS, TPC.
* Lock profile in SE; expose read‑only summary in UI.
* Ship only bands that are legal for destination region.

---

## 18) License & Contribution

* **License**: to be decided (e.g., dual: hardware docs under CERN‑OHL‑S; software under GPLv3/AGPLv3 or permissive).
* **Contrib**: PRs welcome after CLA; style guides in `/docs`.

---

## 19) Appendices

### A) TDD Superframe Example (10 ms)

```
|<--- 8.5ms Video DL --->|<1.0ms Ctrl UL>|<0.5ms Guard/Hop>|
```

### B) Hop Table Pseudocode

```python
channels = score_channels(scan())            # rank by noise/DFS/occupancy
pool = take_top(channels, N)
seq  = prn_shuffle(seed=KDF(link_key, time), pool)
for each superframe:
    ch = next(seq)
    tune(ch); transmit();
```

### C) Link Budget Worksheet (template)

* FSPL(dB) = 32.44 + 20·log10(f_MHz) + 20·log10(d_km)
* Margin(dB) = TX_Power + TX_AntGain + RX_AntGain − FSPL − NF − Required_SNR − Losses
* Aim for **≥ 10–15 dB** margin at planned range.

---

**Status**: `DRAFT R0` — ready to begin schematic capture for AU/GU, define BandPack pinouts, and spin SDR bring‑up boards.
