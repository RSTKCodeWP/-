Great — locking this into a GitHub-ready repo for **N-Spine**.

Below are copy-paste files you can commit as-is. I’ve kept it modular (README + docs + BoM + tests). After the files, you’ll find a short “Sources” section with citations to the official datasheets I used.

---

### Repository description (put this in GitHub’s “Description” field)

High-voltage (360–400 VDC) ground-to-air tether + single-mode fiber link for 10″ FPV drones. Onboard isolated 24 V bus, buffer-battery failover, 100–200 m hybrid cable (power ±, 1× SMF). Includes architecture, BoM, wiring plan, and test checklists.

---

### `README.md`

```markdown
# N-Spine — HV Tether + Single-Mode Fiber for 10″ FPV (100–200 m)

**Brutally practical design:** push **high-voltage DC** up a **light hybrid tether** (power ± + **1× SMF**), convert to a stiff **24 V bus** on the drone, and keep data on **fiber** to kill EMI. Works at **100–200 m** on a 10″ airframe with a 4-in-1 **80 A / 6 S ESC**.

---

## 0) TL;DR
- **Cable**: GORE hybrid, **RCN9166** (20 AWG power ± + 1× SMF) for 200 m; **RCN9168** (24 AWG + 1× SMF) is OK for lighter 100 m demos.
- **Ground**: AC → **PFC 360 VDC** (PF-A) → contactor + pre-charge → tether.
- **Airframe**: **Vicor BCM6123** HV-bus converter (≈384→24 V) → 24 V bus → 4-in-1 ESC + avionics; **ideal-diode OR** to a small **6 S buffer**.
- **Data**: **1000BASE-LX (1310 nm)** SFPs over the tether’s single-mode fiber.

---

## 1) Architecture

```

230 VAC
→ RCCB/MCB → EMI filter
→ PFC front-end → ~360–400 VDC (Ground HV bus)
→ Tether (GORE hybrid: +HV, –HV, 1× single-mode fiber)
→ Airframe HV→LV converter (≈384→24 V isolated)
→ 24 V bus to ESC/FC/payload + OR’d 6S buffer
→ Fiber to SFP media converter (IP video/RC/telemetry)

