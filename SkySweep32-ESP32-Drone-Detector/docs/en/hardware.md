# Hardware Setup Guide

## Bill of Materials (BOM)

### Core RF Detection Modules

| Component | Specifications | Quick Search / Buy Links | Common Pitfalls & Notes | Approx. Cost |
|-----------|----------------|--------------------------|-------------------------|--------------|
| **ESP32 DevKit V1** | 240MHz dual-core, WiFi/BT, 520KB RAM | [AliExpress](https://www.aliexpress.com/wholesale?SearchText=ESP32+DevKit+V1+30P) / [Amazon](https://www.amazon.com/s?k=ESP32+DevKit+V1+30pin) | ⚠️ Do NOT buy **ESP8266** or **ESP32-S2/S3/C3** unless you are an expert, as the pin layout is completely different. | $5-10 |
| **CC1101 Module** (8-pin SPI) | 300-928MHz transceiver | [AliExpress](https://www.aliexpress.com/wholesale?SearchText=CC1101+8pin+915mhz) / [Amazon](https://www.amazon.com/s?k=CC1101+915mhz+8pin) | Make sure it's the standard **8-pin SPI version**. Buy the frequency matching your region (e.g. 868MHz for EU, 915MHz for US/UA). | $3-5 |
| **NRF24L01+ Module** (PA+LNA) | 2.4GHz transceiver | [AliExpress](https://www.aliexpress.com/wholesale?SearchText=NRF24L01%2B+PA+LNA) / [Amazon](https://www.amazon.com/s?k=NRF24L01%2B+PA+LNA) | Must have a **`+`** (plus) in the name. Get the version with external antenna and shielding for better range. | $2-4 |
| **RX5808 Module** (5.8G) | 5.8GHz video receiver | [AliExpress](https://www.aliexpress.com/wholesale?SearchText=RX5808+module) / [Amazon](https://www.amazon.com/s?k=RX5808+receiver+module) | Standard FPV receiver. Note: Some modules require bridging a jumper/resistor to enable SPI mode. | $3-5 |
| **OLED Display** (SSD1306) | 128x64 I2C SSD1306 | [AliExpress](https://www.aliexpress.com/wholesale?SearchText=0.96+OLED+I2C+SSD1306) / [Amazon](https://www.amazon.com/s?k=0.96+OLED+I2C+SSD1306) | Ensure it has **4 pins** (VCC, GND, SCL, SDA). Do NOT buy the 7-pin SPI version. | $3-5 |

### New Feature Modules (6 Enhancements)

| Component | Specifications | Quick Search / Buy Links | Common Pitfalls & Notes | Purpose | Approx. Cost |
|-----------|----------------|--------------------------|-------------------------|---------|--------------|
| **GPS Module** (NEO-6M/7M) | UART, 1Hz-10Hz update rate | [AliExpress](https://www.aliexpress.com/wholesale?SearchText=NEO-6M+GPS+module) / [Amazon](https://www.amazon.com/s?k=NEO-6M+GPS+module) | Ensure it comes with a ceramic patch antenna. | Geolocation tracking | $8-12 |
| **LoRa SX1276 Module** | 915MHz (US/UA) or 868MHz (EU) SPI | [AliExpress](https://www.aliexpress.com/wholesale?SearchText=SX1276+LoRa+module+915mhz) / [Amazon](https://www.amazon.com/s?k=SX1276+LoRa+module+915mhz) | Buy the correct frequency for your region. Must be SPI interface. | Meshtastic mesh | $6-10 |
| **MicroSD Card Module** | SPI interface, supports up to 32GB | [AliExpress](https://www.aliexpress.com/wholesale?SearchText=MicroSD+card+module+SPI) / [Amazon](https://www.amazon.com/s?k=MicroSD+card+module+SPI) | Choose the SPI interface module, not SDIO. | Data logging | $2-4 |
| **MicroSD Card** | 8-32GB Class 10 | [AliExpress](https://www.aliexpress.com/wholesale?SearchText=micro+sd+card+16gb) / [Amazon](https://www.amazon.com/s?k=micro+sd+card+16gb) | Needs to be formatted as FAT32 before use. | Log storage | $5-10 |

### Supporting Components

| Component | Quantity | Specifications | Approx. Cost |
|-----------|----------|----------------|--------------|
| Breadboard/PCB | 1 | For prototyping | $2-5 |
| Jumper Wires | 40+ | Male-to-female, various lengths | $3-5 |
| Power Supply | 1 | 5V 3A USB or LiPo 3.7V 2000mAh | $8-15 |
| Antennas (900MHz) | 1 | 8.2cm wire or helical | $2-5 |
| Antennas (2.4GHz) | 1 | Dipole or PCB antenna | $3-6 |
| Antennas (5.8GHz) | 1 | Cloverleaf RHCP/LHCP | $5-10 |
| Antennas (915MHz LoRa) | 1 | 8.6cm wire or helical | $3-6 |
| GPS Antenna | 1 | Passive ceramic patch | $3-8 |

**Total Cost**: ~$70-130 USD (with all 6 new features)

## Wiring Diagram

See [wiring_diagram.svg](../wiring_diagram.svg) for visual reference.

## Step-by-Step Assembly

### 1. ESP32 Preparation

- Connect ESP32 to breadboard
- Ensure 3.3V and GND rails are accessible
- **IMPORTANT**: ESP32 GPIO pins are 3.3V tolerant only!

### 2. SPI Bus Wiring (Shared)

Connect the following pins from ESP32 to ALL three RF modules:

| ESP32 Pin | Signal | Connect To |
|-----------|--------|------------|
| GPIO 23 | MOSI | CC1101 MOSI, NRF24 MOSI, RX5808 MOSI |
| GPIO 19 | MISO | CC1101 MISO, NRF24 MISO, RX5808 MISO |
| GPIO 18 | SCK | CC1101 SCK, NRF24 SCK, RX5808 SCK |
| 3.3V | VCC | All modules VCC |
| GND | GND | All modules GND |

### 3. Chip Select (CS) Pins

Each SPI device needs a unique CS pin:

| Module | ESP32 CS Pin | Module CS Pin | Tier |
|--------|--------------|---------------|------|
| NRF24L01+ | GPIO 15 | CSN | Base+ |
| CC1101 | GPIO 5 | CSN/SS | Standard+ |
| RX5808 | GPIO 13 | CS | Standard+ |
| LoRa SX1276 | GPIO 14 | NSS | Pro |
| SD Card | GPIO 27 | CS | Pro |

### 4. NRF24L01+ CE Pin

| ESP32 Pin | NRF24 Pin |
|-----------|-----------|
| GPIO 2 | CE |

### 5. RX5808 RSSI Pin

| ESP32 Pin | RX5808 Pin |
|-----------|------------|
| GPIO 34 (ADC) | RSSI |

### 6. OLED Display (I2C)

| ESP32 Pin | OLED Pin |
|-----------|----------|
| GPIO 21 | SDA |
| GPIO 22 | SCL |
| 3.3V | VCC |
| GND | GND |

### 7. GPS Module (UART2)

| ESP32 Pin | GPS Pin |
|-----------|---------|
| GPIO 16 | TX (GPS transmit) |
| GPIO 17 | RX (GPS receive) |
| 3.3V | VCC |
| GND | GND |

**Note**: GPS module TX connects to ESP32 RX and vice versa.

### 8. MicroSD Card Module (SPI)

| ESP32 Pin | SD Card Pin |
|-----------|-------------|
| GPIO 23 | MOSI |
| GPIO 19 | MISO |
| GPIO 18 | SCK |
| GPIO 27 | CS |
| 3.3V | VCC |
| GND | GND |

### 9. LoRa SX1276 Module (SPI)

| ESP32 Pin | LoRa Pin |
|-----------|----------|
| GPIO 23 | MOSI |
| GPIO 19 | MISO |
| GPIO 18 | SCK |
| GPIO 14 | NSS/CS |
| GPIO 33 | DIO0 |
| GPIO 32 | DIO1 |
| GPIO 12 | RST |
| 3.3V | VCC |
| GND | GND |

**Note**: LoRa CS (GPIO 14) and RESET (GPIO 12) share pins with the optional I2S Microphone (BCLK & WS). You cannot use both LoRa and Acoustic Detection simultaneously on the same board without custom pin reassignments.

### 10. Optional Peripherals (Alerts & Power)

| ESP32 Pin | Component | Description |
|-----------|-----------|-------------|
| GPIO 4 | Passive Buzzer | PWM audio alerts |
| GPIO 2 | LED | Visual threat indicator |
| GPIO 36 | Battery ADC | Voltage divider (100k/100k) for 4.2V lipo |

## Module-Specific Notes

### CC1101 (900 MHz RF)

- **Antenna**: Requires 868/915MHz antenna (wire length ~8.2cm for 915MHz)
- **Power**: Draws ~15mA in RX mode, ~30mA in TX mode
- **Voltage**: 1.8-3.6V (3.3V recommended)
- **Range**: Up to 500m line-of-sight

### NRF24L01+ (2.4 GHz RF)

- **Antenna**: Built-in PCB antenna or external SMA
- **Power**: PA+LNA version draws up to 115mA in TX mode
- **Voltage**: 1.9-3.6V (3.3V recommended)
- **Note**: Use 10µF capacitor between VCC and GND if experiencing instability
- **Range**: Up to 1000m with PA+LNA version

### RX5808 (5.8 GHz Video)

- **Antenna**: Requires 5.8GHz antenna (cloverleaf or patch)
- **Power**: ~100mA typical
- **Voltage**: 5V input (has onboard 3.3V regulator)
- **Note**: Connect VCC to ESP32 5V pin (VIN), not 3.3V
- **Channels**: 40 channels across 5 bands (Raceband, Fatshark, etc.)

### OLED Display (I2C)

- **I2C Address**: Usually 0x3C or 0x3D
- **Power**: ~20mA
- **Voltage**: 3.3V or 5V compatible
- **Resolution**: 128x64 pixels monochrome

### GPS Module NEO-6M/7M (UART)

- **Protocol**: NMEA 0183 standard
- **Update Rate**: 1Hz default (configurable up to 10Hz)
- **Accuracy**: 2.5m CEP (Circular Error Probable)
- **Cold Start**: ~27 seconds
- **Hot Start**: ~1 second
- **Power**: ~45mA active, ~10mA backup
- **Voltage**: 3.3V or 5V compatible
- **Antenna**: Requires passive ceramic patch antenna (included with most modules)

### MicroSD Card Module (SPI)

- **Supported Cards**: MicroSD, MicroSDHC (up to 32GB)
- **File System**: FAT16, FAT32
- **Power**: ~80mA during write operations
- **Voltage**: 3.3V or 5V with level shifter
- **Speed**: SPI mode up to 25MHz
- **Note**: Format card as FAT32 before first use

### LoRa SX1276 Module (SPI)

- **Frequency**: 915MHz (US) or 868MHz (EU)
- **Modulation**: LoRa, FSK, OOK
- **Sensitivity**: -148dBm (SF12, 125kHz BW)
- **Output Power**: +20dBm (100mW) maximum
- **Range**: Up to 10km line-of-sight
- **Power**: ~120mA TX mode, ~10mA RX mode
- **Voltage**: 3.3V
- **Antenna**: Requires 915MHz helical or wire antenna (8.6cm)
- **Protocol**: Meshtastic compatible

## Power Considerations

**Total Current Draw (All Features Enabled)**:
- ESP32: ~160mA (WiFi active), ~240mA (WiFi + BLE scanning)
- CC1101: ~30mA
- NRF24L01+: ~115mA (TX mode)
- RX5808: ~100mA
- OLED: ~20mA
- GPS Module: ~45mA
- SD Card: ~80mA (write operations)
- LoRa SX1276: ~120mA (TX mode)
- **Total Peak**: ~770mA (all modules transmitting simultaneously)
- **Typical Average**: ~350-450mA (normal operation)

**Recommended Power Supply**: 
- **USB**: 5V 3A adapter (recommended for bench testing)
- **Battery**: LiPo 3.7V 2000-3000mAh with 5V boost converter
- **Portable**: 18650 battery holder (2S configuration) with buck converter

**Battery Life Estimates** (2500mAh LiPo):
- Continuous operation: ~5-6 hours
- Low-power mode (GPS off, no logging): ~8-10 hours
- Deep sleep between scans: ~24+ hours

## Antenna Recommendations

### 900 MHz (CC1101)
- **Type**: Quarter-wave wire antenna
- **Length**: 8.2cm for 915MHz
- **Gain**: 0-2dBi

### 2.4 GHz (NRF24L01+)
- **Type**: PCB antenna (built-in) or external dipole
- **Gain**: 2-5dBi (PA+LNA version)

### 5.8 GHz (RX5808)
- **Type**: Cloverleaf (RHCP/LHCP) or patch antenna
- **Gain**: 2-8dBi
- **Connector**: SMA or RP-SMA

## Enclosure Design

Recommended enclosure specifications:
- **Material**: ABS plastic or 3D-printed PLA
- **Dimensions**: 120mm x 80mm x 40mm minimum
- **Features**:
  - Antenna ports (SMA bulkhead connectors)
  - Ventilation holes for heat dissipation
  - OLED display cutout
  - USB access for programming/power

## Testing Procedure

1. **Visual Inspection**: Check all connections for shorts
2. **Power Test**: Connect power, verify 3.3V on all module VCC pins
3. **Serial Monitor**: Upload firmware, check initialization messages
4. **Module Detection**: Verify each RF module responds (check serial output)
5. **RSSI Test**: Place active 2.4GHz device nearby, verify detection on NRF24
6. **Display Test**: Confirm OLED shows signal bars

## Troubleshooting

| Problem | Possible Cause | Solution |
|---------|----------------|----------|
| ESP32 won't boot | GPIO0 pulled low | Check wiring, ensure GPIO0 is floating |
| Module not detected | SPI wiring error | Verify MOSI/MISO not swapped |
| NRF24 unstable | Power supply noise | Add 10µF capacitor near VCC pin |
| RX5808 no signal | Wrong voltage | Ensure RX5808 VCC connected to 5V |
| OLED blank | Wrong I2C address | Try 0x3C or 0x3D in code |

## Safety Warnings

⚠️ **RF Exposure**: Keep antennas at least 20cm from body during operation.

⚠️ **ESD Protection**: Handle modules with anti-static precautions.

⚠️ **Overheating**: Ensure adequate ventilation, especially for PA+LNA modules.

## Next Steps

After hardware assembly, proceed to [Software Configuration](software.md).
