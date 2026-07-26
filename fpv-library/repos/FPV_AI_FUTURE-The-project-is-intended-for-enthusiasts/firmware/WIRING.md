# Block-3 Hardware Integration & Wiring

**Scope:** the full physical integration of the Block-3 night-thermal kinetic interceptor:
Raspberry Pi 5 (the AI) ↔ Betaflight FC over MSP UART; FT640 analog thermal → Pi; analog VTX tap
for the operator monitor; the **independent HW-kill MCU between battery/ESC power and the motors**;
and the operator launch-console ABORT driving the MCU.

This document pairs with `firmware/V_AND_V.md`. Nothing here is energized with props on until the
three V&V tests + the HW-kill bench check pass.

Verified software modules referenced (frozen, green in CI):
`fpv_ai.betaflight_link.onboard_runtime`, `…serial_link`, `…msp_codec`, `…fork_model.ForkModel`,
`…arming.ArmingStateMachine`, `…failsafe.FailsafeController/Watchdog`, `…hwkill.HardwareKill`.

---

## 0. Power & signal domains (the most important diagram)

There are **three deliberately independent domains.** Independence is a safety property, not an
accident — do not cross-power them for convenience.

```
                         ┌───────────────────────── FLIGHT POWER DOMAIN ─────────────────────────┐
   LiPo (4S/6S) ──┬────────────────► [ HW-KILL GATE ]  ── switched motor power ──► 4-in-1 ESC ──► MOTORS
                  │                  (MOSFET / smart-ESC                                  ▲
                  │                   kill line, default-DENY)                            │ DSHOT/PWM
                  │                        ▲                                              │
                  │                        │ gate = permit-beacon-fresh AND not-latched   │
                  │                        │                                              │
                  ├──► BEC 5V ──► FC ───────────────────────────── motor signals ─────────┘
                  │              (Betaflight FPV-AI fork)
                  │                 │  ▲
                  │            MSP  │  │ telemetry            ELRS RX ──(CRSF)── FC   (operator radio:
                  │            UART │  │                         ▲                    arm AUX1 + kill AUX2,
                  │                 ▼  │                         │ 2.4/915 ELRS RF    NOT in MSP override mask)
                  ├──► BEC 5V ──► RPi 5 ──────────────────────────┘
                  │              (AI: detect/track/guide, MSP_SET_RAW_RC override)
                  │                 ▲
                  │     CVBS→USB     │ FT640 analog thermal (CVBS) ─► USB frame grabber ─► Pi USB
                  │
                  └──────────────────────────────────────────────────────────────────────┐
                                                                                          │
   ┌──────── INDEPENDENT KILL DOMAIN (its own battery cell or BEC + its own clock) ───────┘
   │
   HW-KILL MCU (RP2040 / Pico)  ◄── dedicated RF/serial RX ──  permit beacon  ◄─┐
        │  drives gate above                                                    │
        │                                                                       │
        └── operator-kill latch ◄────── ABORT (mushroom) on dedicated channel ──┤
                                                                                │
   LAUNCH CONSOLE (operator) ──── permit beacon TX + ABORT TX ──────────────────┘
        (also: ELRS radio handset for arm/kill;  analog video RX for monitor)
```

Key independence rules:
- The **HW-kill MCU has its own power feed and its own clock.** It must keep deciding (and keep the
  gate honest) even if the Pi is hung, the FC is bricked, and the ELRS link is jammed. It reads
  **only** its own dedicated permit-beacon RF/serial + the operator ABORT — never MSP, never ELRS,
  never the FC. This mirrors `hwkill.py`'s docstring exactly.
- The **HW-kill gate sits physically in the motor-power path, below the FC and below the ESC's
  logic.** It cuts the power the motors draw, so a commanded-but-unpermitted motor cannot spin.
- The **ELRS link is a separate RF domain from the permit beacon.** Two independent kills (ELRS
  AUX-kill disarms the FC; HW-kill cuts motor power) that do not share a failure.

---

## 1. Raspberry Pi 5 ↔ FC — MSP UART

