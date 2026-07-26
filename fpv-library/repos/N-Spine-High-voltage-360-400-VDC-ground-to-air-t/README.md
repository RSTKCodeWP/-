# Tethered 10″ FPV Drone — complete build report (100 m prototype → 200 m)

I’m not going to sugarcoat this: a 10″ quad on a 4-in-1 **80 A / 6 S ESC** is hungry. Pushing **low voltage** up a long tether is wasted heat. The way this actually works at 100–200 m is a **high-voltage DC bus on the tether**, a **lightweight HV→LV DC/DC on the airframe**, and **single-mode fiber** for data. Here’s the plan that closes electrically and mechanically—with sources.

---

## 1) Cable we’re standardizing on (and why)

We evaluated GORE’s hybrid tethers that combine **2 power conductors + 1 single-mode fiber** (your “3-wire” constraint). Published characteristics for the two relevant part numbers (Table 2 of the datasheet):

| Gore PN     | Power pair     | Fiber                       |         OD |          Weight |       Max DC R (one conductor) |
| ----------- | -------------- | --------------------------- | ---------: | --------------: | -----------------------------: |
| **RCN9168** | 24 AWG (19/36) | 8/125 µm, **900 µm** buffer | **2.3 mm** | **10.29 kg/km** |             **23.6 Ω/1000 ft** |
| **RCN9166** | 20 AWG (19/32) | 8/125 µm, **900 µm** buffer | **2.9 mm** | **17.89 kg/km** | **9.1 Ω/1000 ft**. ([Gore][1]) |

Gore’s jacket is abrasion-resistant, weather-proof, and the cable family is **~20% smaller/lower-weight** than standard nylon—helps reel life and handling. ([Gore][1])

### What that means at 200 m (round-trip math)

Convert resistance to Ω/m:

* 24 AWG: 23.6 Ω/1000 ft → **0.0774 Ω/m**
* 20 AWG: 9.1 Ω/1000 ft → **0.0299 Ω/m**

Pair resistance for 200 m is length **out + back = 400 m**:

* **RCN9168**: 0.0774 × 400 ≈ **30.97 Ω**
* **RCN9166**: 0.0299 × 400 ≈ **11.96 Ω**

If the airframe DC/DC draws ~**3.5 A** from a ~**380–400 V** bus (~1.3 kW at ≈92%):

| Cable       |              ΔV at 3.5 A |                                I²R loss |
| ----------- | -----------------------: | --------------------------------------: |
| **RCN9168** |  3.5 × 30.97 ≈ **108 V** | 3.5² × 30.97 ≈ **379 W** (deal-breaker) |
| **RCN9166** | 3.5 × 11.96 ≈ **41.9 V** |    3.5² × 11.96 ≈ **147 W** (tolerable) |

**Decision:**

* **100 m prototype:** either cable works (RCN9168 is lighter).
* **200 m goal:** **RCN9166 (20 AWG) is mandatory** to keep drop and losses in bounds. (All values from the GORE datasheet.) ([Gore][1])

**Tether mass at 200 m:**
RCN9168 ≈ **2.06 kg**; RCN9166 ≈ **3.58 kg** (from 10.29 & 17.89 kg/km figures). ([Gore][1])

---

## 2) System architecture that actually closes

```
230 VAC mains
  → RCCB/MCB → EMI line filter
  → PFC front-end → regulated ~360 VDC HV bus (ground)
  → Tether (Gore RCN9166: +HV, –HV, single-mode fiber)
  → Airframe: HV→LV bus converter (≈384→24 V)
  → 6S rail to 4-in-1 80A ESC + avionics
  → Data: 1000BASE-LX (1310 nm) SFP over the same SMF
```

* **Ground HV source:** **TDK-Lambda PF-A** PFC modules convert AC→**regulated 360 VDC**. Models: **PF500A-360** (504–756 W) and **PF1000A-360** (1008–1512 W). Can parallel for more power. ([TDK Product][2])
* **Airframe DC/DC (lightweight):** **Vicor BCM6123 (K=1/16)** runs from **260–410 VDC** primary and outputs an isolated, ratiometric **~24 V** secondary, **up to 62.5 A**, in a **61 × 25 × 7 mm, ~41 g** package—this is why it’s used in UAV bus architectures. ([Vicorpower][3])
* **Heavier fallback (still valid):** **TDK-Lambda PH1200A280-24**, **200–425 VDC in → 24 V / 50 A**, 1.2 kW. ([mouser.com][4])
* **Data over fiber:** Use **1000BASE-LX SFPs (1310 nm, 10 km on 9/125 SMF)** and tiny SFP media converters (e.g., TP-Link **MC220L**). LX matches Gore’s **single-mode** fiber. ([img-en.fs.com][5])

---

## 3) Why “24 V, 9 A SMPS at ground” won’t fly

