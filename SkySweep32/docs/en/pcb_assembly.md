# SkySweep32 Pro Tier — PCB Assembly Guide

> **Tier**: 🔴 Pro (Sentinel) — Full build: ESP32 + NRF24 + CC1101 + RX5808 + OLED + GPS + LoRa + SD Card  
> **PCB Size**: 120 × 80 mm, 2-layer FR4, 1.6 mm  
> **Files**: `hardware/skysweep32_pro.kicad_pcb`, `hardware/enclosures/skysweep32_pro_case_*.stl`

---

## Bill of Materials (BOM)

| Ref | Component | Value / Model | Package | Qty | Notes |
|-----|-----------|---------------|---------|-----|-------|
| U1 | LDO Voltage Regulator | AMS1117-3.3 | SOT-223 | 1 | 5V→3.3V, max 1A |
| J_ESP32_L/R | ESP32 Socket | ESP32 DevKit V1 (30-pin) | 2×15 header | 2 rows | **DO NOT solder ESP32 directly** — use socket headers |
| J_NRF24 | 2.4 GHz Module | NRF24L01+ PA+LNA | 2×4 2.54mm | 1 | Use PA+LNA version with external antenna |
| J_CC1101 | 900 MHz Module | CC1101 (8-pin SPI) | 2×4 2.54mm | 1 | Match frequency to your region: 868/915MHz |
| J_RX5808 | 5.8 GHz Video Rx | RX5808 | 1×6 2.54mm | 1 | **Needs 5V** — connect to VIN, not 3.3V |
| J_OLED | OLED Display | SSD1306 0.96" 128×64 I2C | 1×4 2.54mm | 1 | 4-pin I2C version only (GND/VCC/SCL/SDA) |
| J_GPS | GPS Module | NEO-6M or NEO-7M | 1×4 2.54mm | 1 | Include ceramic patch antenna |
| J_LORA | LoRa Module | SX1276 915MHz | 2×5 2.54mm | 1 | Match frequency to region |
| J_SD | MicroSD Module | SPI MicroSD adapter | 1×6 2.54mm | 1 | Use SPI version, not SDIO |
| J_PWR | DC Power Jack | 5.5/2.1mm barrel | CUI PJ-102A | 1 | 5V 2A minimum |
| J_BAT | LiPo Connector | JST-PH 2-pin | JST-PH B2B | 1 | 3.7V LiPo (optional) |
| J_SMA1 | SMA Antenna | 900 MHz (CC1101) | Edge-mount SMA | 1 | 8.2cm wire or helical |
| J_SMA2 | SMA Antenna | 2.4 GHz (NRF24) | Edge-mount SMA | 1 | Dipole or PCB antenna |
| J_SMA3 | SMA Antenna | 5.8 GHz (RX5808) | Edge-mount SMA | 1 | Cloverleaf RHCP/LHCP |
| J_SMA4 | SMA Antenna | 915 MHz (LoRa) | Edge-mount SMA | 1 | 8.6cm wire or helical |
| C_IN | Electrolytic Cap | 100µF / 16V | Radial D6.3mm | 1 | Input filter cap (5V rail) |
| C_OUT | Electrolytic Cap | 10µF / 10V | Radial D6.3mm | 1 | Output filter cap (3.3V rail) |
| C_NRF24_BIG | Electrolytic Cap | 10µF / 10V | Radial D6.3mm | 1 | NRF24 power stabilizer (important!) |
| C_RX5808 | Electrolytic Cap | 100µF / 10V | Radial D6.3mm | 1 | RX5808 5V stabilizer |
| C_* (×6) | Ceramic Cap | 100nF | SMD 0805 | 6 | Decoupling on each module VCC |
| R_BAT1, R_BAT2 | Resistor | 100kΩ | SMD 0805 | 2 | Battery voltage divider (GPIO36) |
| R_LED | Resistor | 330Ω | SMD 0805 | 1 | LED current limiter |
| LED1 | LED | Red, 3mm | THT | 1 | Threat indicator |
| BZ1 | Passive Buzzer | 5V passive | 12mm THT | 1 | GPIO4 PWM alert |
| H1–H4 | Mounting Holes | M3 NPTH | 3.2mm drill | 4 | For brass heat-set inserts |

**Estimated BOM cost**: ~$60–80 USD (all components)

---

## Pin Map (from `src/config.h`)

| ESP32 GPIO | Signal | Connected To |
|------------|--------|--------------|
| GPIO 2 | NRF_CE | NRF24L01+ CE pin |
| GPIO 4 | BUZZER | Passive buzzer + |
| GPIO 5 | CC_CS | CC1101 CSN |
| GPIO 12 | LORA_RST | SX1276 RESET |
| GPIO 13 | RX_CS | RX5808 SPI_SEL |
| GPIO 14 | LORA_CS | SX1276 NSS |
| GPIO 15 | NRF_CS | NRF24L01+ CSN |
| GPIO 16 | GPS_RX | GPS TX → ESP RX |
| GPIO 17 | GPS_TX | ESP TX → GPS RX |
| GPIO 18 | SPI_SCK | Shared SPI clock (all RF modules + SD) |
| GPIO 19 | SPI_MISO | Shared SPI MISO |
| GPIO 21 | I2C_SDA | OLED SDA |
| GPIO 22 | I2C_SCL | OLED SCL |
| GPIO 23 | SPI_MOSI | Shared SPI MOSI |
| GPIO 27 | SD_CS | MicroSD CS |
| GPIO 32 | LORA_DIO1 | SX1276 DIO1 |
| GPIO 33 | LORA_DIO0 | SX1276 DIO0 |
| GPIO 34 | RX_RSSI | RX5808 RSSI (ADC, input-only) |
| GPIO 36 | BAT_ADC | Battery voltage divider midpoint (ADC) |

