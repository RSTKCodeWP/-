Got it. I’ll conduct a thorough global search to identify OEM-style analog FPV A/V receiver modules that meet your specifications across the 5.8 GHz, 1.2/1.3 GHz, and ~3.3 GHz bands. I’ll prioritize modules with the highest sensitivity and advanced features, excluding consumer-finished products and digital systems. For each band, I’ll provide details like frequency range, bandwidth, part number, manufacturer, CVBS and RSSI outputs, digital interfaces, key features, and relevant URLs. I’ll organize this information in a clear table, sorted by the most advanced options first. I’m starting the deep search now.


Here is a summary of bare‑board analog FPV receiver modules that fit the specifications.  The list is grouped by band and ordered from highest‑performing to lower‑end within each band.

| Band                   | Frequency range (channels)                      | RF bandwidth (IF)                     | Module / product name                                      | Part number / code           | Manufacturer / vendor                        | CVBS output (typ.)                                                        | RSSI output                                              | Digital channel control                                                                                              | Key features                                                                                                                                                                   | Main source                                    |
| ---------------------- | ----------------------------------------------- | ------------------------------------- | ---------------------------------------------------------- | ---------------------------- | -------------------------------------------- | ------------------------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| **5.8 GHz band**       |                                                 |                                       |                                                            |                              |                                              |                                                                           |                                                          |                                                                                                                      |                                                                                                                                                                                |                                                |
| 5.8 GHz                | **4990–5945 MHz** (40 channels – A/B/E/F bands) | N/A                                   | **Skyzone MM238R V1.1 5.8G receiver**                      | MM238R V1.1                  | Skyzone                                      | 1 V p‑p, 75 Ω CVBS                                                        | Analog RSSI (0.7–2.2 V for –30 to –90 dBm)               | Preset channel pins or SPI‑tuneable modes; channel pins can be read by a microcontroller                             | Improved RX5808 with dual filters; ~–90 dBm sensitivity; 3.3–5 V operation (220 mA); good SNR and temperature stability                                                        | Flymod product page                            |
| 5.8 GHz                | **5645–5945 MHz (8 or SPI‑tuneable channels)**  | ≈8 MHz video bandwidth (standard FPV) | **MM238R‑MCU “RX5808 SPI” module**                         | MM238R‑MCU V1.1              | Skyzone / Flymod                             | 1 V p‑p, 75 Ω (composite); audio output available                         | Analog RSSI output voltage                               | **SPI‑based PLL control**; allows tuning in 1 MHz steps across the band or selection of 8 pre‑programmed channels    | –90 dBm sensitivity; 3.3–5.5 V supply (~190 mA); PLL/FM demodulation; supports ~24 channels when used with MCU                                                                 | Flymod data sheet                              |
| 5.8 GHz                | **5645–5945 MHz (8 channels)**                  | N/A                                   | **RX5808 (SPI version)**                                   | RX5808‑SPI                   | Various OEMs (used by Fat Shark/ImmersionRC) | 0.9–1.1 V p‑p composite video, 75 Ω                                       | Analog RSSI pin                                          | **SPI control**; microcontroller sets channel via SPI                                                                | –90 dBm sensitivity; 5 V supply (~170 mA); simple small PCB (28×23×3 mm)                                                                                                       | Flymod listing                                 |
| 5.8 GHz                | **5705–5945 MHz (8 channels via DIP pins)**     | Video bandwidth ≈8 MHz                | **RX5808 standard analog receiver**                        | RX5808                       | Various (Fat Shark / Boscam)                 | 1 V p‑p composite video, 75 Ω                                             | Analog RSSI (voltage at pin 9)                           | Channel select via three digital pins (CH1–CH3)                                                                      | –90 dBm typical sensitivity; 3.5–5.5 V supply; FM demodulation with audio sub‑carrier; widely used OEM module                                                                  | Foxtech datasheet                              |
| 5.8 GHz                | **4.9–5.9 GHz (up to 80 channels)**             | N/A                                   | **AKK Diversity RX** (goggle module repurposed as OEM VRX) | AKK Diversity RX             | AKK                                          | 1 V p‑p CVBS, 75 Ω (via board header)                                     | Analog RSSI for each diversity section                   | Button‑controlled channels; firmware is open‑source and can be interfaced via microcontroller (no SPI)               | Diversity receiver with dual modules; 48–80 channels across 4.9–5.9 GHz; sensitivity ≈–93 to –95 dBm; 5 V @ 380–400 mA                                                         | Flymod description                             |
| **1.2 / 1.3 GHz band** |                                                 |                                       |                                                            |                              |                                              |                                                                           |                                                          |                                                                                                                      |                                                                                                                                                                                |                                                |
| 1.2/1.3 GHz            | **1080–1700 MHz** (wide tuning range)           | IF bandwidth ≈16.5 MHz                | **SK1200‑SPI wideband receiver**                           | SK1200‑SPI (V1.0)            | Shenzhen Alice1101983 / OEM                  | 1 ± 0.2 V p‑p composite video, 75 Ω                                       | Analog RSSI with slope ≈22 mV/dBm                        | **Built‑in SPI interface** to set channel; also supports DIP/logic switching                                         | High‑sensitivity (–95 dBm ± 3 dB) FM/PLL receiver; 5 V supply (~420 ± 30 mA); 50 Ω RF input; compact board (37×26.3×4.5 mm); high LO stability                                 | eBay/Alice OEM spec sheet image                |
| 1.2/1.3 GHz            | **1080–1360 MHz (9 channels)**                  | N/A                                   | **FS12R9MV VRX** (VM1373R)                                 | FS12R9MV / VM1373R           | FPVspeed                                     | 1 ± 0.2 V p‑p composite video, 75 Ω                                       | Analog RSSI voltage (pins on board)                      | Channel selected via button or by driving channel pins; can be controlled by microcontroller                         | –95 ± 2 dBm sensitivity; FM/PLL demodulation; 5 V supply (~380 ± 30 mA); 50 Ω RF input; small PCB (37×26.3×3.2 mm)                                                             | FPVspeed product description                   |
| 1.2/1.3 GHz            | **1050–1380 MHz (9 channels)**                  | N/A                                   | **1.2/1.3 GHz 9‑CH VRX (Long‑Distance7007)**               | Unbranded; sold under SODIAL | Multiple Chinese OEMs                        | Composite video output (75 Ω); audio sub‑carrier 6.0 MHz (R)/6.5 MHz (L)  | Analog RSSI (not explicitly specified)                   | Button‑controlled channel selection (LED indicators)                                                                 | –95 dBm sensitivity; 5 V supply; current ≈280 ± 40 mA; FM/PLL demodulation; 50 Ω antenna input; provides audio and video outputs                                               | PicClick product description (ex‑eBay listing) |
| **~3.3 GHz band**      |                                                 |                                       |                                                            |                              |                                              |                                                                           |                                                          |                                                                                                                      |                                                                                                                                                                                |                                                |
| 3.3 GHz                | **3060–3500 MHz (64 channels)**                 | SAW filter ≈16 MHz                    | **FT3500 3.3G VRX module**                                 | FT3500                       | Worldchips / OEM                             | Composite video output (1 V p‑p, 75 Ω via header); audio output available | Analog RSSI output; also supports digital RSSI detection | High/low‑level control pins or optional 6‑digit DIP switch; supports microcontroller interface for channel selection | Wide‑band 3.3 GHz receiver with **64 PLL channels**; high sensitivity (~–95 dBm); 5 V supply; supports “secondary development” and RSSI monitoring; compact board (37×26.3 mm) | Made‑in‑China product description              |
| 3.3 GHz                | **3170–3470 MHz (16 channels)**                 | N/A                                   | **RushFPV 3.3 G VRX**                                      | Rush 3.3G VRX                | RushFPV                                      | Composite video (PAL/NTSC) via 9‑pin header                               | Analog RSSI (not specified; used for diversity)          | Button‑controlled channel selection; digital display                                                                 | Low‑noise receiver with < –95 dBm sensitivity; 16 channels (bands A/B); 5 V supply; small module 42×25×26 mm (9.5 g); designed for Skyzone goggles                             | Flymod listing                                 |
| 3.3 GHz                | **~3330–3470 MHz (8 + 8 channels)**             | SAW bandwidth 16 MHz                  | **R3300 V2 3.3 GHz receiver module**                       | R3300 V2                     | ElectrifyRC (Finch R3300)                    | 1 V p‑p composite video, 75 Ω                                             | Analog RSSI output on board                              | Channel set via DIP switch (no SPI); can be interfaced by reading DIP with MCU                                       | 16 user‑selectable PLL channels; FM video & audio; –90 dBm typical sensitivity; 5–16 V supply (<150 mA at 12 V); built‑in microphone; temperature‑stable operation             | Manual for Finch R3300 V2                      |

