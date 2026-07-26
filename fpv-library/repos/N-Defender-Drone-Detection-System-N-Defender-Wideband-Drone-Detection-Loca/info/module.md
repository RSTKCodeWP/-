Good, that wall of text was turning into RF spaghetti.
I’ve filtered it down to **only the modules that actually match your spec**:

* Bare PCB / OEM modules (not goggles or boxed VRX)
* Analog **CVBS video out**
* **RSSI output** (documented, or clearly part of the family)
* **Digital channel control** (SPI or GPIO/DIP that you can drive from MCU)

Everything else (half-documented goggle receivers, boxes with 12 V + AV jack, no RSSI, no control info) is dropped.

---

## 5.8 GHz analog FPV A/V receiver modules

### 5.8 GHz band – cleaned list

| Module / Part No.      | Vendor                         | Freq range (MHz)                                                                       | Sensitivity*                           | Outputs (CVBS / RSSI / audio)                                                                                           | Digital control                                                                                                    | Supply (V / mA)                               | Notes                                                                                                                                               |
| ---------------------- | ------------------------------ | -------------------------------------------------------------------------------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FS58R3MW (MM238RW)** | FPVspeed                       | **4900–5945** (FPV bands A/B/E/F style) ([fpvspeed.com][1])                            | **–90 dBm** (spec) ([fpvspeed.com][1]) | CVBS: 1 ± 0.2 Vpp, 75 Ω, negative; 50 Hz–6 MHz, S/N ≥ 38 dB; RSSI: **0.7–2.2 V for –30 to –90 dBm** ([fpvspeed.com][1]) | **SPI PLL** (RTC6705, SPI protocol + C ref files provided) ([fpvspeed.com][1])                                     | 3.3–5.0 V, **220 mA max** ([fpvspeed.com][1]) | Modern RX5808-class successor; fully documented CVBS + RSSI + SPI; small PCB (28 × 23 mm). Very “engineer-friendly” 5.8G VRX. ([fpvspeed.com][1])   |
| **RX5808 bare module** | Various (Foxtech, generic OEM) | ~**5725–5865** for 8CH boards; up to 40+ CH with SPI (depending on design) ([eBay][2]) | ~**–90 dBm** (chip datasheet)          | CVBS ~1 Vpp, 75 Ω; analog **RSSI pin** on chip is usually routed out on module header ([eBay][2])                       | **3-wire SPI** (LE, CLK, DATA) for frequency; some boards also expose “channel select” GPIO-only modes ([eBay][2]) | ~3.5–5.5 V, ~170–220 mA (typ. board)          | Old workhorse. Documentation is weaker than FS58R3MW but ecosystem is huge (open-source diversity receivers, etc). Cheap fallback / low-end option. |

*Sensitivity is “datasheet RF sensitivity”, not “marketing range”.

**What I kept / removed for 5.8 GHz**

* **Kept:** FS58R3MW (your best serious OEM 5.8G VRX) and RX5808 (cheap legacy option).
* **Dropped:** rapidFIRE, SpeedyBee, AKK goggle modules etc. – they’re not bare PCB with documented RSSI + SPI/GPIO control; they’re finished goggle/box receivers.

---

## 1.2 / 1.3 GHz analog FPV A/V receiver modules

### 1.2 / 1.3 GHz band – cleaned list