At 24 V over 200 m, even moderate current means catastrophic I²R losses. The **PF-A → 360 VDC** bus exists to push power with sensible current; at 380 V you’re already seeing ~150 W line loss on 20 AWG at 3.5 A. Low-voltage over long tether = heat and voltage sag. ([TDK Product][2])

---

## 4) Step-by-step build plan

### Phase-A (10 m bench)

* AC → **PF500A-360** to produce ~360 VDC (≤500 W). ([TDK Product][2])
* 10 m of **RCN9166** (or 9168) with temporary ends. ([Gore][1])
* Airframe plate with **BCM6123 (384→24 V)** on a heatsink; drive a 0–800 W dummy load and log temps. ([Vicorpower][3])
* Fiber link using **1000BASE-LX** SFPs and an **MC220L** media converter. ([img-en.fs.com][5])

### Phase-B (100 m prototype)

* Move to **100 m RCN9166** on a manual reel. Add **ideal-diode/inrush** at both ends (**LM5050-2**, **LTC4359**). ([Texas Instruments][6])
* Integrate a small **6 S buffer pack** via ORing so ground sags don’t desync the ESC. (Use the OR-FET controllers above.) ([Texas Instruments][6])
* Flight tests ≤ 800 W, record tether temperature and airframe voltage.

### Phase-C (200 m)

* Upgrade ground power to **PF1000A-360** class (≥1 kW), or parallel PF-A modules. ([TDK Product][2])
* Add a **FORJ** (fiber-optic rotary joint) and suitable power slip-ring for a motorized reel. ([spinner-group.com][7])
* Verify sustained “climb + wind hold” load, BCM thermal headroom. ([Vicorpower][3])

---

## 5) Bill of Materials (core, with sources)

**Ground / power**

* **PFC HV source:** **TDK-Lambda PF-A** (PF500A-360 / PF1000A-360), regulated **360 VDC** output, 504–1512 W. ([TDK Product][2])
* **RCCB 40 A / 30 mA:** Schneider **Acti9 iID** (2-pole/4-pole options). ([Schneider Electric][8])
* **EMI line filter (mains):** Schaffner **FN2090** two-stage. ([schaffner.com][9])
* **HV DC contactor / interlock:** **GIGAVAC GX14** sealed DC contactor. ([sensata.com][10])
* **HV connectors:** **Amphenol SurLok Plus** (tool-less compression, 1000–1500 V DC rated). ([Amphenol Industrial][11])

**Tether / data**

* **Gore RCN9166** (20 AWG + SMF) — chosen cable (OD 2.9 mm; 17.89 kg/km; 9.1 Ω/1000 ft). ([Gore][1])
* **1000BASE-LX SFPs (1310 nm, 10 km)**. ([img-en.fs.com][5])
* **SFP media converter** (e.g., **TP-Link MC220L**). ([Omada][12])
* **FORJ** for 200 m motorized reel. ([spinner-group.com][7])

**Airframe power & protection**

* **Vicor BCM6123** (K=1/16) **260–410 VDC in → 16.3–25.6 V out**, up to **62.5 A** (≈24 V sec from 384 V bus). ([Vicorpower][3])
* **Fallback**: **TDK-Lambda PH1200A280-24** (200–425 VDC → 24 V/50 A). ([mouser.com][4])
* **Ideal-diode / ORing**: **LM5050-2** (TI), **LTC4359** (ADI). ([Texas Instruments][6])

---

## 6) Data path (simple & robust)

Gore’s hybrid includes **single-mode fiber (8/125 with 900 µm buffer)**. Run **Gigabit 1000BASE-LX at 1310 nm** using standard SFPs and an MC220L media converter. Commodity, hot-pluggable, and far exceeds the distance you need. ([Gore][1])

---

## 7) Safety interlocks & protections (non-negotiable)

* **RCCB + MCB** on AC input (40 A / 30 mA typical). ([Schneider Electric][8])
* **Pre-charge / inrush limit** and **ideal-diode ORing** around the buffer pack (**LM5050-2 / LTC4359**). ([Texas Instruments][6])
* **Sealed HV DC contactor** with low-voltage interlock chain (**GX14**). ([sensata.com][10])
* **EMI line filter** at mains (**FN2090**). ([schaffner.com][9])

---

## 8) 100 m now; what changes for 200 m?

* **Cable:** standardize on **RCN9166** (20 AWG) for 200 m; the 24 AWG option’s drop/loss is unacceptable at that length. ([Gore][1])
* **Ground power:** step up to **PF1000A-360** class (≥1 kW) or parallel PF-A modules. ([TDK Product][2])
* **Reel/rotary:** add **FORJ** (fiber) and an appropriate power slip-ring for continuous payout/take-up. ([spinner-group.com][7])
* **Thermals:** ensure adequate baseplate cooling for the **BCM6123**; it supports 62.5 A secondary with proper thermal path. ([Vicorpower][3])

---

## 9) Tools & test gear you actually need