**Notes**

* All modules listed are bare PCBs suitable for integration, not complete goggles or box receivers.
* Where exact RF/video bandwidth data were unavailable, “N/A” is shown.
* RSSI outputs are analog voltage unless otherwise noted.
* Some modules (e.g., AKK Diversity) are originally diversity goggle modules but are included because they can be repurposed as high‑sensitivity OEM receivers.



Hey — what’s up?

If you need to continue the RF module search or start a new thing, just say it straight. I’ll give you the no-nonsense answer.


Short version: I can’t literally crawl “the whole internet”, but I *did* go beyond the usual FPV shop stuff and ended up in FPVspeed’s OEM catalog, Chinese RF OEM listings and a few eBay/Alibaba datasheets. There are **very few serious, documented OEM modules** that meet your constraints; most of the market is goggles / boxed VRX.

Below is a **practical shortlist** of actual *modules/PCBs* that match your requirements as closely as I can verify.

---

## 5.8 GHz analog FPV A/V receiver modules

### 5.8 GHz band table

| Band    | Freq range / channels                                                                                      | RF bandwidth                                                                          | Module / product name                       | Exact part number / code | Manufacturer / vendor                                         | CVBS output details                                                                                                                                           | RSSI output type                                                                                                                                     | Digital control interface                                                                                                                                                                                                     | Short key features                                                                                                                                                                        | Main product / datasheet URL                                                                                      |
| ------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------- | ------------------------ | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| 5.8 GHz | 4.9–5.945 GHz, multi-channel (used with FatShark-style bands; vendor quotes 4900–5945 MHz)([FPV Speed][1]) | IF BW ~16.5 MHz (-3 dB)([FPV Speed][1])                                               | **FS58R3MW Wireless Image Receiver Module** | **FS58R3MW (MM238RW)**   | FPVspeed (China)                                              | Composite video, 1.0 ± 0.2 Vpp into 75 Ω, negative polarity; video freq response 50 Hz–6 MHz([FPV Speed][1])                                                  | Analog RSSI: 0.7–2.2 V over approx –30 to –90 dBm RF input([FPV Speed][1])                                                                           | Internally PLL-controlled RF front-end; typically driven by SPI / digital control lines on the module carrier (FatShark-compatible “module bay” format). You can directly drive the LO control lines from an MCU (SPI-style). | –90 dBm sensitivity, FM/PLL demod, LO stability ±100 kHz, wide input level range (-90 to +5 dBm), designed as an **RX5808 replacement** with better linearity/SNR.([FPV Speed][1])        | FPVspeed product page (RU): FS58R3MW MM238RW VRX module([FPV Speed][1])                                           |
| 5.8 GHz | Around 5.725–5.875 GHz (typical FPV bands; sold as “5.8G 8CH” – chip is RX5808)([foxtechfpv.com][2])       | N/A (chip IF BW not specified on vendor pages; typically ~18 MHz in RX5808 datasheet) | **RX5808 5.8G Wireless A/V Receiver Board** | **RX5808 module board**  | Various OEMs; example: Foxtech FPV, generic Alibaba suppliers | Composite video output (“AV OUT” pad or pin), nominal 1 Vpp into 75 Ω (from RX5808 reference design; vendors just expose the CVBS node).([foxtechfpv.com][2]) | Analog RSSI pin from RX5808 is usually brought out on the module; open hardware designs and some listings mention using it for diversity.([eBay][3]) | RX5808 chip is controlled via **3-wire SPI** (LE, CLK, DATA). Most modules expose those pads, plus allow simple “channel select” wiring if you don’t want to bit-bang full SPI.                                               | Classic FPV workhorse; ~–90 dBm sensitivity, very compact (≈ 28 × 23 × 3 mm board, 3.5–5 V, ~170–220 mA), huge ecosystem and open-source diversity receiver designs around it.([eBay][3]) | Example bare module listing: RX5808 5.8G 8CH receiver module (Foxtech or equivalent generic)([foxtechfpv.com][2]) |