| Module / Part No.      | Vendor      | Freq range (MHz)                                                                                         | Sensitivity                                     | Outputs (CVBS / RSSI / audio)                                                                                                          | Digital control                                                                                        | Supply (V / mA)                                                            | Notes                                                                                                                                |
| ---------------------- | ----------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **SK1200-SPI**         | Weidesupply | **1080–1700** ([weidesupply.com][3])                                                                     | **–95 dBm ± 3** ([weidesupply.com][3])          | CVBS: 1 ± 0.2 Vpp, 75 Ω; analog RSSI with documented curve ≈1.09 V (–90 dBm) → 2.69 V (–30 dBm) ([weidesupply.com][3])                 | **SPI** (DATA, LE, CLK) – fully open “drone receiver” design ([weidesupply.com][3])                    | 5 V, **420 ± 30 mA** ([weidesupply.com][3])                                | Wide-tuning 1.2/1.3-class open-source module. Nice if you want fully documented RSSI slope + SPI in this band.                       |
| **FS12R9MV (VM1373R)** | FPVspeed    | **1080–1360** (1.2/1.3 GHz, 9 CH) ([fpvspeed.com][4])                                                    | **–95 dBm ± 2** ([fpvspeed.com][4])             | CVBS: 1 ± 0.2 Vpp, 75 Ω; marketed as “high sensitivity, strong RSSI signal detection” (analog RSSI output) ([fpvspeed.com][4])         | 9-channel selection via digital pins / DIP; suitable for MCU GPIO control (FM/PLL) ([fpvspeed.com][4]) | 5 V, **380 ± 30 mA** ([fpvspeed.com][4])                                   | Focused 1.2/1.3G FPV VRX, explicitly aimed at “secondary development”. Good default 1.2/1.3 module if you don’t need crazy wideband. |
| **FS13R9MS (SM1370R)** | FPVspeed    | **~1050–1380** (1.2/1.3 GHz 9 CH) ([eBay][5])                                                            | ~**–95 dBm** (same family, exact number in PDF) | CVBS + **audio** (A/V module with sound); analog RSSI typical for this family (explicit in FPVspeed docs / marketing) ([Pinterest][6]) | 9-channel GPIO/DIP style control (same architecture as FS12R9MV) ([fpvspeed.com][7])                   | 5 V, **300 mA max** ([eBay][5])                                            | Use this when you need 1.2/1.3G with integrated analog audio + CVBS + RSSI, and you’re okay with 9 fixed channels.                   |
| **FS1264R**            | FPVspeed    | **1080–2200** (64 CH across 1.2 / 1.4 / 1.5 / 1.6 / 1.7 / 1.8 / 1.9 / 2.0 / 2.2 GHz) ([fpvspeed.com][1]) | **–95 dBm** class ([fpvspeed.com][1])           | CVBS output (1 Vpp / 75 Ω in family datasheets) + analog RSSI detection ([fpvspeed.com][1])                                            | 6-pin 1.27 mm DIP / TTL GPIO for channel select; also MCU-drivable PLL (SPI-like) ([fpvspeed.com][1])  | 5 V (current similar to SK1200: ~400 mA; exact in PDF) ([fpvspeed.com][1]) | Wideband monster: if you want **1.2G now but also 1.5–2.2G later**, this is the flexible option with RSSI + CVBS.                    |

**Band-level reality for 1.2/1.3 GHz**

* Serious OEM boards are basically **FPVspeed (FS12/13/1264) + SK1200-SPI**.
* Cheap “1.2G receiver boxes” without RSSI / SPI were **not** included – they don’t fit your requirements.

---

## ~3.3 GHz analog FPV A/V receiver modules

### 3.1–3.7 GHz band – cleaned list

| Module / Part No.        | Vendor                                         | Freq range (MHz)                                                   | Sensitivity                                                                   | Outputs (CVBS / RSSI / audio)                                                                                                       | Digital control                                                                                                                                  | Supply (V / mA)                                                            | Notes                                                                                                                                                                                    |
| ------------------------ | ---------------------------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FS3137RX**             | FPVspeed                                       | **3100–3700** (3.3 GHz band) ([fpvspeed.com][4])                   | ≈**–95 dBm** class (same RF family; exact in PDF)                             | CVBS analog output (FPV VRX family); analog RSSI (standard for FSxx receivers – called out in family marketing) ([fpvspeed.com][4]) | **SPI mode** for LO/channel; explicitly “SPI Mode, High Sensitivity, Supporting Secondary Development” ([fpvspeed.com][4])                       | 5 V (current similar to FS58R3MW; exact in PDF)                            | This is the **cleanest 3.3 GHz match** to FS58R3MW: same vendor, same design philosophy, SPI-controlled, intended for OEM/DIY integration.                                               |
| **SK3500-SPI**           | (Weidesupply ecosystem; sold via Fruugo, etc.) | **~3100–3800** (3.3 GHz band) ([fpvspeed.com][8])                  | ~**–95 dBm** (family spec)                                                    | CVBS 1 ± 0.2 Vpp, 75 Ω and analog RSSI (same architecture as SK1200-SPI; detailed in vendor docs) ([fpvspeed.com][8])               | **SPI** (open-source receiver; marketed explicitly as SPI open-source VRX) ([fpvspeed.com][8])                                                   | 5 V class, current similar to SK1200; see SK3500 datasheet for exact value | “Open-source” 3.3 GHz VRX module. Same style as SK1200-SPI but centered in C-band. Attractive if you want all three bands on the same SK-family footprint.                               |
| **FT3500 3.3G VRX 64CH** | Shenzhen Xingkai / FTYTO (many rebrands)       | **3060–3500** (64 CH) ([Shenzhen Xingkai Technology Co., Ltd.][9]) | **–97 to –95 dBm** (vendor spec) ([Shenzhen Xingkai Technology Co., Ltd.][9]) | Composite CVBS video output; analog RSSI “signal detection” is explicitly supported ([Shenzhen Xingkai Technology Co., Ltd.][9])    | Channel via **high/low-level GPIO pins** or solderable 6-digit DIP switch – easy to map to MCU GPIO ([Shenzhen Xingkai Technology Co., Ltd.][9]) | 5 V (small PCB, ~37 × 26 mm) ([Shenzhen Xingkai Technology Co., Ltd.][9])  | Very common 3.3 GHz VRX module in the Chinese market; high sensitivity, 64 channels, many sellers (Alibaba, Made-in-China, etc.). Good if you need availability and simple GPIO control. |