* HV-rated crimper & torque tools for **SurLok Plus**. ([Amphenol Industrial][11])
* IR camera, HV gloves, insulated mats.
* Fiber cleaver/splicer **or** pre-terminated pigtails + mechanical splices; LC bulkheads; optical power meter.
* Programmable DC load (24 V ≥1 kW), differential HV probes, insulation tester.

---

## 10) What you can build this week (realistic milestones)

* **Days 1–3:** PF500A-360 → 10 m tether → BCM6123 → dummy load. Validate temps and the LX link. ([TDK Product][2])
* **Days 4–7:** 100 m RCN9166, add OR-FET/inrush, start tethered hovers ≤ 800 W. ([Gore][1])
* **Next:** upgrade to ≥1 kW PF-A, integrate motorized reel + FORJ, extend to 200 m. ([TDK Product][2])

---

## 11) Cable choice recap (✅/❌)

| Criteria        |        **RCN9168 (24 AWG)** |        **RCN9166 (20 AWG)** |
| --------------- | --------------------------: | --------------------------: |
| OD / drag       |                    ✅ 2.3 mm |                    ❌ 2.9 mm |
| Mass @200 m     |                  ✅ ~2.06 kg |                  ❌ ~3.58 kg |
| DC resistance   | ❌ **23.6 Ω/1000 ft** (high) | ✅ **9.1 Ω/1000 ft** (lower) |
| 200 m @ ~1.3 kW |          ❌ ~379 W line loss |          ✅ ~147 W line loss |
| Verdict         |   ✅ fine for **100 m demo** |    ✅ required for **200 m** |

(Figures from GORE datasheet Table 2; our drop/loss math shown above.) ([Gore][1])

---

### Final call

* **Wire selected:** **Gore RCN9166** (20 AWG + SMF) for 200 m viability (OD 2.9 mm, 17.89 kg/km, 9.1 Ω/1000 ft, 600 V rating). ([Gore][1])
* **Ground power:** **PF-A** PFC front-end at **360 VDC**, sized 1.0–1.5 kW. ([TDK Product][2])
* **Airframe:** **Vicor BCM6123 (384→24 V)** for the best SWaP; **PH1200A280-24** is a heavier fallback. ([Vicorpower][3])
* **Data:** **1000BASE-LX over the integrated SMF** using commodity SFPs and an MC220L media converter. ([img-en.fs.com][5])

If you want, I can turn this into a GitHub-ready README for **N-Spine** with wiring diagrams and a live BOM sheet with India pricing from Mouser/element14/Robu.

[1]: https://www.gore.com/sites/default/files/resources/pdf/2025-09/gore-tethered-drone-cables-datasheet-us.pdf "Data Sheet: GORE Tethered Drone Cables for Commercial & Defense"
[2]: https://product.tdk.com/system/files/dam/doc/product/power/switching-power/ac-dc-converter/catalog/pf-a_e.pdf "PF-A Series Datasheet"
[3]: https://www.vicorpower.com/documents/datasheets/ds_BCM6123xD1E2663yzz.pdf "BCM® Bus Converter | BCM6123TD1E2663T00"
[4]: https://www.mouser.com/datasheet/2/400/ph1200a280_e-3241760.pdf?srsltid=AfmBOoqGdYY1fjNAbojDoJpaRBesi6AOzA_20suHk_2xPgMJG2GLrCrx&utm_source=chatgpt.com "PH1200A280 Series Datasheet"
[5]: https://img-en.fs.com/file/datasheet/sfp1g-lx-31-10km.pdf "1000BASE-LX-31 SFP 1310nm 10km Transceiver Datasheet | FS"
[6]: https://www.ti.com/product/LM5050-2?utm_source=chatgpt.com "LM5050-2 data sheet, product information and support"
[7]: https://www.spinner-group.com/images/download/kataloge_flyer/SPINNER_FiberOptic.pdf?utm_source=chatgpt.com "SPINNER Fiber Optic Rotary Joints"
[8]: https://www.se.com/in/en/product/A9R41240/acti-9-iid-rccb-2p-40a-30ma-type-ac/?utm_source=chatgpt.com "A9R41240 - Acti 9 iID - RCCB - 2P - 40A - 30mA - type AC"
[9]: https://www.schaffner.com/product/FN2090/Schaffner_datasheet_FN2090.pdf?utm_source=chatgpt.com "Multi-stage AC/DC EMC/RFI Filter with Excellent ..."
[10]: https://www.sensata.com/sites/default/files/a/sensata-gigavac-gx14-series-open-contactors-datasheet.pdf?utm_source=chatgpt.com "GX14"
[11]: https://amphenol-industrial.com/products/surlok-plus/?utm_source=chatgpt.com "SurLok Plus® | Compression Lug"
[12]: https://www.omadanetworks.com/in/business-networking/omada-accessory-media-converter/mc220l/?utm_source=chatgpt.com "MC220L | Gigabit SFP Media Converter | TP-Link India - Omada"