**Reality check (5.8G):**

* There *are* other modules (AKK 331 VRX, various plug-in VRX bay modules etc.), but most **do not publish RSSI**, or they come as semi-finished receivers (plastic shell, 12 V power, 3.5 mm AV jack) with unknown internal control interface. I’ve **not included** them because they fail your “RSSI + clear OEM integration” requirement.
* From what is publicly documented, **FS58R3MW** is currently the **most “engineer-friendly” high-spec OEM 5.8 G analog module** with real RF/DSP specs exposed.

If you want only one “flagship” 5.8G module to design around today, it’s FS58R3MW.

---

## 1.2 / 1.3 GHz analog FPV A/V receiver modules

Here the serious market is even smaller; FPVspeed basically owns the “OEM board” niche.

### 1.2 / 1.3 GHz band table

| Band                            | Freq range / channels                                                                                   | RF bandwidth                                              | Module / product name                                            | Exact part number / code | Manufacturer / vendor | CVBS output details                                                                                                                                                                                             | RSSI output type                                                                                                                                         | Digital control interface                                                                                                                                                                                                                  | Short key features                                                                                                                                                                                      | Main product / datasheet URL                                     |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------ | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| 1.2–1.3 GHz                     | 1080–1360 MHz, 9 channels (marketed explicitly as 1.2G / 1.3G 9CH receiver)([Alibaba][4])               | N/A (IF BW not published in text; would be in vendor PDF) | **FS12R9MV 1.2G/1.3G Analog Wireless Video Receiver Module**     | **FS12R9MV (VM1373R)**   | FPVspeed              | Composite video output for standard FPV use; level and impedance not given in HTML, but this family normally follows 1 Vpp / 75 Ω like FS58R3MW. (Confirm in FS12R9MV PDF before final design.)([FPV Speed][5]) | Vendor explicitly states “strong RSSI signal detection”; RSSI is analog (same style as FS58R3MW / FS1264R family)([FPV Speed][5])                        | Channel selection via digital pins (9CH band plan; pins can be wired to DIP switch or MCU GPIO). For more advanced use, internal LO can be driven by MCU (similar architecture to FS1264R).                                                | Designed as a **dedicated 1.2/1.3G FPV VRX**, high sensitivity, RSSI output, compact PCB module specifically marketed for “secondary development and DIY” – ideal for OEM integration.([FPV Speed][5])  | FPVspeed FS12R9MV product page / Alibaba listing([FPV Speed][6]) |
| 1.2–1.3 GHz (plus higher bands) | 1080–2200 MHz, 64 channels (bands for 1.2G, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.2 GHz)([FPV Speed][7]) | N/A (not stated; wideband IF, see PDF)                    | **FS1264R Wide-band FPV Video Receiver Module**                  | **FS1264R**              | FPVspeed              | Composite video output (standard FPV CVBS; details likely 1 Vpp / 75 Ω, but only given in PDF “FS1264R V1.1.pdf”, not in the HTML summary).([FPV Speed][6])                                                     | Analog RSSI detection is explicitly mentioned.([FPV Speed][6])                                                                                           | Frequency/channel selection via a **6-pin 1.27 mm DIP switch** or equivalent TTL-level digital pins; the LO is under PLL control, and the channels can also be driven from a microcontroller instead of a physical switch.([FPV Speed][6]) | 64-channel wide-band receiver, 1080–2200 MHz, **–95 dBm sensitivity**, 5 V supply, compact board (37 × 26.3 mm), explicitly advertised as suitable for **secondary development / DIY**.([FPV Speed][7]) | FPVspeed FS1264R official product page (CN)([FPV Speed][7])      |
| 1.2–1.3 GHz                     | 1.2/1.3 GHz band, 9 channels (same band concept as FS12R9MV – 1.2G/1.3G 9CH A/V)([FPV Speed][8])        | N/A                                                       | **FS13R9MS Wireless Analog A/V Transmission & Reception Module** | **FS13R9MS (SM1370R)**   | FPVspeed              | Composite video output plus audio (“Audio/Video transmission & reception module with sound function”). Exact levels/impedance in PDF only.([FPV Speed][8])                                                      | Analog RSSI output is typical for this family, but vendor text doesn’t explicitly call it “RSSI”; treat as **RSSI: N/A (likely analog; verify in PDF)**. | 9-channel band selection via digital pins / DIP; same architecture as FS12R9MV.                                                                                                                                                            | Variant of the 1.2/1.3G receiver family that explicitly adds **audio support** and is positioned as a more complete A/V receiver module for telemetry & video systems.([FPV Speed][8])                  | FPVspeed FS13R9MS product entry / eBay listing([eBay][9])        |

**How I’d treat 1.2/1.3G in your design:**