The Pi flies the FC by sending `MSP_SET_RAW_RC` over a hardware UART; the FC sends MSP telemetry
back (the Pi's `FailsafeController` link watchdog feeds on this — `on_telemetry()`).

### Pi 5 UART choice — use the PL011, not the mini-UART
- **Use `/dev/ttyAMA0` (PL011)**, GPIO14 (TXD, pin 8) / GPIO15 (RXD, pin 10). The PL011 is a
  full 16550-class UART with a stable, clock-independent baud rate — required for reliable MSP at
  high rate. The mini-UART (`/dev/ttyS0`) ties its baud to the core clock and is unsuitable.
- On Pi 5, free the primary UART from the Linux console and enable it:
  - `/boot/firmware/config.txt`: `enable_uart=1`, and (Pi 5) `dtparam=uart0` / use the
    `dtoverlay=uart0` mapping for the 40-pin header UART; ensure the Bluetooth modem is not
    stealing PL011 (`dtoverlay=disable-bt` if needed) so `ttyAMA0` is the header UART.
  - Remove `console=serial0,115200` from `/boot/firmware/cmdline.txt` so Linux does not drive the
    line.
- The serial transport in software is `fpv_ai.betaflight_link.serial_link` / `…transport`; frame
  encode/decode is `fpv_ai.betaflight_link.msp_codec` (it also **sanitises non-finite guidance to
  neutral/idle** before it ever becomes an MSP frame — invariant 4 of `arming.py`).

### Pin-to-pin (level-matched 3.3 V — do NOT cross 5 V into the Pi)
Both Pi 5 and modern FC MSP UART pads are **3.3 V logic**. Connect directly, TX→RX crossed:

| Signal            | Raspberry Pi 5 (40-pin)      | Flight Controller (MSP UART pad) |
|-------------------|------------------------------|----------------------------------|
| Pi **TX** → FC RX | GPIO14 / TXD0, **pin 8**     | UARTx **RX**                     |
| Pi **RX** ← FC TX | GPIO15 / RXD0, **pin 10**    | UARTx **TX**                     |
| **GND** (common)  | pin 6 (or 9/14/20/25/30/34/39)| FC GND                          |

- **Common ground is mandatory** and must be a solid, short tie — a floating ground is the classic
  cause of intermittent MSP corruption that can look like a fork bug on the bench.
- Do **not** power the Pi from the FC's BEC through these pins. The Pi has its own BEC (it draws too
  much for the FC 5 V rail and a brownout there is catastrophic). Only TX/RX/GND cross here.
- Keep the MSP UART harness short and away from the VTX and motor leads (RF/EMI). Twist TX/RX with
  ground if it must run near power.

### FC-side configuration (Betaflight CLI)
- Assign the chosen UART to **MSP** in Ports (`serial …` peripheral = MSP) at the Pi's baud.
  **Baud: 115200** is the safe default and matches the bench; you may raise to 230400/420000 only
  after re-passing all V&V at that rate. Set `serial …` MSP baud index accordingly.
- ELRS stays the **serial RX** (`feature RX_SERIAL`, `serialrx_provider = CRSF`) on its **own**
  UART — this is the independent radio. (Recall `rxInit()` in `src/main/rx/rx.c` selects one RX
  provider; serial RX is it. MSP override layers on top — next item.)
