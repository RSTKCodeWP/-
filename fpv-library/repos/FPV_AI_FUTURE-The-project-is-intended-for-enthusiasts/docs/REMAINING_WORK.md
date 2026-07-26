<!-- Honest remaining-work assessment, grounded in the tree as of 2026-07-19. Update when reality changes. -->

# BLOCK-03 — REMAINING WORK (honest assessment, 2026-07-19)

Grounding: full suite **723 passed / 0 failed** on this tree; the gimbal measurement (`10/10`, CPA 1.23 m) is
from today. This is not a wish-list — every item is tied to something measured or to a physical gap named in
the repo. Effort is in rough person-days for someone who knows this codebase; treat it as order-of-magnitude.

## The one-line status

**The front half of the system is real on hardware. The back half is real only in simulation. Nothing has
flown, and the physical airframe does not yet match the software.** Everything below is about closing those
three gaps, in dependency order.

---

## What is genuinely DONE (do not redo)

| capability | evidence | where |
|---|---|---|
| Perception on a live FT640 | ~20 fps, real thermal, person + compact targets locked | Pi @ 192.168.1.103, `fpv_ai.bench` |
| Operator authority chain | two-press Ed25519 → arming `AI_ACTIVE`; no arm without it | `production_runtime`, tested |
| MSP override link + manual backup | bench-verified over USB | `msp_override_flight.py` |
| Autonomous closure, **gimbal**, in sim | **10/10, CPA 1.23 m**, closed perception loop, real servo dynamics | `launch_and_forget mount="gimbal"` |
| MARCH reacquisition (off-FOV) | reacquires a 99°-off target within ~2° | `march_sim` |
| Gimbal control + plant + bench | controller, servo model, data-log, tests | `fpv/gimbal/` (0.6k) |

**The decision this unblocks:** strapdown 0/5 vs real gimbal 10/10 on one harness. The configuration question
is now a measurement, not an argument. If the owner picks gimbal, the sim path is closed end to end.

---

## The three real gaps, in dependency order

### GAP 1 — The physical airframe does not match the software premise
This is the true long pole and it is **procurement + integration, not code**. From the 2026-06-21 audit
(`[[block03-hardware-vs-software-gap]]`):

- The **flashed FC is a stock manual-FPV quad**: `msp_override_channels_mask=0`, no `RX_MSP_OVERRIDE`, no
  failsafe/kill box, ARM on AUX5. The MSP-override flight path and the Betaflight fork are an **unapplied
  spec — none of it is on silicon.**
- The **BOM camera is visible-light** (Caddx Ratel), not thermal. The FT640 that works on the bench and the
  QD115TB gimbal are separate hand-held units, not integrated on the airframe.
- The **HW-kill MCU firmware is unflashed and unbenched** (`clock_is_valid()` is a stub). The only kill on
  the airframe today is stock ELRS RX-loss auto-land.