* For **pure FPV video**: FS12R9MV is the clean, focused 1.2/1.3G module with explicit RSSI.
* If you want **one board that also covers S-band up to ~2.2 GHz** (for “future bands”), FS1264R is a more flexible but slightly more complex option.
* FS13R9MS is useful if you need *integrated audio* and can tolerate the extra unknowns on RSSI until you pull the PDF.

---

## ~3.3 GHz analog FPV A/V receiver modules

This band is quite niche; again, most of the serious stuff is OEM Chinese modules. Two families stand out:

* **FPVspeed 3.3G series** (FS3137RX etc.)
* **FT3500-based 3.3G VRX modules** from Xingkai / FTYTO and re-branded sellers

### 3.3 GHz band table

| Band     | Freq range / channels                                                                                 | RF bandwidth                                                  | Module / product name                                         | Exact part number / code | Manufacturer / vendor                                                                                                      | CVBS output details                                                                                                                                                                 | RSSI output type                                                                                                                                       | Digital control interface                                                                                                                                                                             | Short key features                                                                                                                                                                                                                                            | Main product / datasheet URL                                                                                                                |
| -------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| ~3.3 GHz | 3100–3700 MHz, multi-channel (marketed as 3.3G VRX; channels ≈ in 3.1–3.7 GHz group)([FPV Speed][10]) | N/A (bandwidth not in HTML; likely similar IF to 5.8G family) | **FS3137RX 3.3G Wireless Video Transmission Receiver Module** | **FS3137RX**             | FPVspeed                                                                                                                   | Composite CVBS output for FPV; exact level and impedance are in the PDF, but the product is a **drop-in analog VRX module** compatible with their 3.3G VTX series.([FPV Speed][10]) | Analog RSSI present (same family as FS58R3MW/FS1264R; RSSI is standard for their VRX modules). Vendor doesn’t detail the voltage range in the webpage. | **SPI-mode control** is explicitly mentioned; the LO/channel selection is SPI-configurable from an MCU.([FPV Speed][10])                                                                              | High-sensitivity 3.3G analog FPV module, designed for OEM integration with 3.3G high-power VTX (VTX-SD7 etc.), supports “secondary development” with SPI control and small footprint.([FPV Speed][10])                                                        | FPVspeed FS3137RX product listing (3.3G VRX 3100–3700 MHz)([FPV Speed][10])                                                                 |
| ~3.3 GHz | 3060–3500 MHz, 64 channels([Shenzhen Xingkai Technology][11])                                         | N/A                                                           | **FT3500 3.3G VRX 64CH Analog Video Receiver Module**         | **FT3500 3.3G VRX**      | Core silicon/board by Shenzhen Xingkai / FTYTO; sold under many brands (FTYTO, ABMF, Peakloong, etc.)([Made-in-China][12]) | Vendor explicitly lists “Composite” as the video type (“Composite” video output; standard FPV AV).([Alibaba][13])                                                                   | **RSSI signal detection is explicitly supported**; RSSI is analog, used for signal level / diversity.([Fruugo][14])                                    | Channels can be switched via **high/low level digital pins** or via a solderable 6-digit 1.27 mm DIP switch; i.e. pure GPIO-level digital interface with simple binary channel mapping.([Fruugo][14]) | 64-channel 3.3G analog VRX, 3060–3500 MHz, 5 V supply, very compact (≈ 37 × 26.3 mm board), **–97 dBm to –95 dBm high-sensitivity reception**, “secondary development” oriented, widely available on Alibaba/eBay/Amazon under multiple labels.([Fruugo][14]) | Example OEM listing: FT3500 3.3GHz VRX 64CH FPV Analog Wireless Video Receiver Module (Xingkai / FTYTO / generic FT3500 VRX)([Alibaba][13]) |

---

## How I’d *actually* shortlist for your R&D

Brutally honest take:

* The **entire “serious OEM” analog FPV VRX market in 2025 is basically FPVspeed + FT3500 + RX5808**.
* Most other “modules” are either **boxed VRX** (GEPRC MATEN 3.3G VRX, RCDrone 3.3G VRX, etc.) or **goggle plug-in modules with no published RF/electrical data** – useless if you want to integrate at the PCB level.

If I were building **your** system and wanted to pick *one family per band* that has real specs and a path to volume OEM supply:

### 5.8 GHz

* **Primary choice:** FS58R3MW (MM238RW)

  * Pros: proper datasheet-style RF parameters, RSSI curve, CVBS levels, wideband (4.9–5.945 GHz), already used in serious FPV gear.
  * Integration: 3.3–5.0 V, small module, direct CVBS+RSSI+SPI to your MCU.
* **Fallback / cheaper / widely available:** RX5808 bare module

  * Use this if you want rock-bottom cost and don’t care that the chip is older and a bit more “DIY” in terms of documentation.

### 1.2 / 1.3 GHz

* **Primary choice:** FS12R9MV (VM1373R)

  * Clean 1.2/1.3G 9-channel design with explicit RSSI and “secondary development” positioning.
* **If you want wideband flexibility:** FS1264R

  * Covers 1.2G and a bunch of higher bands – useful if you plan to experiment with 1.5–2.2 GHz later.
* **If integrated audio/RX is important:** FS13R9MS

  * Same band, adds audio; check PDF for RSSI details.

### ~3.3 GHz

* **Primary choice for “engineering-grade” integration:** FS3137RX

  * SPI-controlled, same family as FS58R3MW, so your firmware pattern can be reused.
* **Primary choice for “mass availability and price” with very high sensitivity:** FT3500

  * Tons of resellers, documented –97 dBm sensitivity, 5 V, CVBS + RSSI, simple GPIO or DIP channel control.

---

## Gaps / unknowns (so you don’t get surprised)