```

**Design rules**
- Keep **current low** on the tether: run **~360–400 VDC** at a few amps.
- Use an **isolated HV→24 V** module on the drone with real thermal design.
- Treat the **6 S buffer** as ride-through for sags and climb bursts.
- Keep **control/video on SMF**; no copper data pairs in the tether.

---

## 2) Cable decision (3-wire: +, –, 1× SMF)

| Item | Power pair | Fiber | OD | Weight | Max DC-R (per conductor) | Role |
|---|---:|---:|---:|---:|---:|---|
| **RCN9168** | 24 AWG | 1× SM (900 µm) | **2.3 mm** | **10.29 g/m** | **23.6 Ω/1000 ft** | Lightest; best for 10–100 m demos |
| **RCN9166** | 20 AWG | 1× SM (900 µm) | **2.9 mm** | **17.89 g/m** | **9.1 Ω/1000 ft** | Heavier; required for real 200 m power |

**At 200 m (pair length = 400 m):**  
RCN9168 → ~31.0 Ω pair → ΔV ≈ **108 V** @ 3.5 A; loss ≈ **379 W** (too hot)  
RCN9166 → ~11.9 Ω pair → ΔV ≈ **42 V**  @ 3.5 A; loss ≈ **146 W** (tolerable)

**Decision:**  
- Standardize on **RCN9166** for 200 m ops.  
- Use **RCN9168** only when minimum weight/drag at ≤100 m is the top priority.

---

## 3) Ground power (GPU)

- **PFC HV source:** **TDK-Lambda PF-A** modules → regulated **360 VDC** (PF500A-360 ~504–756 W; PF1000A-360 ~1008–1512 W; parallelable).  
- **Safety/EMC:** 2-pole **RCCB 30 mA**, MCB, **mains EMI filter** (Schaffner FN2090), **HV DC contactor** (Gigavac GX14), **pre-charge** resistor + bypass, **bleeder**.  
- **HV connector:** **Amphenol SurLok Plus** (1 kV class), panel + inline, keyed.

---

## 4) Airframe power

- **Primary choice:** **Vicor BCM6123** (K=1/16) — **260–410 VDC in → ~16.3–25.6 V out** (24 V from ~384 V bus), up to **~62.5 A**. Tiny, isolated, high density.  
- **Fallback (heavier):** **TDK-Lambda PH1200A280-24** — **200–425 VDC in → 24 V / 50 A**, 1.2 kW.  
- **Bus conditioning:** 24–28 V TVS at ESC pads; 2–4× **2200 µF/63 V** low-ESR caps; **ideal-diode OR-ing** (LM5050-2 / LTC4359) to a **6 S 1–2 Ah** buffer.  
- **Thermals:** Conduction plate + ducted airflow on the converter; keep HV pigtail **short and isolated**.

---

## 5) Data path (simple + robust)
- The tether includes **single-mode fiber (8/125, 900 µm buffer)**.  
- Use **1000BASE-LX SFPs (1310 nm, 10 km)** and a compact **SFP↔RJ45** media converter (e.g., TP-Link **MC220L**).  
- Put the media converter on a regulated **5–12 V rail** (not the ESC BEC).

---

## 6) Build plan

### Phase-A (bench, 10 m)
1. AC → **PF500A-360** → ~360 VDC (≤500 W).  
2. 10 m of RCN9166/9168 → **BCM6123** on heatsink → 24 V dummy-load (0–800 W).  
3. LX SFP link over fiber; verify ground-loop immunity.

### Phase-B (field, 100 m)
1. **100 m RCN9166** on reel; add **pre-charge** + **ideal-diode** ends.  
2. Hover ≤800 W; log HV-in, HV-out, 24 V ripple, converter temps.  
3. **HV pull-test**: drop contactor at hover → buffer catches → controlled descent.

### Phase-C (200 m)
1. Upgrade to **PF1000A-360** (≥1 kW) or parallel PF-A.  
2. Motorized reel + **FORJ** (fiber-optic rotary joint) + suitable power slip-ring.  
3. Limit continuous throttle; allow buffer-assisted bursts; confirm thermal margins.

---

## 7) Safety (non-negotiable)
- **HV DC can injure/kill.** Rated connectors, creepage/clearance, insulated tools, PPE.  
- **Double-E-STOP:** logic + power path.  
- **No hot-plugging HV.** Pre-charge first; contactor enable last.  
- Operations only on private test site under local UAS rules.

---

## 8) Bill of Materials (core)

### Ground / GPU
- **PFC 360 VDC:** TDK-Lambda **PF500A-360** / **PF1000A-360**  
- **EMI filter:** Schaffner **FN2090** (1-phase, chassis mount)  
- **HV contactor:** **Gigavac GX14** (24 V coil)  
- **HV connector:** **Amphenol SurLok Plus** (panel + in-line kit)  
- **Protection:** RCCB 40 A/30 mA, MCB, pre-charge resistor + relay, bleeder

### Tether / data
- **Cable:** GORE **RCN9166** (20 AWG + 1× SMF) for 200 m; **RCN9168** for 100 m demo  
- **Fiber link:** 1000BASE-**LX** SFPs (1310 nm) + **TP-Link MC220L** media converter  
- **200 m reel:** FORJ (single-channel SMF) + rated power slip-ring

### Airframe
- **HV→24 V:** **Vicor BCM6123** (K=1/16); *alt:* **TDK-Lambda PH1200A280-24**  
- **OR-ing / inrush:** **LM5050-2** or **LTC4359** + FETs  
- **Protection:** TVS ~400 V (HV side), TVS 26–28 V (24 V side), low-ESR bulk

---

## 9) Repo structure

```