- Enable the fork's override path: `feature RX_MSP_OVERRIDE`, set
  `msp_override_channels_mask` to **roll+pitch+yaw+throttle only**, and map `BOXMSPOVERRIDE` to the
  AUX the Pi raises. **Leave AUX1(arm) and AUX2(kill) OUT of the mask** so the ELRS radio keeps sole
  ownership of arm/kill (the V&V-1 invariant). With the fork, ensure `msp_override_failsafe` and the
  arbitration behave per `ForkModel.update()` (#13374/#13416 fixes).

---

## 2. FT640 analog thermal → Pi (vision input)

The FT640 is an **analog CVBS** thermal core (composite video out), not USB/CSI. Path:

```
FT640 thermal core ──(analog CVBS, e.g. PAL/NTSC composite)──► USB video frame grabber
                                                              (UVC, e.g. a CVBS-to-USB capture)
                                                              ──► Pi 5 USB port ──► /dev/video0
```

- **FT640 → grabber:** composite video center conductor to the grabber's CVBS input; shield to the
  grabber's video ground. Match the FT640's video standard (PAL vs NTSC) to the grabber.
- **Grabber → Pi:** any USB UVC frame grabber that enumerates as `/dev/video0`; the Pi's perception
  runtime (`fpv_ai.betaflight_link.onboard_runtime` → perception/seeker) reads frames from it.
- **Power the FT640 from a clean rail** (its own regulator off the Pi BEC or a dedicated BEC), well
  decoupled — thermal cores are sensitive and a noisy rail shows up as video noise that degrades the
  tracker. Keep the FT640 video lead away from the VTX and motor leads.
- **Latency note (design constraint):** the analog→USB grabber path adds capture+USB latency
  (typ. tens of ms). The guidance/failsafe layer already accounts for stale vision —
  `FailsafeController` HOLD_LAST coasts on the last valid command for brief gaps (`guidance_hold_s`)
  and ABORTs on a long gap (`guidance_abort_s`). Do not tighten the loop assuming zero camera latency.

---

## 3. Analog VTX tap → operator monitor

The operator must see what the seeker sees, on an independent analog path (so the operator retains
situational awareness even if the Pi/MSP link is degraded).

```
FT640 CVBS ──┬──► USB grabber ──► Pi (AI vision, Section 2)
             │
             └──► Analog VTX (5.8 GHz) ──RF──► operator's analog video RX ──► launch-console monitor
```

- **Tap the FT640 composite video before the grabber** (a simple video splitter / buffered tap, or
  the FT640's second video output if present) so the VTX feed is independent of the Pi. If the Pi
  dies, the operator still has live thermal video on the monitor.
- Optionally overlay the Pi's track box via the FC/OSD or a dedicated OSD on the VTX path — but the
  *raw* analog video must reach the operator even with the Pi down.
- **VTX power:** off the flight BEC, but keep its lead and antenna away from the MSP UART and the
  ELRS RX (RF desense of the control link is a real failure mode). Antenna isolation between VTX,
  ELRS, and the permit-beacon RX must be checked on the bench.

---

## 4. Independent HW-kill MCU — between battery/ESC power and the motors

This is the **last line below the FC**, the physical realization of `hwkill.py`. It is a
self-contained MCU (target **RP2040 / Raspberry Pi Pico**, or Arduino-class) whose only outputs are
the motor-power gate and whose only inputs are its own dedicated permit-beacon RX + the operator
ABORT on that dedicated channel + its own clock.

### Where it cuts (the gate)
Place the gate **in the motor-power path, below the FC and ESC logic** so an unpermitted motor
command cannot turn a motor:

- **Option A — high-side MOSFET on the ESC main power** (preferred for a 4-in-1 stack): a logic-
  level / gate-driven high-side switch (P-FET + driver, or a high-side smart-switch / solid-state
  relay rated for the pack current and inrush) between the LiPo+ and the ESC's main power input. MCU
  GPIO drives the gate; **default state = OPEN (power cut)**. Use a pull that defaults the gate to
  CUT if the MCU is unpowered or its GPIO floats (default-deny in hardware, not just firmware).
- **Option B — smart-ESC kill line:** if the ESC exposes a dedicated enable/kill input, the MCU
  drives it directly to the cut state by default. Verify the ESC actually de-powers the motors (not
  merely "idle") when the line is asserted.
- Size the switch for **continuous pack current + inrush**; add a pre-charge / soft-start so closing
  the gate does not brown out the ESC. Snub/clamp for inductive motor-power switching.

### MCU inputs / power (independence)
- **Own power:** a separate BEC or a small dedicated cell so the MCU keeps running and the gate stays
  honest when the rest of the craft is dead. If it shares the main pack, it must default the gate to
  CUT on its own brownout.
- **Own clock:** the MCU's own oscillator drives the `beacon_timeout_s` watchdog
  (`HardwareKill` → `Watchdog`). A **non-finite / stalled / backwards clock → CUT** (firmware
  invariant 4; bench test 5.6).
- **Dedicated permit-beacon RX:** its OWN RF/serial channel (separate band/module from ELRS and from
  the VTX), receiving a periodic "engagement permitted" beacon from the launch console. **No fresh
  beacon within `beacon_timeout_s` (default 0.5 s) → CUT** — autonomously. The 0.5 s default is
  deliberately **longer than the software failsafe (0.2 s)** so the controlled safe-ditch runs first
  and this is the guaranteed backstop.
- **Operator ABORT on the same dedicated channel → CUT, LATCHED** until a deliberate physical reset
  (`operator_kill()` / `reset()`). A transient or a returning beacon does **not** re-enable
  (bench tests 5.4/5.5).

### Firmware contract (must match `fpv_ai.betaflight_link.hwkill`)
- `permit_beacon(now)` — fresh valid beacon → feed the watchdog.
- `operator_kill(reason)` — latch CUT until `reset()`.
- `motor_power_enabled(now)` = `not latched AND beacon.healthy(now)` → drives the gate GPIO.
- Default-deny on boot (gate CUT until the first fresh beacon).
- `effective_motor_power = fc_commands_motors AND hw_kill_enabled` — the gate is a dominant veto.

> The MCU does **not** read the FC, the Pi, MSP, or ELRS. If you find yourself wiring any of those
> into the MCU, stop — that destroys the independence that is the entire reason this layer exists.

---

## 5. Operator launch-console → ABORT and permit beacon

The launch console (operator station) is the human authority. It does three independent things:

1. **Drives the HW-kill MCU:** transmits the periodic **permit beacon** on the MCU's dedicated
   channel (its presence = "power may stay on") and the **ABORT (mushroom button)** on that same
   dedicated channel. Pressing ABORT → MCU `operator_kill()` → latched motor-power CUT. Releasing
   ABORT or losing the console does **not** re-enable — only a physical reset at the craft does.
2. **Holds the ELRS handset:** the operator's radio with **AUX1 = arm** (low→high edge to arm; no
   auto-re-arm — stock `ARMING_DISABLED_NOT_DISARMED`, latched by the fork on kill) and
   **AUX2 = kill** (dominant disarm even while MSP overrides — V&V-1). These are NOT in the MSP
   override mask.
3. **Shows the operator monitor:** the analog video RX fed by the VTX tap (Section 3).

The console also originates the **committed authorization** the arming core requires
(`ArmingAuthorization` in `arming.py`: verifier-passed + keypress recorded within the auth window,
unexpired, non-synthetic for a live engagement). The physical FIRE keypress is **data inside that
authorization**, not a free-floating latched signal — so a stale press cannot auto-arm a later,
unrelated authorization.

### Two operator kill paths, by design (independent failure modes)
| Path | Mechanism | What it stops | Independent of |
|------|-----------|---------------|----------------|
| ELRS AUX2 kill | Radio → FC disarm (fork dominant-kill + latched inhibit) | FC disarms; motor commands stop | the Pi/MSP, the permit beacon |
| Console ABORT | Mushroom → permit-beacon channel → HW-kill MCU latched CUT | Motor **power** physically cut below the FC | the FC, the Pi, ELRS |

Both must be reachable by the operator at all times during tethered and free-flight tests.

---

## 6. Pre-power wiring checklist (before any V&V)

- [ ] MSP UART: Pi `ttyAMA0` TX(pin8)→FC RX, RX(pin10)←FC TX, **common GND**; 3.3 V both sides;
      Pi NOT powered from FC.
- [ ] Pi `config.txt`/`cmdline.txt`: PL011 freed from console, `enable_uart=1`, BT not on PL011.
- [ ] FC: ELRS = `RX_SERIAL`/CRSF on its own UART; MSP on the Pi's UART @115200; `RX_MSP_OVERRIDE`
      enabled with `msp_override_channels_mask = RPY+throttle only`; AUX1/AUX2 NOT in mask.
- [ ] FT640 CVBS → USB grabber → Pi `/dev/video0`; FT640 on a clean dedicated rail.
- [ ] VTX tap independent of the Pi; VTX/ELRS/permit-beacon antennas isolation-checked.
- [ ] HW-kill gate physically in the motor-power path (LiPo+ → gate → ESC), **default-OPEN/cut**;
      MCU on its own power + own clock + own permit-beacon RX; ABORT on the dedicated channel.
- [ ] Props OFF; ESC power either disconnected or on a current-limited bench supply.
- [ ] Two operators present; ELRS kill and console ABORT both within reach.

Only after this checklist and `firmware/V_AND_V.md` Sections V&V-1/2/3 + HW-kill 5.1–5.7 all PASS
does the craft advance to **tethered (props-on, bolted to a fixture)**, then **free flight** over a
surveyed/cleared keep-out footprint.