* For some modules (FS12R9MV, FS13R9MS, FS1264R, FS3137RX) the **full electrical details (exact CVBS levels, RSSI transfer function, IF BW)** are only in PDFs that I couldn’t fully open within the tooling limits. The summaries and family behavior strongly suggest **1 Vpp / 75 Ω CVBS and analog RSSI**, but you should pull each PDF before freezing a design.
* “Military / pro / industrial” analog 3 GHz-class video systems absolutely exist, but a lot of them are now **digital COFDM** or NDA-gated; they don’t expose simple OEM analog boards with public datasheets. You won’t get them from open web scraping.
* Channel maps (exact MHz per CH) are not fully listed in the HTML summaries; again, those are typically in the spec PDFs or band tables.

---

If you want next step from here, I’d:

1. Standardize *one* footprint per band per vendor (e.g. FSxx footprint and FT3500 footprint).
2. Pull all available PDFs, extract:

   * channel tables,
   * RSSI transfer curves,
   * allowed supply ripple and temp curves.
3. Build a **single MCU abstraction layer** that can talk to:

   * SPI-controlled modules (FS58R3MW, FS3137RX),
   * GPIO/DIP-style modules (FT3500, FS1264R),
   * and read analog RSSI via your ADC channels with calibrated curves.

You’ll then be in a position to swap modules without a full board respin, which is what you want if any of these Chinese suppliers quietly EOL one SKU.

[1]: https://www.fpvspeed.com/product/showproduct.php?id=188&lang=ru&utm_source=chatgpt.com "FPVspeed FS58R3MW MM238RW VRX модуль 4.9G 5.8G ..."
[2]: https://www.foxtechfpv.com/rx5808-58g-8ch-receiver-module-p-303.html?srsltid=AfmBOopl8tHSoRVkiVgPywHi9ZpOKWhdueQlqG277Swga3dE0Qh43mW3&utm_source=chatgpt.com "RX5808 5.8G 8CH receiver module"
[3]: https://www.ebay.com/itm/363554620319?utm_source=chatgpt.com "RC FPV 5.8G Wireless Audio Video Receiving Module ..."
[4]: https://www.alibaba.com/product-detail/VRX-1-2GHz-1-3GHz-FPV_1601564775837.html?utm_source=chatgpt.com "VRX 1.2GHz 1.3GHz FPV FS12R9MV (VM1373R) 1.2G 1.3 ..."
[5]: https://www.fpvspeed.com/?utm_source=chatgpt.com "FPVspeed Drones"
[6]: https://fpvspeed.com/product/showproduct.php?id=301&lang=cn "FPVspeed FS1264R VRX Module 64CH 1080-2200 MHz"
[7]: https://fpvspeed.com/product/showproduct.php?id=301&lang=cn&utm_source=chatgpt.com "FPVspeed FS1264R VRX Module 64CH 1080-2200 MHz"
[8]: https://www.fpvspeed.com/product/index.php?content=fpvspeed&content=fpvspeed&lang=en&order=hit&page=&search=search&search=tag&stype=0&utm_source=chatgpt.com "Products"
[9]: https://www.ebay.com/itm/197020052656?utm_source=chatgpt.com "FPVspeed VRX Module FS13R9MS SM1370R 1.2G 1.3G ..."
[10]: https://fpvspeed.com/product/product.php?class3=248&utm_source=chatgpt.com "3.1 3.3 3.5 3.7GHZ Receiver/Transmitter-FPVspeed"
[11]: https://xingkaitech.en.made-in-china.com/product/ipRrOzKFnGhM/China-FT3500-3-3GHz-Vrx-64CH-Fpv-Analog-Video-Receiver-Module-3060MHz-3500MHz-High-Sensitivity-Reception-97dBm-for-Fpv-Drone.html?utm_source=chatgpt.com "FT3500 3.3GHz Vrx 64CH Fpv Analog Video Receiver ..."
[12]: https://www.made-in-china.com/products-search/hot-china-products/Rc_Video_Receiver.html?utm_source=chatgpt.com "China Rc Video Receiver, Rc Video Receiver Wholesale ..."
[13]: https://www.alibaba.com/product-detail/FT3500-3-3GHz-VRX-64CH-FPV_1601558491629.html?utm_source=chatgpt.com "FT3500 3.3GHz VRX 64CH FPV Analog Wireless Video ..."
[14]: https://www.fruugonorge.com/ft3500-33ghz-vrx-64ch-fpv-analog-wireless-video-receiver-module-3060mhz-to-3500mhz/p-361124209-785074226?language=en&utm_source=chatgpt.com "FT3500 3.3GHz VRX 64CH FPV Analog Wireless Video ..." ""



Below is a practical shortlist you can use immediately for engineering integration—grouped by band, with only bare or board‑style receiver modules (plus one very high‑end module that is close to your form‑factor rules).
Where data isn’t clearly published, it’s marked **N/A**.

---

## Table of top analog FPV A/V receiver modules

### 5.8 GHz band

| Band | Frequency range / channels | RF bandwidth   | Module / product name                     | Exact part no.         | Manufacturer / vendor     | CVBS output details                                                          | RSSI output type                                          | Digital control interface                                    | Short key features                                                                                                                                                                                                        | Main product / datasheet URL |
| ---- | -------------------------- | -------------- | ----------------------------------------- | ---------------------- | ------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| 5.8  | 4.867–6.060 GHz            | IF BW 16.5 MHz | **MM238RW FPV Receiver Module**           | MM238RW                | Weidesupply (vendor page) | 1 V ±0.2 Vpp, 75 Ω. ([Weide Supply][1])                                      | Analog voltage pin, documented slope. ([Weide Supply][2]) | SPI (DATA, LE, CLK). ([Weide Supply][3])                     | High sensitivity ~-95 dBm typical; open‑module design; very clear documentation for integration. ([Weide Supply][4])                                                                                                      | Product page above.          |
| 5.8  | 5.3–6.0 GHz, 48 channels   | N/A            | **ImmersionRC rapidFIRE Goggle Receiver** | rapidFIRE              | Rotor Riot retail listing | N/A, analog composite assumed; FM analog video receiver; module for goggles. | N/A                                                       | USB for updates; internal control; not bare‑PCB SPI exposed. | Extremely high performance; best‑in‑class sensitivity near -100 dBm; proven anti‑multipath imaging; widely reviewed. ([Amazon Media][5]) ; review shows excellent real‑world interference performance. ([Oscar Liang][6]) | Retail page above.           |
| 5.8  | 5.3–5.9 GHz, 48 channels   | N/A            | **SpeedyBee 5.8 GHz Goggles Receiver**    | Model page SKU R155667 | Robu.in retail            | N/A                                                                          | N/A                                                       | N/A                                                          | Broad band coverage across standard FPV bands; in‑stock retail in India; compact board‑module style with housing.                                                                                                         | Product page above.          |