> ⚠️ **Conflict**: GPIO 12/14 are shared between LoRa SX1276 and the optional I2S Microphone (Acoustic module). Do **not** enable both simultaneously.

---

## Soldering Order (Recommended)

Follow this sequence to avoid blocked access:

### Phase 1 — SMD Components First
1. **U1 AMS1117-3.3** (SOT-223) — solder to board first while flat
2. **SMD Capacitors** (100nF × 6, 0805) — all decoupling caps near each header
3. **SMD Resistors** (R_BAT1, R_BAT2 100kΩ, R_LED 330Ω, 0805)

### Phase 2 — Through-Hole Passive
4. **Electrolytic Caps** — C_IN (100µF), C_OUT (10µF), C_NRF24_BIG (10µF), C_RX5808 (100µF)  
   ⚠️ Mind polarity: the **longer leg is +** (positive)

### Phase 3 — Connectors & Headers
5. **SMA Edge-Mount Connectors** × 4 — align flush with board edge before soldering
6. **DC Power Jack** J_PWR
7. **JST-PH Battery Connector** J_BAT (if using LiPo)
8. **All Pin Headers** (1×4, 1×6, 2×4, 2×5) — use breadboard or modules to align
9. **ESP32 Socket Headers** (2 × 1×15, pin 1 at top) — **do not solder module directly**

### Phase 4 — Through-Hole Indicators
10. **LED1** (Red, 3mm) — flat side of LED towards R_LED resistor
11. **BZ1 Buzzer** — observe polarity marking

### Phase 5 — Modules
12. Insert all modules into headers (do not solder permanently)
13. Insert **ESP32 DevKit V1** into socket

---

## Power Architecture

```
5V DC Jack (J_PWR) ─────────┬──── RX5808 VCC (5V required!)
                             │
                        AMS1117-3.3V LDO
                             │
3.3V Rail ───────────────────┼──── ESP32 VCC
                             ├──── NRF24L01+ VCC (+ 10µF cap)
                             ├──── CC1101 VCC
                             ├──── OLED VCC
                             ├──── GPS VCC
                             ├──── LoRa VCC
                             └──── MicroSD VCC

LiPo (J_BAT, optional) ─── Voltage Divider (100k + 100k) ──── GPIO36 (ADC)
```

> ⚠️ **Peak current**: ~770mA with all modules active. Use a **5V 2A minimum** power supply.

---

## Ordering PCBs

### JLCPCB (recommended, cheapest)
1. Open `hardware/skysweep32_pro.kicad_pcb` in **KiCad 6+**
2. Go to **File → Plot** → select Gerber format → click **Plot**
3. Click **Generate Drill Files** → OK
4. Upload the `gerber/` folder to [jlcpcb.com](https://jlcpcb.com)
5. Settings: **2 layers**, **1.6mm**, **FR4**, **HASL or ENIG** finish, **Green** soldermask
6. Price: ~$2 for 5 boards + shipping

### PCBWay (alternative)
Same Gerber files work on [pcbway.com](https://pcbway.com) — slightly higher quality options.

---

## Firmware Build (Pro Tier)

```bash
# In project root:
pio run -e esp32dev_pro

# Or flash directly:
pio run -e esp32dev_pro -t upload
```

Make sure `platformio.ini` has:
```ini
[env:esp32dev_pro]
build_flags = -DTIER_PRO
```

---

## Testing Checklist

After assembly, verify in this order:

- [ ] **Visual inspect**: no solder bridges, all caps have correct polarity
- [ ] **5V rail**: measure 5V between J_PWR pins before inserting ESP32
- [ ] **3.3V rail**: measure 3.3V on U1 output after connecting power
- [ ] **Serial Monitor**: `pio device monitor` — check module init messages
- [ ] **NRF24**: serial should show `[NRF24] OK` or similar
- [ ] **CC1101**: serial should show `[CC1101] chip v=0x14`
- [ ] **RX5808**: RSSI reading should change when 5.8GHz source is nearby
- [ ] **OLED**: should display boot screen within 2 seconds
- [ ] **GPS**: open serial, wait ~60s for cold fix — check for NMEA sentences
- [ ] **LoRa**: serial should show `[LoRa] init OK`
- [ ] **SD**: insert formatted FAT32 card — serial should show `[SD] OK`
- [ ] **Web dashboard**: connect to WiFi `SkySweep32` → open `192.168.4.1`