---

## TL;DR – what this cleaned list actually means for your design

If you want **one serious, documented module per band** that ticks *all* your boxes (bare PCB + CVBS + RSSI + digital):

* **5.8 GHz (primary)** → **FS58R3MW (MM238RW)**
* **1.2/1.3 GHz (primary)** → **FS12R9MV** or **SK1200-SPI** (pick based on how wide a band you want)
* **3.3 GHz (primary)** → **FS3137RX** or **FT3500** (SPI vs simple GPIO trade-off)

RX5808, FS13R9MS, FS1264R, SK3500-SPI are **valid second-line options** / alternates (audio, wideband, open-source).

Everything else from the previous mess that didn’t clearly expose **CVBS + RSSI + digital control** is intentionally thrown out. No point designing around half-documented goggles or plastic boxes when you’re building a proper flight-computer-grade system.

If you want, next step I can:

* Build you a **single “VRX footprint + pinout standard”** per band (FS-family vs SK/FT-family),
* Or map these modules into a **unified MCU driver API** (channel select, RSSI read, band abstraction).

[1]: https://fpvspeed.com/product/showproduct.php?id=50 "FPVspeed VRX FS58R3MW MM238RW 4.9G 5.8G 6G"
[2]: https://www.ebay.com/itm/265118618399?utm_source=chatgpt.com "RC FPV 5.8G Wireless Audio Video Receiving Module ..."
[3]: https://www.weidesupply.com/open-source-receiver-drone-module-price/?utm_source=chatgpt.com "SK1200-SPI Revolutionary Open Source Receiver - Weidesupply"
[4]: https://fpvspeed.com/product/showproduct.php?id=173 "FPVspeed FS12R9MV VM1373R VRX Module 1.2G 1.3G 9CH"
[5]: https://www.ebay.com/itm/197020052656?utm_source=chatgpt.com "FPVspeed VRX Module FS13R9MS SM1370R 1.2G 1.3G ..."
[6]: https://www.pinterest.com/pin/fpvspeed-vrx-fs13r9ms-sm1370r-12g-13g-9ch-in-2025--4603804823851598080/?utm_source=chatgpt.com "מודול FPVspeed VRX FS13R9MS SM1370R 1.2G 1.3G 9CH ..."
[7]: https://www.fpvspeed.com/product/index.php?class1=221&lang=cn&order=new&page=3&search=search&utm_source=chatgpt.com "产品中心"
[8]: https://www.fpvspeed.com/product/?utm_source=chatgpt.com "Products"
[9]: https://xingkaitech.en.made-in-china.com/product/ipRrOzKFnGhM/China-FT3500-3-3GHz-Vrx-64CH-Fpv-Analog-Video-Receiver-Module-3060MHz-3500MHz-High-Sensitivity-Reception-97dBm-for-Fpv-Drone.html?utm_source=chatgpt.com "FT3500 3.3GHz Vrx 64CH Fpv Analog Video Receiver ..."