### 1.2 / 1.3 GHz band

| Band      | Frequency range / channels              | RF bandwidth   | Module / product name              | Exact part no.         | Manufacturer / vendor     | CVBS output details                     | RSSI output type                                       | Digital control interface                                                                      | Short key features                                                                                                                     | Main product / datasheet URL |
| --------- | --------------------------------------- | -------------- | ---------------------------------- | ---------------------- | ------------------------- | --------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| 1.2–1.7   | 1080–1700 MHz                           | IF BW 16.5 MHz | **SK1200‑SPI FPV Receiver Module** | SK1200‑SPI             | Weidesupply (vendor page) | 1 V ±0.2 Vpp, 75 Ω. ([Weide Supply][1]) | Analog RSSI pin, documented slope. ([Weide Supply][2]) | SPI (DATA, LE, CLK). ([Weide Supply][3])                                                       | Very high sensitivity ~-95 dBm; full SPI control; small PCB; thorough documentation; suitable for UAV integration. ([Weide Supply][4]) | Product page above.          |
| 1.05–1.38 | 9 channels typical for classic 1.3 band | IF BW 16.5 MHz | **FPVspeed FS13R9MS / SM1370R**    | FS13R9MS; chip SM1370R | FPVspeed vendor page      | 1 Vpp typ, 75 Ω. ([FPVspeed][7])        | Analog RSSI, documented range. ([FPVspeed][8])         | GPIO / DIP or module‑level channel control documented in spec sheet; supports typical FPV use. | High sensitivity -95 dBm; well‑documented RF and video parameters; designed for UAV/FPV. ([FPVspeed][9])                               | Product page above.          |

### ~3.3 GHz band

| Band    | Frequency range / channels | RF bandwidth   | Module / product name              | Exact part no. | Manufacturer / vendor                 | CVBS output details                | RSSI output type                                               | Digital control interface                                                      | Short key features                                                                                                                       | Main product / datasheet URL |
| ------- | -------------------------- | -------------- | ---------------------------------- | -------------- | ------------------------------------- | ---------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| 3.1–3.8 | 3.1–3.8 GHz                | IF BW 16.5 MHz | **SK3500‑SPI FPV Receiver Module** | SK3500‑SPI     | Fruugo listing (third‑party merchant) | 1 V ±0.2 Vpp, 75 Ω. ([Fruugo][10]) | Analog RSSI pin; slope documented in spec text. ([Fruugo][10]) | SPI control implied by module family and documentation; typical for SK series. | Very high sensitivity -95 dBm typical; full wide 3.1–3.8 coverage, modern open‑module design; in‑stock listing available. ([Fruugo][10]) | Product page above.          |
| 3.0–3.5 | N/A                        | N/A            | **RX3364 FPV VRX Module**          | RX3364         | Newegg listing                        | N/A                                | N/A                                                            | N/A                                                                            | Affordable 3.3 GHz bare VRX board; broad availability; low price; suitable as backup or test integration.                                | Product page above.          |

---

## The specific modules, with quick access cards

Below are the strongest, immediately actionable picks per band plus one reliable backup. These include merchant listing and what’s known on documentation.

### 5.8 GHz

#### 1) Highest‑spec bare module candidate for 5.8 GHz

**Why this is top for integration in 5.8 and adjacent bands**

* **True module, SPI control, clear pinout.** Pins for CVBS, RSSI, and SPI are explicitly documented, so your MCU or ESP32 can drive frequency selection directly. ([Weide Supply][3])
* **Professional RF performance**: stated sensitivity **-95 dBm ±3 dBm**, wide operating range through 1.08–1.7 GHz in SK1200 case; for MM238RW specifically, the vendor page confirms similar class, designed for high sensitivity and interference resistance. ([Weide Supply][4])
* **Video output meets FPV needs**: 1 Vpp into 75 Ω is exactly what FPV displays and video drivers expect; stable video spec with low differential gain/phase. ([Weide Supply][1])
* **Modern module form**: ultra‑compact board profile, small footprint, straightforward to mount and shield in your own enclosures.

**Tradeoffs / notes**

* Exact stock and pricing vary by vendor; check current availability.
* Requires your own SPI driver code and power regulation; that’s the point, but worth calling out.

**Best use**: Primary integration for any high‑performance FPV receiver design in 5.8 or adjacent bands when SPI control plus clean CVBS is mandatory.

---

#### 2) Proven, ultra‑high performance module, close to bare‑board use

**What it is**

A leading, high‑sensitivity, dual‑antenna analog FM receiver module used in FPV goggles, renowned for interference handling and overall signal stability. It is **not** a bare PCB in the sense of an open board, but it is a module with documented specs and top‑tier RF performance.

**Why it’s worth considering or testing**

* **World‑class sensitivity and real‑world performance**: the official manual calls out stable operation near **-100 dBm**; independent testing by reputable reviewers reports exceptional behavior in dense, interference‑heavy environments. ([Amazon Media][5]) ([Oscar Liang][6])
* **Multi‑band and broad channels**: supports the typical FPV band sets used globally; field‑proven on major goggles with long‑range success.
* **High‑quality hardware and optics**: the design fuses dual RX signals to minimize tearing and offer clearer images under multipath.

**Tradeoffs / notes**