**Work:** re-flash the FC with the fork (MSP override + kill box); mount the thermal seeker (gimbal, per
today's result) + Pi + kill-MCU; wire the three independent power/kill/radio domains per `firmware/WIRING.md`;
flash and bench the kill-MCU (replace the `clock_is_valid` stub). **~5–10 days, gated on parts in hand.**
Nothing downstream is real until this exists.

### GAP 2 — Hardware-in-the-loop has never been closed
We have proven perception on the real seeker, and we have proven the closed loop in sim. We have **never run
the two together**: real seeker frames → real guidance → commands, closing on a moving cue.
`sil_runtime.py` is deployed to the Pi but a clean live closed-loop run is still pending.

**Work, staged (props OFF throughout):**
1. **Bench HIL on a static stand** — seeker on the gimbal bench (`fpv/gimbal/bench_runner.py`,
   `seeker_core/gimbal_bench_io.py` already exist), target moved by hand, verify the guidance command tracks.
   **~3–5 days.** This is the cheapest way to catch the gap between rendered-thermal sim and real AGC/clutter.
2. **Full HIL** — real FC in the loop (MSP), real seeker, motion on a rig or captive test. **~5–8 days.**

This is where the sim's optimism gets tested. The rendered thermal is clean; real FT640 AGC, clutter, and
vibration are not. Expect surprises here, not in flight — that is the point of doing it.

### GAP 3 — Nothing has flown
The MSP-override manual-backup path (`FLIGHT_TEST_OVERRIDE.md`) exists precisely so a first flight is
recoverable: the pilot holds the sticks, the toggle hands the seeker a bounded envelope, release or Pi-loss
returns control to the RX. But it has **not been flown**, and no §"proven-in-sim" claim is real until it is.

**Work:** first flight tests in the bounded envelope (slow overhead well-cued target, up-camera viewable
cone), manual backup live. **~5–10 flying days**, entirely gated on GAP 1 and GAP 2. This is field work, not
desk work, and it carries the real irreducible risk.

---

## Software items still open (all now LOWER priority than the gaps above)

Today's gimbal result reorders these. They were mostly attacking the **strapdown** failure, which the gimbal
dissolves — so they are refinements, not blockers, for the doctrine target.

- **Guidance upgrade** (`GUIDANCE_UPGRADE_PLAN.md`: ZEM/OGL lag-comp, IRPL frame). The "correct too late and
  too hard" problem was measured on strapdown, where λ̇ was corrupted; with the gimbal λ̇ is clean (median
  0.030) and it hits 10/10 **without** these. They remain worth doing for **envelope width against maneuver**
  — but the 0.84 g plant wall bounds that regardless, so the payoff is capped. **Downgraded to nice-to-have.**
- **Over-demand policy** (§6.1) — same story: it mattered because saturated bank corrupted the strapdown
  seeker. On a gimbal the seeker is decoupled, so the saturation cost is much lower. Still a clean thing to
  design, no longer urgent.
- **Passive range** (§6.2) — coarse (28%) and needs a maneuver that costs the intercept. Genuinely useful
  only if we ever need a size-free range; the commit gate now has the miss-phase cue instead. **Parked.**
- **`seeker_core` migration** — still the target architecture for the FPGA port, still not worth doing until
  the physics and the mount are settled. **Unchanged: parked until GAP 2 informs it.**

---

## The honest critical path

```
parts in hand ─▶ GAP 1 (build + flash, ~1–2 wks) ─▶ GAP 2 (bench HIL → full HIL, ~2 wks)
                                                          │
                                                          ▼
                                              GAP 3 (first flights, field, ~1–2 wks)
```

**Everything real is downstream of GAP 1, and GAP 1 is gated on procurement, not on us.** The software is
far ahead of the hardware — which is the good problem to have, but it means the remaining calendar time is
dominated by build, integration, and flight, not by writing code.

## What could still overturn the plan (stated so it is not a surprise)

1. **Real thermal ≠ rendered thermal.** The sim's 10/10 is on clean rendered frames. Real FT640 AGC + clutter
   + vibration could pull CPA out past 1.5 m. GAP 2 exists to find this early. This is the biggest unknown.
2. **The doctrine target must actually be weakly-maneuvering.** Everything rests on ≤~0.12–0.2 g of target
   maneuver (the 3-to-1 rule against our plant). A target that jinks harder is out of reach on this airframe,
   full stop — no amount of the software above changes it.
3. **The camera-orientation question** (up-looking vs boresight-forward) still needs an owner decision; the
   recent sim assumes up-looking. Cheap to settle, but it changes the flight geometry.

## Bottom line

The project is **not** close to done, but it is close to a specific, honest milestone: a **first
hardware-in-the-loop closure on the real seeker**. That is the next thing worth its cost, it is mostly gated
on parts rather than code, and it is the point where the sim's promises meet the real sensor. Everything after
it is field work with irreducible risk. Everything before it — the front half of the system, and now a
sim-closed back half on a buildable configuration — is done and measured.