N-Spine/
├─ README.md
├─ docs/
│  ├─ system-architecture.md
│  ├─ cable-analysis-200m.md
│  ├─ safety-hazops.md
│  └─ references.md
├─ hardware/
│  ├─ ground-pfc/      # PF-A, contactor, pre-charge, E-STOP
│  ├─ tether/          # RCN9166/9168 terminations, strain relief
│  └─ airframe-psu/    # BCM6123 or PH1200 plate, OR-ing, TVS, caps
├─ bom/
│  ├─ bom-core.csv
│  └─ vendors-india.md
├─ tests/
│  ├─ bench-checklist.md
│  └─ flight-acceptance.md
└─ LICENSE

```

---

## 10) Acceptance checklist (extract)

- **HV enable path**: pre-charge OK; E-STOP drops; bleeder <60 V in <60 s  
- **24 V bus**: ripple <50 mVpp @ 30–50 A; no FC resets on load steps  
- **Failover**: HV kill at hover → buffer takeover → controlled descent  
- **200 m run**: sustained hover; BCM baseplate <85 °C; stable LX link
```

---

### `docs/system-architecture.md`

```markdown
# System Architecture — N-Spine

## Blocks
- **GPU (Ground Power Unit)**: AC → PF-A PFC → 360–400 VDC HV bus; EMI, RCCB/MCB, contactor, pre-charge, SurLok bulkhead.
- **Tether**: GORE hybrid (power ± + 1× SMF). 100 m demo: RCN9168 optional; 200 m: RCN9166 required.
- **Airframe PSU**: Vicor BCM6123 (K=1/16) for ~24 V from ~384 V; TVS, bulk caps; OR-ing to 6 S buffer (LM5050-2/LTC4359).
- **Data**: 1000BASE-LX SFP over tether SMF; SFP↔RJ45 media converter.

## Interfaces
- **HV out (ground)**: 360–400 VDC via SurLok; interlocked contactor; pre-charge first.
- **HV in (air)**: short twisted pigtail → TVS (~400 V) → HV→LV module → 24 V bus.
- **LV bus**: 24.0–24.3 V at ESC pads, sensed and compensated; 12 V/5 V aux rails from DC-DCs.
- **Fiber**: LC/SC per chosen transceivers; LX SFP modules at 1310 nm.

## Control & Interlocks
- HV OK lamp, interlock chain, E-STOP, current limit on PF-A.
- Line-tension interlock on reel (future), geofence in FC, throttle cap for early flights.
```

---

### `docs/cable-analysis-200m.md`

```markdown
# Cable Analysis @ 200 m — RCN9168 vs RCN9166

## Inputs
- HV bus ≈ 380–400 VDC; airframe draw ≈ 3.5 A (≈1.2–1.3 kW at ~92%).
- Round-trip length = 400 m (out + back).

## Datasheet values (per conductor)
- **RCN9168** (24 AWG): 23.6 Ω/1000 ft → 0.0774 Ω/m; OD 2.3 mm; 10.29 g/m.
- **RCN9166** (20 AWG): 9.1 Ω/1000 ft → 0.0299 Ω/m;  OD 2.9 mm; 17.89 g/m.

## Derived values
- **Pair resistance @ 200 m:**
  - RCN9168: 0.0774 × 400 ≈ **30.97 Ω**
  - RCN9166: 0.0299 × 400 ≈ **11.96 Ω**

- **Voltage drop @ 3.5 A:**
  - RCN9168: 3.5 × 30.97 ≈ **108 V**
  - RCN9166: 3.5 × 11.96 ≈ **41.9 V**

- **Line loss @ 3.5 A:**
  - RCN9168: 3.5² × 30.97 ≈ **379 W**
  - RCN9166: 3.5² × 11.96 ≈ **147 W**

## Decision
- **200 m ops:** choose **RCN9166**.  
- **100 m demo:** RCN9168 acceptable if weight is critical and power limited.

## Tether mass @ 200 m
- RCN9168 ≈ **2.06 kg**, RCN9166 ≈ **3.58 kg**.

```

---

### `docs/safety-hazops.md`