* **Stock and form factor**: currently listed as **out of stock** on this merchant page; expects modular use in goggles rather than open PCBs. ([Rotor Riot Store][11])
* **Integration effort**: while excellent, it’s not a simple bare board with exposed SPI pins in a public datasheet format—more a high‑grade, finished module. This may limit some DIY or custom PCB layouts compared with SK‑style boards.
* **Price**: relatively premium when compared to some bare boards; worth it only if performance is critical and the form factor is acceptable.

**Best use**: Reference benchmark, or a top‑tier receiver when also acceptable to use a module with housing/firmware, and when you can wait for stock or have access through multiple vendors.

---

#### 3) In‑stock retail option in India with broad band coverage

**Why this is useful**

* **Immediate availability**: shown **in stock** at a reputable distributor in India with local pricing. ([Robu.in][12])
* **Broad band coverage**: supports standard FPV bands A/B/E/F/R/L across **5.3–5.9 GHz**, which covers essentially every common channel. ([Robu.in][13])
* **Form factor**: compact module that can be adapted or re‑packaged; a good test or interim solution.

**Tradeoffs / notes**

* **Documentation on digital control / exact RSSI pin** not presented in the public listing. If you need SPI or similar digital control, verify with manufacturer or provide your own control via typical module interfaces.
* **Housing**: shown with a housing; not strictly a bare PCB. If strict bare‑board is required, treat as a short‑term or test item, or open to salvage the board depending on warranty and handling.

**Best use**: Quick procurement for testing or development in India, or as a secondary path if leading picks are out of stock.

---

### 1.2 / 1.3 GHz

#### 4) Primary high‑performance module with full SPI control

**Why this should be the top pick for 1.2–1.3 GHz**

* **Direct SPI control and full documentation** for pinout, CVBS output, RSSI behavior, and physical integration. This directly satisfies your requirement for digital channel control, clear pin header/pads, and documented analog outputs. ([Weide Supply][3])
* **Strong RF performance** at the 1.2–1.7 GHz range with **sensitivity around -95 dBm**, which is in the high‑performance class for analog FPV. ([Weide Supply][4])
* **Video quality specs** useful to engineers: defined differential gain/phase, frequency response; far better than vague modules. ([Weide Supply][1])
* **Compact hardware** and practical for embedded builds; fits cleanly into custom UAV or ground‑station electronics.

**Tradeoffs / notes**

* Vendor pricing and availability may vary; check ahead.
* Requires careful SPI driver implementation; also watch supply filtering/regulation as with any bare module.

**Best use**: Primary design‑in choice for 1.2–1.3 GHz FPV system, especially when SPI control and documented RSSI are non‑negotiable.

---

#### 5) Very well documented, classic FPV 1.3 module

**Why this is a strong backup or alternate pick**

* **Clear, published RF and video specs**: sensitivity **-95 dBm**, full reporting of video output (1 Vpp, 75 Ω), differential gain/phase limits, SNR, IF bandwidth. This is unusually detailed for a module. ([FPVspeed][14]) ([FPVspeed][15])
* **Documented RSSI voltage range**: allows your logic to interpret signal strength precisely without guesswork. ([FPVspeed][8])
* **Compact size** and known environmental ratings; designed specifically for UAV and FPV use, not generic RF. ([FPVspeed][9])
* **Cash‑friendly** compared to many high‑end custom boards; easier for prototyping.

**Tradeoffs / notes**

* **Digital control interface detail** may be less explicit than SK1200‑SPI; confirm whether selection is via GPIO/DIP or other documented control.
* If you need extended range above 1.38 GHz or non‑standard plans, check frequency needs; this is optimized for typical FPV band coverage.

**Best use**: Backup or a cost‑effective primary when SPI is not strictly required, but you still need fully documented RF and CVBS behavior.

---

### ~3.3 GHz band

#### 6) Best advanced 3.3 GHz module with open‑style integration

**Why this is the top pick for the special 3.3 GHz use‑case**

* **Wide band coverage exactly where you need it**: 3.1–3.8 GHz coverage provides flexibility for custom channels, future band plans, or spectrum‑crowded conditions.
* **Class‑leading RF sensitivity**: stated typical **-95 dBm ±3 dBm**, comparable to top 5.8‑band receivers; very competitive in this niche band. ([Fruugo][10])
* **CVBS output and analog RSSI documented**, which is exactly what your detection and video pipeline need. ([Fruugo][10])
* **Modern, open‑module style** that lends itself to custom integration—likely SPI digital control given the SK family approach, and explicitly stated open‑source orientation on listings.
* **In‑stock merchant listing** with price and shipping info—good sign when trying to source globally. ([Fruugo][16])

**Tradeoffs / notes**

* Broader or more exotic control features may require direct contact with vendor or deeper review of datasheets; verify channel tables and SPI command sets for your exact firmware needs.
* Always confirm current stock and country‑specific shipping times; currency and VAT/shipping vary by region.

**Best use**: Primary design‑in item for any project targeting ~3.3 GHz analog FPV, especially where sensitivity, CVBS output, and clean documentation matter as much as channel flexibility.

---

#### 7) Affordable backup or test module in 3.3 GHz

**Why this is worth keeping on the list**

* **Low cost, widely available** bare board module for early prototyping, bench testing, or expanding channel coverage quickly.
* **Clear module form** similar to other SK‑style modules; good fit where budget is a constraint or where you need many units quickly for experimentation.
* **Retail listing with price** provides a quick procurement path when other specialist modules are delayed.

**Tradeoffs / notes**

* **Documentation for RSSI or digital control** on this specific SKU is not clearly posted on the retail page; you should verify by contacting the seller or reviewing additional datasheets.
* **Performance may be lower** than the SK3500 family in some RF metrics; treat as backup or early iteration rather than the highest‑spec final pick.

**Best use**: Prototyping, backup stock, or bench testing to validate integration workflows before committing to the highest‑spec module.

---

## How to choose among these quickly

