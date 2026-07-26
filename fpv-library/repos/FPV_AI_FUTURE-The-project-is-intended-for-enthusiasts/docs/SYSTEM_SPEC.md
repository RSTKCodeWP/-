# CUAS Block-3 "03-fpv" — Thermal Seeker System Specification

**Status: bench-validated prototype (TRL ≈ 3–4). Not flight-qualified. Not fielded.**
Last updated 2026-07-15. This document is written to be *honest for external review* — every capability claim
below is tied to evidence, and every limit is stated plainly.

---

## 1. What this is (one paragraph)

A companion-computer **seeker + guidance stack** for a **body-to-body (no warhead) kinetic counter-UAS
interceptor**. A nose-mounted thermal camera acquires and tracks the target; a human operator authorizes the
engagement with **two deliberate presses**; the stack then commands the airframe. The whole chain runs today on
a **Raspberry Pi 5 bench**; the target flight computer is a **Zynq/FPGA** (the Pi validates the algorithms and
integration bit-for-bit before the FPGA port). There is **no warhead** — the kill mechanism is the airframe
striking the target.

## 2. Architecture (sensor → actuator)

```
FT640 thermal ─▶ detector ─▶ track / LOS ─▶ guidance (PN) ─▶ mission supervisor ─▶ arming ─▶ actuator
 (8-bit CVBS)   (top-hat/CCL/  (ego-comp     (lateral accel)  (acquire→study→     (Ed25519   (MSP RC /
                 centroid)      LOS rate)                       ready→commit→        two-press) motors)
                                                                engage→terminal)
```
- **Detector** is bit-exact to the FPGA streaming front-end (top-hat → adaptive threshold → connected
  components → intensity-weighted sub-pixel centroid). The centroid is the primary line-of-sight measurement.
- **Default-DENY everywhere**: no LOS without a detection; no range without a real observable; no lock without
  enrollment; **no engagement authority without a verified operator commit**; degrade to coast/abort, never invent.

## 3. Human authority (the safety core)

- **Two physical presses**: (1) CAPTURE — lock the seeker onto the operator's aim; (2) LAUNCH — commit.
- The commit is a **dual-Ed25519 signed authorization** verified by the arming core; a single/invalid signature
  never arms. Pre-commit the system is **sense-only** (studies + builds the target reference, commands nothing).
- A **dominant, sticky KILL** (abort button) safes the system from any state and cannot be revived without a reset.
- **The machine never classifies the target type to permit or deny a hit.** The learned drone-vs-not classifier
  and its dataset were removed as untrusted; no ML gates the engagement. The human is the authority.

## 4. What is VALIDATED on real hardware (with evidence)

| Capability | Evidence |
|---|---|
| Detector runs on **live FT640 thermal** | 16.9 fps native 720×576 on the Pi5; recorded raw+annotated video + per-frame CSV (run t1) |
| **Full FC-link protocol** on a real Betaflight FC | MSP API 1.46, live gyro, 99–100 % link health; MSP codec/arming/authorization suites green on the Pi (138 tests) |
| **HITL two-press engagement** end-to-end | 2 physical buttons → lock → study → READY → dual-Ed25519 commit → arming ladder (SAFE→…→AI_ACTIVE) → RC on the wire; per-tick CSV dumps |
| **Physical motor actuation** (bench, props off) | operator's button spins the motors through the whole chain via direct MSP motor command |
| **Integrated Pi system** | config-driven `seeker.service` (auto-start, **safe-by-default: no motor actuation on boot**), auto-recording, web status |
| Clean-room core + FPGA front-end | `seeker_core` 21 tests green; streaming RTL detector with bit-exact co-sim (47 fpga tests) |

## 5. Honest envelope & limits (read this before believing anything)

- **TRL ≈ 3–4, BENCH.** Not flight-tested, not qualified, not fielded. All results are static-bench.
- **Strapdown misses a maneuvering target.** In the honest 3D sim, a strapdown seeker MISSES a weakly-maneuvering
  winged-UAV (~3.5 m CPA vs a ~1.5 m contact requirement); a **gimbaled** seeker HITS (~1.15 m). For body-to-body
  vs a maneuvering target, the **gimbal is the decisive lever**. The current bench is strapdown.
- **No measured range** on the bench (subtense/ToF ranging not exercised); **gyro uncalibrated** (ego-compensation
  OFF) until the S0 calibration is done — the bench validates detection/tracking, not ego-compensated LOS.
- **Detector weaknesses** (measured): ~6.5 s cold-start (camera warm-up); the camera-only path has **no
  cross-frame association** (needs the tracker stage) so the "target" hops in clutter; frame-edge artifacts and
  20-blob saturation in warm-clutter scenes. A real sky/clean-background test is pending.
- **Bench motor actuation is a demonstration, not flight-arm.** It uses the Betaflight motor-test path
  (`MSP_SET_MOTOR`, disarmed), because Betaflight will not arm from companion-computer MSP RC without
  `MSP_OVERRIDE` (and, per an open Betaflight issue, a base RC receiver to avoid failsafe). The real flight-arm
  path is `MSP_OVERRIDE` or the **Zynq driving actuators directly** (no MSP crutch).
- **Terminal lock-loss** is the identified root cause of the strapdown terminal miss (blob break-up at close
  range), not envelope/attitude/vibration — the fix is terminal lock-hold, not yet implemented.

## 6. Path to maturity (honest, ordered)

1. **Gimbal integration** — physical target tracking; the decisive lever for a maneuvering target.
2. **Calibration** — gyro-scale (S0) → enable ego-compensation; detector thresholds to the real scene; servo signs.
3. **Real-target sky tests** — detection range, SNR vs distance, true track continuity on a moving target.
4. **Terminal lock-hold** — the root-cause fix for the strapdown terminal miss.
5. **Zynq/FPGA flight computer** — the bit-exact detector front-end + direct actuator control (no MSP crutch);
   the Pi remains the golden reference.

## 7. Evidence index

- Per-run dumps: `runs/*.csv`, `runs/session_*.csv`, annotated + raw video.
- Bench-run report (detector on FT640): the run-t1 artifact.
- Test suites (Pi + dev): `fpv_ai/betaflight_link` 138, `seeker_core` 21, `fpga` 47, flagship guidance/safety.
- Sim reproductions: strapdown-vs-gimbal CPA, plant g-wall, terminal lock-loss root cause.

---

*Written to survive scrutiny. If a reviewer asks "does it work?", the answer is: the sense→authorize→command
chain is validated end-to-end on real hardware on a bench; the flight envelope against a maneuvering target is
NOT yet demonstrated and depends on the gimbal + terminal lock-hold + a flight-grade computer. That gap is the
work, and it is stated, not hidden.*