```markdown
# Safety & HAZOP — N-Spine

## Top hazards
- **Electric shock (360–400 VDC)**: fatal risk; enforce lockout, E-STOP, bleeder discharge.
- **Arc/inrush**: pre-charge with timed bypass; no hot-plugging.
- **Thermal**: BCM/PH modules on rated baseplate; verify <85 °C under worst-case.
- **Tether strike/prop contact**: hard fairlead, standoff, yaw limits without slip-ring.
- **EMI/ESD**: mains EMI filter; chassis bonding; fiber for data.

## Controls
- RCCB 30 mA + MCB; key-switch + mushroom E-STOP; contactor interlock; signage “DANGER—HVDC”.
- PPE: insulated gloves, mats, IR thermometer; test at a private site.

## Procedures
- Pre-charge → contactor enable; armed indicator; shutdown order: contactor → bleed to <60 V in <60 s → mains off.
```

---

### `docs/references.md`

```markdown
# References (primary datasheets)
- GORE — Tethered Drone Cables (RCN9166/RCN9168) datasheet (OD, weight, DC-R, fiber).
- TDK-Lambda — PF-A PFC modules (PF500A-360 / PF1000A-360), 360 VDC regulated.
- Vicor — BCM6123, 260–410 V primary, ratiometric ~16.3–25.6 V secondary (K=1/16).
- TDK-Lambda — PH1200A280-24, 200–425 VDC in → 24 V/50 A.
- TP-Link — MC220L media converter, 1000BASE-SX/LX ↔ RJ-45.
```

---

### `bom/bom-core.csv`

```csv
Block,Item,Part Number,Key Specs,Qty,Vendor Link (example)
Ground,PFC HV Source,TDK-Lambda PF500A-360,"AC→360VDC, 504–756W",1,https://product.tdk.com/en/search/power/switching-power/ac-dc-converter/info?part_no=PF500A-360
Ground,PFC HV Source (200 m),TDK-Lambda PF1000A-360,"AC→360VDC, 1008–1512W",1,https://www.emea.lambda.tdk.com/de-en/products/pf-legacy
Ground,Mains EMI Filter,Schaffner FN2090,"Single-phase, chassis mount",1,https://www.mouser.in/
Ground,HV DC Contactor,Gigavac GX14,"≥750VDC, sealed, 24V coil",1,https://www.mouser.in/
Ground,HV Connector Set,Amphenol SurLok Plus,"1 kV DC, tool-less",1 set,https://www.mouser.in/
Tether,Hybrid Cable (200 m),GORE RCN9166,"20AWG power ± + 1× SMF; OD 2.9mm",200 m,https://www.gore.com/products/tethered-drone-cables-commercial-defense
Tether,Hybrid Cable (100 m demo),GORE RCN9168,"24AWG power ± + 1× SMF; OD 2.3mm",100 m,https://www.gore.com/products/tethered-drone-cables-commercial-defense
Data,Media Converter,TP-Link MC220L,"GigE SFP ↔ RJ45, 1000BASE-SX/LX",1,https://www.omadanetworks.com/in/business-networking/omada-accessory-media-converter/mc220l/
Data,SFP Transceivers,1000BASE-LX SFP (1310 nm),"SMF, 10 km",2,https://www.fs.com/
Airframe,HV→LV Converter (primary),Vicor BCM6123 (K=1/16),"260–410VDC → ~16–26V, up to ~62.5A",1,https://www.vicorpower.com/documents/datasheets/ds_BCM6123xD1E2663yzz.pdf
Airframe,HV→LV Converter (alt),TDK-Lambda PH1200A280-24,"200–425VDC → 24V/50A, 1.2kW",1,https://product.tdk.com/en/search/power/switching-power/dc-dc-converter/info?part_no=PH1200A280-24
Airframe,Ideal-Diode Controller,TI LM5050-2,"High-side OR-ing FET controller",2,https://www.ti.com/lit/gpn/LM5050-2
Airframe,Ideal-Diode Controller (alt),ADI LTC4359,"4–80V ideal-diode controller",2,https://www.analog.com/
Airframe,TVS (HV side),Littelfuse SMCJ400A,"SMCJ, ~400V clamp",2,https://www.mouser.in/
Airframe,TVS (24V side),Littelfuse SMBJ26A,"SMBJ, 26–28V clamp",4,https://www.mouser.in/
Airframe,Bulk Caps,Low-ESR 63V 2200uF,"Panasonic/Nichicon",4,https://www.mouser.in/
Airframe,Aux BEC,Matek 12S Pro BEC,"9–55V in → 5/8/12V @ 5A",1,https://anubisrc.com/
```