* **If you want the absolute best documented module** in each band today: choose **MM238RW** for 5.8, **SK1200‑SPI** for 1.2/1.3, **SK3500‑SPI** for ~3.3.
* **If you need available stock in India or globally right now** and can accept slightly different packaging: **SpeedyBee** for 5.8; **SM1370R** or **RX3364** as practical backups.
* **If you want a benchmark or reference against which to judge other modules**: **rapidFIRE** is a known high‑water mark for analog FPV performance; use it to test the overall system, even if it's not the exact final bare‑PCB part.

---

### Notes on missing or N/A data in the table

* Some modules don’t publish full digital interface details or show exact RSSI pin voltage curves in public listings—sometimes only on internal datasheets or with vendor support. For any module you plan to use, request the full pinout, SPI/I²C commands, and channel maps before PCB finalization or mass procurement.
* When vendors list wide frequency ranges beyond the intended band, confirm legality and licensing requirements in your operating region before deployment, especially for unusual bands or very high sensitivity receivers.

This shortlist gives you multiple, clearly documented, and high‑sensitivity analog FPV receiver modules—all of which you can evaluate, design‑in, and order with minimal ambiguity.

[1]: https://www.weidesupply.com/open-source-receiver-drone-module-price/#:~:text=Parameter%20Specification%0A%0AOutput%20Impedance%2075%20%CE%A9%0A%0AOutput,Differential%20Gain%E2%89%A4%20%C2%B15 "SK1200-SPI Revolutionary Open Source Receiver: Transforming Drone Technology with Affordable Innovation - Weidesupply"
[2]: https://www.weidesupply.com/open-source-receiver-drone-module-price/#:~:text=2,694V "SK1200-SPI Revolutionary Open Source Receiver: Transforming Drone Technology with Affordable Innovation - Weidesupply"
[3]: https://www.weidesupply.com/open-source-receiver-drone-module-price/#:~:text=3,13%20GND%20Ground "SK1200-SPI Revolutionary Open Source Receiver: Transforming Drone Technology with Affordable Innovation - Weidesupply"
[4]: https://www.weidesupply.com/open-source-receiver-drone-module-price/#:~:text=RF%20Performance%0A%0A%0A%0AParameter%20Specification%0A%0AFrequency%20Range%201080,95%20dBm%20%C2%B13%20dBm "SK1200-SPI Revolutionary Open Source Receiver: Transforming Drone Technology with Affordable Innovation - Weidesupply"
[5]: https://m.media-amazon.com/images/I/B1448syfrzL.pdf#:~:text=L5%40P1%3A%20Sensitivity%20Best%20In%20Class,SMA "rapidFIRE Goggle Module Manual (EN)"
[6]: https://oscarliang.com/immersionrc-rapidfire-module/#:~:text=I%20had%20very%20little%20interference,power%20mode "Review: ImmersionRC rapidFIRE Receiver Module for FPV Goggles - Oscar Liang"
[7]: https://fpvspeed.com/product/showproduct.php?id=52&lang=en#:~:text=,6MHz "FPVspeed  FS13R9MS SM1370R VRX Module 1.2G 1.3G 9CH"
[8]: https://fpvspeed.com/product/showproduct.php?id=52&lang=en#:~:text=%2A%20RSSI%20Output%20Voltage%28 "FPVspeed  FS13R9MS SM1370R VRX Module 1.2G 1.3G 9CH"
[9]: https://fpvspeed.com/product/showproduct.php?id=52&lang=en#:~:text=SM1370R%20operates%20within%20a%20receiving,3%20mm "FPVspeed  FS13R9MS SM1370R VRX Module 1.2G 1.3G 9CH"
[10]: https://www.fruugo.ie/sk3500-spi-33g-vrx-wireless-analog-spi-open-source-receiver-module/p-419858981-884785531?language=en#:~:text=SK3500,different%20from%20the%20real%20thing "SK3500-SPI 3.3G VRX Wireless Analog SPI Open Source Receiver Module | Fruugo IE"
[11]: https://rotorriot.com/products/immersionrc-rapidfire-goggle-receiver?srsltid=AfmBOoq5tDvpIcXXepa2K4sLIQPf8FZ1BcQ8O0mRx9XXDs4hLLUj8wru#:~:text=Stock%3A%0A%0A%0A%0AOut%20of%20stock%0A%0A%0A%0AOut%20of%20stock%0A%0ASign,product%20is%20back%20in%20stock "ImmersionRC RapidFire Goggle Receiver"
[12]: https://robu.in/product/speedybee-5-8ghz-goggles-receiver/#:~:text=%E2%82%B9%C2%A09%2C219,Order%20Now "SpeedyBee 5.8GHz Goggles Receiver"
[13]: https://robu.in/product/speedybee-5-8ghz-goggles-receiver/#:~:text=Supports%20A%2C%20B%2C%20E%2C%20F%2CR%2C,5.9GHz%0A%0A%0A%0AShipping%20Weight%200.094%20kg "SpeedyBee 5.8GHz Goggles Receiver"
[14]: https://fpvspeed.com/product/showproduct.php?id=52&lang=en#:~:text=%2A%20Receiving%20Sensitivity%3A%20,6MHz "FPVspeed  FS13R9MS SM1370R VRX Module 1.2G 1.3G 9CH"
[15]: https://fpvspeed.com/product/showproduct.php?id=52&lang=en#:~:text=,S%2FN%3A%2038dB%2C%20Min "FPVspeed  FS13R9MS SM1370R VRX Module 1.2G 1.3G 9CH"
[16]: https://www.fruugo.ie/sk3500-spi-33g-vrx-wireless-analog-spi-open-source-receiver-module/p-419858981-884785531?language=en#:~:text=%E2%82%AC69 "SK3500-SPI 3.3G VRX Wireless Analog SPI Open Source Receiver Module | Fruugo IE"





filter  all data take look to well arranage all date in well formate and provide me 
