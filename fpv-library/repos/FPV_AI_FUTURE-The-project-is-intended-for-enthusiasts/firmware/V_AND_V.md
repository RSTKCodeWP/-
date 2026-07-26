# Block-3 Firmware Bench V&V — Mandatory Props-OFF Gate

**Scope:** the three bench tests that gate ANY powered (props-on) test of the Block-3 kinetic
night-thermal interceptor. This document is the bench procedure for the Betaflight FPV-AI fork
(`firmware/betaflight-fork/`) and the independent HW-kill MCU (`firmware/hwkill-mcu/`).

**Status of this document:** the *logic* under test is already frozen as an executable
specification and is green in CI:

- `fpv_ai.betaflight_link.fork_model.ForkModel` — the fork's RX arbitration (V&V-1/2/3).
- `fpv_ai.betaflight_link.hwkill.HardwareKill` — the independent kill below the FC.
- `fpv_ai.betaflight_link.arming.ArmingStateMachine` — the single disarm authority.
- `fpv_ai.betaflight_link.failsafe.FailsafeController` / `Watchdog` — link/guidance watchdogs.

The bench tests below **re-prove the same invariants on real silicon.** If the bench result
disagrees with the model, the *hardware/firmware* is wrong and is blocked — the model has been
adversarially reviewed and is the reference. Do not "fix" a bench disagreement by editing the
model to match buggy firmware.

---

## 0. Hard rules (read before touching anything)

> **R0 — PROPELLERS OFF.** Every test in this document is run with propellers physically
> removed and set outside arm's reach. No exceptions, no "just this once."

> **R1 — Gate.** No tethered test, and no props-on test of any kind, runs until **all three of
> V&V-1, V&V-2, V&V-3 PASS on the actual flight controller AND the independent HW-kill MCU has
> passed its own bench check (Section 5).** A single FAIL or INDETERMINATE blocks the gate.

> **R2 — Order is fixed and not skippable:**
> `bench (props-off)  →  tethered (props-on, craft bolted to a fixture/load cell, no free flight)  →  free-flight`.
> You may not jump ahead. Re-run the full props-off suite after *any* firmware rebuild, config
> change, or wiring change — these tests are cheap and the failure mode is a spinning kinetic craft.

> **R3 — Two people.** One operator on the ELRS radio with a hand on the AUX-kill switch and a
> hand on the launch-console ABORT; one engineer on the bench instruments. The radio operator's
> only job is to be ready to kill.

> **R4 — Independent power domains stay independent during the test.** Do not bench the fork
> with the HW-kill MCU's RF beacon spoofed/forced-on by the same Pi that runs the fork. The point
> of the HW-kill is independence; testing it through the thing it guards against defeats the test.

### What the firmware actually does (grounded in current Betaflight `master`)

The fork is built on Betaflight's stock `RX_MSP_OVERRIDE` feature, NOT on `RX_MSP`. This is the
crux and the reason the three V&Vs are framed the way they are:

- Stock `rxInit()` in `src/main/rx/rx.c` selects exactly one provider via sequential
  `else if`: `FEATURE_RX_SERIAL` → `RX_PROVIDER_SERIAL`, else `FEATURE_RX_MSP` →
  `RX_PROVIDER_MSP`. **`RX_SERIAL` and `RX_MSP` are mutually exclusive** (Betaflight issue
  **#8292**). If you used `RX_MSP`, the ELRS radio would not exist to the FC and there would be
  no independent failsafe/kill. That configuration is forbidden for this craft.
- `RX_MSP_OVERRIDE` (feature `FEATURE_RX_MSP_OVERRIDE`, `src/main/rx/msp_override.c`,
  `rxMspOverrideReadRawRc()`) **layers on top of the serial (ELRS/CRSF) RX.** The serial RX stays
  primary; only the channels set in `rxConfig()->msp_override_channels_mask` are replaced by the
  Pi's `MSP_SET_RAW_RC` values, and only while the `BOXMSPOVERRIDE` mode is active. The serial
  RX's own frame status keeps driving `rxSignalReceived` / `rxFlightChannelsValid`. This is what
  lets the ELRS link keep an independent kill while the Pi flies.
- **Channel allocation (config invariant, asserted on the bench):**
  - Roll / Pitch / Yaw / Throttle → **in** `msp_override_channels_mask` (the Pi flies these).
  - **AUX arm channel** (`fork_model` `arm_aux_us`, default AUX1 ≥ 1700) and the **AUX-kill
    channel** (`fork_model` `kill_aux_us`, default AUX2 ≥ 1700) → **NOT** in the override mask.
    They are owned by the ELRS radio only. The Pi cannot, by construction, drive arm or kill.
- Anti-re-arm is stock: `src/main/fc/core.c` `tryArm()` path sets
  `ARMING_DISABLED_NOT_DISARMED` when the RX comes back with the arm switch already high
  (`justGotRxBack && IS_RC_MODE_ACTIVE(BOXARM)`), forcing a deliberate switch low→high edge. The
  fork must preserve this and additionally **latch** the inhibit on an ELRS kill (matching
  `ForkModel._arm_inhibit`).

### What the fork must FIX vs stock (the reason it is a fork, not a config)

Two stock bugs make `RX_MSP_OVERRIDE` unsafe for an autonomous craft and are the direct
subjects of V&V-2 and V&V-3:

- **#13374** (failsafe fires even though valid MSP override RC is present). Stock only counts
  the override toward link-validity when `rxConfig()->msp_override_failsafe` is set AND
  `BOXMSPOVERRIDE` is active. The fork must make MSP-fresh keep the craft alive (V&V-3) **and**
  make MSP-silence-but-ELRS-fresh hand control to ELRS within budget (V&V-2), per `ForkModel.update()`.
- **#13416** (MSP_OVERRIDE commands not executed / motors stop after arm under override). The
  fork must guarantee that, once armed, fresh MSP override does **not** stop the motors (V&V-3).

The fork's arbitration is exactly `ForkModel.update()` and must be reproduced bit-for-bit in C.
Timing budgets used below: `msp_timeout_s = 0.2 s` (MSP silence → handover), and Betaflight's
own `RXLOSS_TRIGGER_INTERVAL = 150 ms` (the serial-RX loss trigger in `rx.c`) — the firmware
must declare MSP loss and hand to ELRS within **≤ 200 ms** end-to-end.

### Common bench rig (all three tests)

- Flight controller flashed with the FPV-AI fork; battery NOT connected to ESC power — power the
  FC from USB or a bench 5 V rail so motors **cannot** be driven even if commanded (props are off
  too — belt and suspenders). For V&V-3 you DO need to see PWM/DSHOT output, so use one of:
  - a 4-in-1 ESC on a current-limited bench supply with **props off**, observing motor spin, OR
  - the FC motor outputs on a **logic analyzer / oscilloscope** (DSHOT or PWM), observing the
    commanded motor value without any ESC at all. Preferred — fully de-energized.
- ELRS receiver bound to the operator radio. Radio configured: AUX1 = arm, AUX2 = kill (a kill
  switch is a hard low/high; assign it to `BOXFAILSAFE` OR a dedicated disarm — see V&V-1 note).
- Raspberry Pi 5 connected to the FC MSP UART per `firmware/WIRING.md`, running the onboard
  runtime (`fpv_ai.betaflight_link.onboard_runtime`) sending `MSP_SET_RAW_RC` at the normal rate
  (≥ 50 Hz; 100–250 Hz typical) with `BOXMSPOVERRIDE` mode mapped to an AUX the Pi raises.
- Instruments: **logic analyzer** (≥ 4 ch, ≥ 1 MS/s) on { MSP UART TX from Pi, FC motor output,
  optionally the ELRS-kill AUX as decoded by FC blackbox }, and **Betaflight Blackbox** logging
  enabled (`debug_mode` set to log RX and failsafe; log `rcCommand`, `motor[]`, `rxSignalReceived`,
  `failsafePhase`). Blackbox is the timing ground-truth that does not depend on the Pi.
- A bench clock: use Betaflight blackbox `time` (µs) for all latency measurements so the Pi clock
  and the FC clock disagreement cannot bias the result.

---

## V&V-1 — ELRS AUX-kill disarms WHILE MSP is actively overriding

**Requirement:** the operator's ELRS AUX-kill disarms the craft *even while the Pi is actively
overriding RC via MSP.* This is the failure that stock `RX_MSP` makes impossible (#8292) and that
the fork's dominant-kill branch (`ForkModel.update()` step 1) restores.

**Model reference:** `ForkModel.update()` — `if elrs_fresh and elrs.aux2 >= kill_aux_us: armed=False,
arm_inhibit=True, reason="elrs_kill"`. Matches `test_fork_model.py` kill-dominance cases.

### Setup
1. Confirm config invariant: `msp_override_channels_mask` covers RPY+throttle only; AUX1(arm) and
   AUX2(kill) are NOT in the mask. (`get msp_override_channels_mask` in CLI; decode the bitmask.)
2. Power FC (USB / bench 5 V). Props OFF. Motor outputs on logic analyzer / de-energized ESC.
3. ELRS radio on; arm switch LOW, kill switch in the SAFE (not-killed) position.
4. Pi runtime streaming `MSP_SET_RAW_RC` at ≥ 50 Hz; raise `BOXMSPOVERRIDE`.

### Steps
1. Operator: move arm switch LOW→HIGH edge (throttle low). FC arms; blackbox `ARMED` flag set.
2. Pi: command a non-trivial override — e.g. throttle to a clearly non-idle value and a roll
   offset — via `MSP_SET_RAW_RC`. Confirm on logic analyzer + blackbox that the **motor output
   tracks the MSP-commanded value** (override is genuinely in control). Mark this instant `t0`.
3. Operator: flip the ELRS AUX2 kill switch HIGH. Do nothing on the Pi (the Pi keeps streaming
   the same non-idle override — this is the adversarial case: the AI is "trying" to fly).
4. Record from blackbox the instant the `ARMED` flag clears and motor output goes to disarmed
   (DSHOT 0 / PWM idle). Mark `t1`.
5. Keep the Pi streaming the non-idle override for ≥ 3 s after the kill. Confirm motors stay at
   zero (kill is sticky; the override cannot "win it back").
6. Operator: return AUX2 to SAFE but leave the arm switch HIGH. Confirm the craft does **NOT**
   re-arm (latched inhibit). Then cycle arm LOW→HIGH and confirm it re-arms only on that fresh edge.

### Measure
- `t1 − t0_kill` where `t0_kill` is the blackbox sample at which AUX2 crossed the kill threshold:
  disarm latency. (Informational; the pass criterion is *that it disarms and stays disarmed*, not
  a tight latency — but log it.)
- Motor output value during steps 3–5 (must reach and hold disarmed).
- Re-arm behavior in step 6.

### PASS criteria (ALL)
- Motors disarm (output → disarmed) after the ELRS kill **while MSP override is still streaming**.
- Disarmed state **holds** for the full ≥ 3 s with the override still commanding non-idle.
- Craft does **NOT** auto-re-arm when the kill is released with arm still high; re-arms only on a
  fresh arm-switch low→high edge.

### FAIL / INDETERMINATE
- FAIL if motors keep tracking the MSP override after the kill (this is the #8292 failure mode and
  means the fork's kill branch is not dominant — STOP, the craft is not benchable).
- FAIL if the craft auto-re-arms on kill-release with arm-high (latched inhibit broken).
- INDETERMINATE if you cannot prove from blackbox that the override was actually in control at `t0`
  (re-run with a larger, unambiguous override delta).

> **Config note:** wire the ELRS kill to a *disarm*, not (only) to Betaflight `BOXFAILSAFE`. The
> fork treats AUX2-high as a dominant disarm + latched inhibit; `BOXFAILSAFE` alone is a stage that
> the override-failsafe logic could mask. V&V-1 must prove a hard disarm, independent of any
> override-validity logic.

---

## V&V-2 — MSP heartbeat loss → RXFAIL → ELRS handover within ≤ 200 ms

**Requirement:** if the Pi (MSP) goes silent, the craft must stop trusting the stale MSP channels
and hand control back to the ELRS radio within **≤ 200 ms**. This is the live counterpart to
`msp_timeout_s = 0.2 s` in `ForkConfig`, and it is the bug class of #13374 (failsafe/validity must
account for MSP, but MSP going stale must *release* control to ELRS, not freeze on the last MSP frame).

**Model reference:** `ForkModel.update()` step 4 — `msp` stale, `elrs` fresh →
`reason="rxfail_elrs_handover"`, control source ELRS. And `ForkModel._fresh()` uses the 0.2 s window.
Note: stock `rxMspFrameStatus()` (`src/main/rx/msp.c`) has **no internal timeout** — it relies on
the generic `rx.c` staleness (`needRxSignalBefore`, `RXLOSS_TRIGGER_INTERVAL = 150 ms`). The fork's
job is to ensure the *override* path inherits a ≤ 200 ms staleness and reverts to the serial RX.

### Setup
1. Same rig as V&V-1. Both links live: Pi streaming MSP override, ELRS radio on with valid sticks.
2. ELRS sticks set to a **distinct, recognizable** RPY/throttle posture (e.g. throttle mid, full
   right roll) that is clearly different from the Pi's override posture, so the handover is visible
   on the motor outputs / blackbox `rcCommand`.
3. Logic analyzer channels: { Pi MSP UART TX, FC motor output }. Blackbox logging `rcCommand[]`,
   `rxSignalReceived`, `failsafePhase`, and the override mode flag.

### Steps
1. Arm (ELRS edge). Raise `BOXMSPOVERRIDE`. Confirm motors track the **Pi** override posture.
2. Hard-stop the Pi's `MSP_SET_RAW_RC` stream instantaneously (kill the runtime process, or
   physically pull the MSP UART TX line — pulling the wire is the cleaner test). Mark the **last
   MSP frame edge** on the logic analyzer as `t_silence`.
3. Observe the FC: motor outputs / `rcCommand` must transition from the **Pi posture** to the
   **ELRS posture** (control handed back to the radio). Mark that transition `t_handover` from
   blackbox (`rcCommand` first reflects ELRS sticks) and cross-check on the logic analyzer.
4. With the Pi still silent, operator flips ELRS AUX2 kill → confirm disarm still works (handover
   left a live, killable ELRS link). Then restore the Pi stream and confirm override resumes only
   after a deliberate re-commit (it must not silently snap back mid-armed without the operator —
   acceptable per design is that override resumes when MSP is fresh again AND mode is active; log
   which behavior the firmware exhibits).

### Measure (the headline number)
- **`Δ = t_handover − t_silence`** measured from blackbox µs timestamps (ground-truth), corroborated
  by the logic analyzer (last MSP TX edge → first motor-output change toward ELRS posture).
- Repeat **≥ 10 times**; report min / median / **max**. The max is what gates.
- Also log `failsafePhase`: ideally the craft hands to ELRS *without* entering stage-2 failsafe at
  all (the ELRS link is valid), i.e. `failsafePhase` stays `FAILSAFE_IDLE` — handover, not failsafe.

### PASS criteria (ALL)
- **Max `Δ` over all repeats ≤ 200 ms.**
- After handover, the motor output reflects the **ELRS** sticks (not frozen Pi values, not a
  failsafe drop while ELRS is valid — #13374 must not reproduce).
- ELRS kill (step 4) still disarms after handover.

### FAIL / INDETERMINATE
- FAIL if `Δ_max > 200 ms`.
- FAIL if motors freeze on the last Pi posture (stale MSP latched — handover broke).
- FAIL if the craft drops into a hard failsafe / disarms purely because MSP went silent **while
  ELRS is valid** (that is #13374; ELRS-valid means hand over, not failsafe-disarm).
- INDETERMINATE if Pi and ELRS postures were not distinguishable on the trace (re-run with a larger
  posture delta).

---

## V&V-3 — MSP override does NOT stop motors after arm (#13416 must not reproduce)

**Requirement:** once armed, switching into MSP override and streaming valid `MSP_SET_RAW_RC` must
**keep the motors running** and tracking the override — it must not silently stop them. Betaflight
issue **#13416** ("MSP_OVERRIDE commands not being executed", 4.5-RC2: motors stop after arm under
override) must not reproduce on the fork.

**Model reference:** `ForkModel.update()` step 3 — `msp_fresh` → control MSP, `motors_driven =
armed`, `reason="msp_override"`. `test_fork_model.py` proves armed+MSP-fresh keeps motors driven.

### Setup
1. Same rig. **Motor visibility is mandatory** for this test: either de-energized DSHOT/PWM on the
   logic analyzer (preferred) or a current-limited 4-in-1 ESC with **props OFF** so you can see/hear
   spin without risk.
2. Pi runtime ready to stream a clearly non-idle override (throttle modestly above idle so a running
   motor is unambiguous on the trace/RPM, but low — this is a bench, props off).

### Steps
1. Operator: arm via ELRS edge (throttle low). Confirm `ARMED`. With override **not yet active**,
   motors at idle/zero as expected.
2. Pi: raise `BOXMSPOVERRIDE` AND begin streaming a non-idle override (throttle above idle, neutral
   RPY). Mark `t_override_on`.
3. Observe motor outputs for **≥ 30 s continuous** with the override streaming at the normal rate:
   - Motors must reach the commanded non-idle value and **stay there** (no drop to zero, no
     periodic cut-outs).
   - Sweep the override throttle up and down a few times; the motor output must track it.
4. While motors are running under override, induce a *single-frame* MSP hiccup (drop exactly one
   `MSP_SET_RAW_RC` frame, well under the 200 ms window) and confirm motors do **not** cut on a
   single late frame (the staleness window, not per-frame, governs — matches `_fresh()`).
5. End the test cleanly: Pi lowers override / commands idle, operator disarms via ELRS edge, then
   ELRS kill to SAFE.

### Measure
- Motor output continuity over the ≥ 30 s window: count any sample where output unexpectedly → 0
  while a fresh override frame was present within the staleness window. **Expected count: 0.**
- Tracking error: motor output follows commanded override throttle through the sweep.
- Single-dropped-frame behavior (step 4): no cut.

### PASS criteria (ALL)
- Motors run continuously under armed MSP override for ≥ 30 s with **zero** unexpected cut-outs.
- Motor output tracks the override throttle sweep.
- A single dropped MSP frame (within the 200 ms window) does not stop the motors.

### FAIL / INDETERMINATE
- FAIL if motors stop, stutter, or periodically cut while valid override frames are arriving
  (this is #13416 reproducing — STOP).
- FAIL if a single late/dropped frame (inside the window) cuts the motors (over-tight per-frame
  gating; must use the staleness window).
- INDETERMINATE if motor visibility was insufficient to detect a brief cut (re-run on the logic
  analyzer at higher sample rate).

---

## 5. Independent HW-kill MCU bench check (gates with V&V-1/2/3)

The HW-kill MCU is the **last line below the FC** and is independent of the fork. It is verified on
its own bench before the gate opens. Model reference: `fpv_ai.betaflight_link.hwkill.HardwareKill`
and `test_hwkill.py`. The MCU firmware must reproduce these exactly (default-deny, latched
operator-kill, loss-of-beacon → cut, non-finite clock → cut).

**Rig:** MCU on its own dedicated RF/serial channel + its own clock (NOT the fork's MSP link, NOT
the Pi that runs the fork — see R4). MOSFET / smart-ESC kill line driving a **bench load (resistor
/ small bulb), not a motor**, so you can watch the gate without spinning anything. Logic analyzer on
{ permit-beacon RX, kill-line / gate output }.

| # | Test | Action | Expected (PASS) |
|---|------|--------|-----------------|
| 5.1 | Default-deny | Power MCU, send NO permit beacon | Gate **CUT** from boot (`motor_power_enabled == False`, `permit_beacon_lost`) |
| 5.2 | Permit enables | Stream a valid permit beacon at the design rate | Gate **PERMIT** (`powered`) only while beacon is fresh |
| 5.3 | Loss-of-signal | While permitted, stop the beacon | Gate **CUT** within `beacon_timeout_s` (default 0.5 s; must be ≥ the fork's software failsafe 0.2 s so the controlled ditch runs first). Measure last-beacon-edge → gate-low. |
| 5.4 | Operator kill latch | Send operator-kill on the dedicated channel | Gate **CUT immediately and LATCHED**; resuming the permit beacon does **NOT** re-enable. Only a deliberate physical reset clears it. |
| 5.5 | Latch survives transient | After 5.4, toggle beacon and power-glitch the RF | Gate stays CUT until physical `reset()` + a fresh live beacon |
| 5.6 | Non-finite / broken clock | Inject a stalled/backwards MCU clock | Gate **CUT** (a broken timer is not a permit) |
| 5.7 | Below-FC dominance | With the FC commanding motors (V&V rig), open the HW-kill gate | Motors de-power regardless of FC command (`effective_motor_power = fc_commands_motors AND hw_kill_enabled`) |

**PASS criteria:** all of 5.1–5.7 pass; measured loss-of-beacon cut time ≤ `beacon_timeout_s`;
operator-kill latch proven to survive beacon-return and an RF transient until physical reset.

**FAIL:** any case where the gate permits power without a fresh beacon, fails to latch the operator
kill, or fails to cut on loss-of-signal / non-finite clock. Any FAIL blocks the gate.

---

## 6. Gate decision and sign-off

Record, dated and signed by both the radio operator and the bench engineer:

| Test | Result | Headline measurement | Blackbox/LA log ref |
|------|--------|----------------------|---------------------|
| V&V-1 ELRS-kill-while-MSP | PASS / FAIL | disarm + sticky + no auto-re-arm | |
| V&V-2 MSP-loss → ELRS handover | PASS / FAIL | `Δ_max = ___ ms` (≤ 200) | |
| V&V-3 motors keep running (#13416) | PASS / FAIL | 0 cut-outs / 30 s | |
| HW-kill MCU (5.1–5.7) | PASS / FAIL | loss-cut `___ ms` ≤ `beacon_timeout_s` | |

> **Gate opens only when the box below is fully true:**
> `V&V-1 PASS ∧ V&V-2 PASS (Δmax ≤ 200 ms) ∧ V&V-3 PASS ∧ HW-kill 5.1–5.7 PASS`
>
> Then, and only then, proceed to **tethered (props-on, craft bolted to a fixture, no free
> flight)**, re-running this entire props-off suite first after the final pre-tether build. Free
> flight follows tethered, over a surveyed/cleared keep-out footprint, with the HW-kill armed and
> the operator on both the ELRS kill and the launch-console ABORT.

Any firmware rebuild, config change, or rewiring **invalidates the gate** and requires the full
props-off suite to be re-run.