---

### `bom/vendors-india.md`

```markdown
# Vendors — India (examples)
- **Mouser India** — PF-A, PH1200A, TVS, SurLok, GX14, capacitors.
- **element14 / Farnell India** — passives, TVS, caps, tools.
- **AnubisRC / Robu** — RC BECs, LiPos (for buffer/testing).
- **FS.com / D-Link / ProLabs** — 1000BASE-LX SFPs.
- **TP-Link / Retail** — MC220L media converter.
- **Gore (direct / distributor)** — RCN9166 / RCN9168 hybrid tether.
```

---

### `tests/bench-checklist.md`

```markdown
# Bench Checklist (10 m)

- PF-A set to 360–380 VDC; current limit ≤ 6 A
- Pre-charge timing verified; E-STOP drops; bleed <60 V in <60 s
- 10 m tether to BCM6123 on heatsink; dummy-load sweep 0→800 W
- 24 V ripple <50 mVpp at 30–50 A; no resets on load steps
- LX link BER 0 over 15 min; no EMI artifacts on video
```

---

### `tests/flight-acceptance.md`

```markdown
# Flight Acceptance (100 m then 200 m)

## 100 m
- Hover 5→10 min at 5/15/30 m AGL; log HV in/out, BCM temp
- HV pull test at hover: buffer takeover, controlled descent
- Short bursts (≤2 s) show buffer current spikes; HV current cap respected

## 200 m
- Standard tether = RCN9166; PF-A ≥ 1 kW
- Sustained hover + wind hold: BCM baseplate <85 °C; 24 V bus ±0.3 V
- Reel tension stable; FORJ link clean; no fiber alarms
```

---

### `LICENSE`

```text
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
...
(standard MIT text)
```

---

## Sources (key facts)

* GORE Tethered Drone Cables datasheet: OD, weight, conductor DC-R, 1× single-mode fiber (RCN9166/RCN9168) — ([Gore][1])
* TDK-Lambda PF-A (PF500A-360 / PF1000A-360): AC→**360 VDC**, power ranges, parallel use — ([TDK Product][2])
* Vicor BCM6123: **260–410 V** primary, isolated **~16.3–25.6 V** secondary (K=1/16), high density — ([Vicorpower][3])
* TDK-Lambda PH1200A280-24: **200–425 VDC in → 24 V/50 A**, 1.2 kW — ([TDK Product][4])
* TP-Link MC220L: GigE **1000BASE-SX/LX ↔ RJ-45** media converter (India page & datasheet) — ([Omada][5])

---

Want me to add a small ASCII wiring diagram for the SurLok + pre-charge path and an image-ready PDF of the README for sharing?

[1]: https://www.gore.com/sites/default/files/resources/pdf/2025-09/gore-tethered-drone-cables-datasheet-us.pdf?utm_source=chatgpt.com "GORE® Tethered Drone Cables"
[2]: https://product.tdk.com/en/search/power/switching-power/ac-dc-converter/info?part_no=PF500A-360&utm_source=chatgpt.com "PF500A-360 : Detailed Information - AC-DC Power Supplies"
[3]: https://www.vicorpower.com/documents/datasheets/ds_BCM6123xD1E2663yzz.pdf?utm_source=chatgpt.com "BCM® Bus Converter | BCM6123TD1E2663T00"
[4]: https://product.tdk.com/en/search/power/switching-power/dc-dc-converter/info?part_no=PH1200A280-24&utm_source=chatgpt.com "PH1200A280-24 : Detailed Information - DC-DC Converters"
[5]: https://www.omadanetworks.com/in/business-networking/omada-accessory-media-converter/mc220l/?utm_source=chatgpt.com "MC220L | Gigabit SFP Media Converter | TP-Link India - Omada"
