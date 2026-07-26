# Betaflight FPV-AI Fork — Patch Specification (Block-3, kinetic night-thermal interceptor)

**Status:** authoring spec. Safety-critical. Correctness over cleverness.
**Mirrors:** `fpv_ai/betaflight_link/fork_model.py` (the verified executable spec). Every behavioral
decision below has a 1:1 counterpart in that model — citations of the form `[fork_model.py:NN]`.
**Verified against:** Betaflight `master` source on `raw.githubusercontent.com/betaflight/betaflight/master/src/main/...`
fetched 2026-06-18. **Line numbers in this document are anchors against function names, NOT absolute
offsets — they WILL drift. Match on the quoted function signature and surrounding code, never on a raw
line number.** (See `BUILD.md` for how to pin the exact tag you build.)

---

## ⚠ Adversarial firmware-safety review — corrections (read before applying)

An independent firmware-safety review found the issues below. Items marked **[fixed in this doc]**
are already corrected here; items marked **[apply when you implement]** are non-negotiable when you
write the C against your Betaflight tag. Do **not** ship without all of them.

- **CRITICAL — §4 must not defeat an active failsafe / operator kill. [fixed in this doc].** The
  `thisChannelValid = true` override now also requires `!failsafeIsActive() && !boxFailsafeSwitchIsOn`.
  Without those, the MSP-override validity exemption would hold THROTTLE at the MSP value during an
  operator `BOXFAILSAFE` kill (the V&V-1 path) or any active failsafe — defeating the kill. The real
  master loop has a `failsafeIsActive()` branch and an unconditional `if (boxFailsafeSwitchIsOn) sample =
  getRxfailValue()` branch; gate against master's actual signals, not the simplified loop shown.
- **MAJOR — operator KILL must be a DEDICATED arming-disable, not `BOXFAILSAFE`. [apply when you
  implement].** Prefer §6b-ii: add a new sticky `ARMING_DISABLED_OPERATOR_KILL` flag set by a direct,
  mask-excluded `rcData[AUX2]` read in `updateArmingStatus()` that calls `disarm()`. Do **not** map the
  kill onto `BOXFAILSAFE` (§6b-i) — that conflates the operator kill with the normal RX-loss/panic
  signal that also drives `boxFailsafeSwitchIsOn`, creating cross-talk with the §4 gate above.
- **MAJOR — the mask-safety latch (§5) must use a STICKY flag. [apply when you implement].** Do **not**
  reuse `ARMING_DISABLED_RX_FAILSAFE` — it is a DYNAMIC flag the RX/failsafe subsystem sets and clears
  every cycle, so a one-shot set in `rxInit()` is immediately overwritten. Use a dedicated flag (e.g.
  `ARMING_DISABLED_MSP_MASK_BAD`) that the failsafe code never auto-clears.
- **Time source — use ONE clock. [apply when you implement].** Stamp and read the MSP heartbeat with the
  same source: pass `currentTimeUs` through to `rxMspOverrideReadRawRc()` rather than calling `micros()`
  inside it. (`currentTimeUs` derives from `micros()`, but keep them identical to avoid skew.)
- The independent HW-kill MCU had a **CRITICAL held-reset un-latch** bug — **already fixed** in
  `../hwkill-mcu/hwkill_mcu.ino` (the reset is now edge-triggered, cleared once per deliberate press).

---

## 0. Architecture decision (read first — this is the whole design)

Stock Betaflight selects **exactly one** RX provider at runtime in `rxInit()` via a first-match
feature cascade (`PARALLEL_PWM > PPM > SERIAL > MSP > SPI`). There is exactly one
`rcReadRawFn` / `rcFrameStatusFn` pair in `rxRuntimeState`. Because `FEATURE_RX_SERIAL` is tested
**before** `FEATURE_RX_MSP`, enabling the serial ELRS RX makes `RX_PROVIDER_MSP` unreachable. That is
the literal root of **issue #8292** (`RX_MSP` and `RX_SERIAL` are mutually exclusive).

**We do NOT make two providers run at once.** That would be the wrong fix. Instead:

- **ELRS / CRSF stays the sole RX provider** (`RX_PROVIDER_SERIAL`). It keeps its native serial
  failsafe and owns arm/disarm/kill on its own AUX channels.
- The Pi drives **roll/pitch/yaw/throttle only** through the existing **`USE_RX_MSP_OVERRIDE`** path
  (`BOXMSPOVERRIDE` + `msp_override_channels_mask`), which substitutes MSP values per-channel inside
  `readRxChannelsApplyRanges()` while leaving non-masked channels on the live ELRS link.
- This is exactly the topology `fork_model.py` models: ELRS kill is dominant and independent of MSP
  override `[fork_model.py:83-88]`.

The fork's job is therefore **not** to add a provider. It is to (1) make MSP-override coexistence the
default for this build, (2) add a real **~200 ms MSP-heartbeat watchdog** that the stock code lacks,
(3) fix #13416/#13374 so MSP-driven motors are not killed after arm, and (4) tighten the arm-edge +
ELRS-kill re-arm-inhibit latch to match `fork_model.py` exactly.

### Channel-mask invariant (the structural precondition for V&V-1)

`msp_override_channels_mask` MUST cover **only** RPYT (and optional AI-flight AUX), and MUST **exclude**
the ELRS arm AUX and the ELRS kill AUX. This is what guarantees the operator's serial RX keeps
independent arm/kill authority while the Pi overrides the flight axes. We enforce this at config-load
(§5) so it cannot be misconfigured into an unsafe state.

Concrete bench wiring this spec assumes (matches `ForkConfig` in `fork_model.py`):

| Channel | Source            | In override mask? |
|---------|-------------------|-------------------|
| Roll / Pitch / Yaw / Throttle (chan 0–3) | MSP (Pi) | **YES** |
| AUX1 = arm (`arm_aux_us=1700`)            | ELRS     | **NO** |
| AUX2 = kill (`kill_aux_us=1700`)          | ELRS     | **NO** |

---

## 1. New config fields and constants

### 1a. `src/main/pg/rx.h` — add the heartbeat-timeout config field

**File:** `src/main/pg/rx.h`
**Struct:** `rxConfig_s` (verified: it has `uint32_t msp_override_channels_mask;` and
`uint8_t msp_override_failsafe;` already — there is **no** `rxProvider` field).

**WHY:** the MSP override path in stock has **no staleness check at all** — `rxMspOverrideReadRawRc()`
merrily returns the last `mspFrame[]` values forever. We need an explicit, configurable timeout so the
heartbeat window matches `ForkConfig.msp_timeout_s = 0.2` `[fork_model.py:32]`, and so it is auditable
in the CLI rather than buried as a literal.

```c
// add inside struct rxConfig_s, near msp_override_failsafe:
    uint16_t msp_override_timeout_ms;  // FPV-AI fork: MSP heartbeat staleness window.
                                       // >= this with no fresh MSP_SET_RAW_RC -> override OFF,
                                       // control handed back to the ELRS serial RX. (V&V-2)
```

**File:** `src/main/pg/rx_pg.c` (the PG_RESET / default block for `rxConfig`).
**WHY:** default it to 200 ms — the same value `fork_model.py` enforces, and comfortably **under** the
stock 150 ms serial `RXLOSS_TRIGGER_INTERVAL`... note: 200 ms > 150 ms. This is intentional and
explained in §3 (the watchdog governs *override fallback*, not the ELRS RXLOSS timer). 200 ms is the
**maximum** MSP silence we tolerate before forcing ELRS control; keep it as the spec value and verify
on the bench.

```c
    .msp_override_timeout_ms = 200,    // FPV-AI fork: mirror fork_model.py msp_timeout_s = 0.2
```

> Kinetic-safety note on `msp_override_failsafe`: `fork_model.py` requires a fresh link to keep motors
> alive and hands back to ELRS when MSP goes stale `[fork_model.py:97-103]`. We therefore keep
> `msp_override_failsafe` semantics but gate the keep-alive on our own heartbeat (§3). Do **not** ship a
> build where stale/garbage MSP can hold the link "valid" indefinitely.

### 1b. `src/main/rx/rx.c` — module constants and heartbeat state

**File:** `src/main/rx/rx.c`, top of file near the existing `RXLOSS_TRIGGER_INTERVAL` define and the
`static bool rxSignalReceived` declaration.

**WHY:** a single source of truth for the heartbeat timestamp, kept **separate** from
`needRxSignalBefore` (which tracks the ELRS provider and must NOT be repurposed — that is the whole
point of keeping ELRS alive underneath, per #8292).

```c
#if defined(USE_RX_MSP_OVERRIDE)
// FPV-AI fork: independent MSP heartbeat. Stamped on every accepted MSP_SET_RAW_RC frame.
// Separate from needRxSignalBefore: that timer follows the ELRS serial provider and must keep
// ELRS alive underneath the override. This one decides ONLY whether MSP override is still trusted.
static timeUs_t mspOverrideLastHeartbeatUs = 0;
static bool     mspOverrideHeartbeatValid  = false;  // false until first finite, in-range frame

bool rxMspOverrideHeartbeatFresh(timeUs_t currentTimeUs)
{
    if (!mspOverrideHeartbeatValid) {
        return false;  // never received a valid MSP frame -> not fresh (default-deny)
    }
    const timeDelta_t age = cmpTimeUs(currentTimeUs, mspOverrideLastHeartbeatUs);
    return age >= 0 && age < (timeDelta_t)(rxConfig()->msp_override_timeout_ms * 1000);
}

void rxMspOverrideNoteHeartbeat(timeUs_t currentTimeUs)
{
    mspOverrideLastHeartbeatUs = currentTimeUs;
    mspOverrideHeartbeatValid  = true;
}
#endif
```

Add prototypes to `src/main/rx/rx.h`:

```c
#if defined(USE_RX_MSP_OVERRIDE)
bool rxMspOverrideHeartbeatFresh(timeUs_t currentTimeUs);
void rxMspOverrideNoteHeartbeat(timeUs_t currentTimeUs);
#endif
```

**Default-deny rationale (mirrors `hwkill.py` and `fork_model._fresh`):** before any valid frame,
`mspOverrideHeartbeatValid == false` so `rxMspOverrideHeartbeatFresh()` returns false — exactly
`ForkModel._fresh(last=None, ...) -> False` `[fork_model.py:117-121]`. Override is never "on" until a
real, finite, in-range MSP frame has arrived.

---

## 2. Heartbeat ingress + non-finite/out-of-range rejection (V&V-2 source of truth)

**File:** `src/main/msp/msp.c`
**Function:** `static mspResult_e mspProcessInCommand(mspDescriptor_t srcDesc, int16_t cmdMSP, sbuf_t *src)`
**Case:** `MSP_SET_RAW_RC` (verified current body):

```c
case MSP_SET_RAW_RC:
#ifdef USE_RX_MSP
    {
        uint8_t channelCount = dataSize / sizeof(uint16_t);
        if (channelCount > MAX_SUPPORTED_RC_CHANNEL_COUNT) {
            return MSP_RESULT_ERROR;
        } else {
            uint16_t frame[MAX_SUPPORTED_RC_CHANNEL_COUNT];
            for (int i = 0; i < channelCount; i++) {
                frame[i] = sbufReadU16(src);
            }
            rxMspFrameReceive(frame, channelCount);
        }
    }
#endif
    break;
```

**CHANGE — validate the masked flight channels BEFORE stamping the heartbeat:**

**WHY:** `hwkill.py` and `fork_model.msp_rc()` both refuse to refresh freshness on a non-finite input
`[fork_model.py:68-71]`. A malformed/garbage RC frame must NOT count as a heartbeat, or stale-but-noisy
MSP could hold the link "fresh" and defeat V&V-2. We bound each masked channel to the configured
`rx_min_usec..rx_max_usec` (the same window `rxMspOverrideReadRawRc()` already clamps to). A frame that
fails validation is accepted into `mspFrame[]` (so `rxMspOverrideReadRawRc`'s own `constrainf` still
sanitizes it) but does **not** refresh the heartbeat — so the watchdog will trip and hand back to ELRS.

```c
case MSP_SET_RAW_RC:
#ifdef USE_RX_MSP
    {
        uint8_t channelCount = dataSize / sizeof(uint16_t);
        if (channelCount > MAX_SUPPORTED_RC_CHANNEL_COUNT) {
            return MSP_RESULT_ERROR;
        } else {
            uint16_t frame[MAX_SUPPORTED_RC_CHANNEL_COUNT];
            for (int i = 0; i < channelCount; i++) {
                frame[i] = sbufReadU16(src);
            }
            rxMspFrameReceive(frame, channelCount);
#if defined(USE_RX_MSP_OVERRIDE)
            // FPV-AI fork: only a structurally valid frame refreshes the override heartbeat.
            // Mirrors fork_model.msp_rc(): a non-finite / out-of-range sample is NOT a heartbeat.
            bool frameValid = (channelCount >= 4);  // need at least R,P,Y,T present
            const uint32_t mask = rxConfig()->msp_override_channels_mask;
            for (int i = 0; i < channelCount && frameValid; i++) {
                if (mask & (1U << i)) {  // only validate channels we will actually override
                    if (frame[i] < rxConfig()->rx_min_usec || frame[i] > rxConfig()->rx_max_usec) {
                        frameValid = false;
                    }
                }
            }
            if (frameValid) {
                rxMspOverrideNoteHeartbeat(micros());
            }
#endif
        }
    }
#endif
    break;
```

> Note: `rxMspFrameReceive()` (in `src/main/rx/msp.c`) already zero-fills channels beyond
> `channelCount` and sets `rxMspFrameDone`/`rxMspOverrideFrameDone`. We do not change it. The heartbeat
> is layered on top so the validity decision lives at the ingress, where we still have the raw frame.

---

## 3. The watchdog: stale MSP → override OFF → ELRS regains control (V&V-2)

This is the core failover. Two coordinated edits.

### 3a. `src/main/rx/msp_override.c` — gate the per-channel override on heartbeat freshness

**File:** `src/main/rx/msp_override.c`
**Function:** `uint16_t rxMspOverrideReadRawRc(const rxRuntimeState_t *rxRuntimeState, const rxConfig_t *rxConfig, uint8_t chan)`
**Verified current body:**

```c
uint16_t rxMspOverrideReadRawRc(const rxRuntimeState_t *rxRuntimeState, const rxConfig_t *rxConfig, uint8_t chan)
{
    uint16_t rxSample = (rxRuntimeState->rcReadRawFn)(rxRuntimeState, chan);
    uint16_t overrideSample = constrainf(rxMspReadRawRC(rxRuntimeState, chan),
                                         rxConfig->rx_min_usec, rxConfig->rx_max_usec);
    bool override = (1 << chan) & rxConfig->msp_override_channels_mask;
    if (IS_RC_MODE_ACTIVE(BOXMSPOVERRIDE) && override) {
        return overrideSample;
    } else {
        return rxSample;
    }
}
```

**CHANGE — add `&& rxMspOverrideHeartbeatFresh(micros())` to the gate:**

**WHY:** this single conjunction is V&V-2. When the MSP heartbeat is stale (Pi hung, MSP link cut,
garbage frames), **every** masked channel instantly falls back to `rxSample` — the live ELRS value —
because the ELRS serial provider never stopped running underneath. This is exactly
`fork_model.update()` step (4): "MSP stale but ELRS fresh -> RXFAIL handover to the operator radio"
`[fork_model.py:101-103]`. No frozen throttle, no held sticks.

```c
uint16_t rxMspOverrideReadRawRc(const rxRuntimeState_t *rxRuntimeState, const rxConfig_t *rxConfig, uint8_t chan)
{
    uint16_t rxSample = (rxRuntimeState->rcReadRawFn)(rxRuntimeState, chan);
    uint16_t overrideSample = constrainf(rxMspReadRawRC(rxRuntimeState, chan),
                                         rxConfig->rx_min_usec, rxConfig->rx_max_usec);
    bool override = (1 << chan) & rxConfig->msp_override_channels_mask;
    // FPV-AI fork: override only while the Pi heartbeat is FRESH. Stale -> fall back to the live
    // ELRS sample (rxSample). The ELRS serial provider has never stopped, so this is an instant,
    // glitch-free handover. (V&V-2; mirrors fork_model.py update() step 4.)
    if (IS_RC_MODE_ACTIVE(BOXMSPOVERRIDE) && override && rxMspOverrideHeartbeatFresh(micros())) {
        return overrideSample;
    } else {
        return rxSample;
    }
}
```

> `micros()` is already available in this translation unit via `drivers/time.h` (pulled in by the RX
> headers). If a build complains, add `#include "drivers/time.h"`.

### 3b. `src/main/rx/rx.c` — only let MSP keep the link "valid" while the heartbeat is fresh

**File:** `src/main/rx/rx.c`
**Function:** `FAST_CODE_NOINLINE void rxFrameCheck(timeUs_t currentTimeUs, timeDelta_t currentDeltaTimeUs)`
**Verified current MSP-override keep-alive block:**

```c
#if defined(USE_RX_MSP_OVERRIDE)
    if (IS_RC_MODE_ACTIVE(BOXMSPOVERRIDE) && rxConfig()->msp_override_channels_mask
        && rxConfig()->msp_override_failsafe) {
        if (rxMspOverrideFrameStatus() & RX_FRAME_COMPLETE) {
            rxSignalReceived = true;
            rxDataProcessingRequired = true;
            needRxSignalBefore = currentTimeUs + needRxSignalMaxDelayUs;
        }
    }
#endif
```

**CHANGE — add the freshness conjunction so a stale stream can NEVER re-assert `rxSignalReceived`:**

**WHY (V&V-2 + #13374):** stock will set `rxSignalReceived = true` as long as a single
`rxMspOverrideFrameStatus()` reports `RX_FRAME_COMPLETE` since the last poll — there is no age check.
On a healthy MSP stream that is correct (it's what keeps motors alive — §4). But it means a Pi that
sends one last frame and then hangs would hold the link "received" for a full
`needRxSignalMaxDelayUs`. We require the heartbeat be **fresh** to refresh the signal. When stale, this
block does nothing; `rxSignalReceived` then reflects the ELRS provider alone, and if ELRS is also gone
the normal serial RXLOSS path runs. This is `fork_model.update()` steps (2)+(4)
`[fork_model.py:91-103]`.

```c
#if defined(USE_RX_MSP_OVERRIDE)
    if (IS_RC_MODE_ACTIVE(BOXMSPOVERRIDE) && rxConfig()->msp_override_channels_mask
        && rxConfig()->msp_override_failsafe
        && rxMspOverrideHeartbeatFresh(currentTimeUs)) {   // FPV-AI fork: fresh heartbeat REQUIRED
        if (rxMspOverrideFrameStatus() & RX_FRAME_COMPLETE) {
            rxSignalReceived = true;
            rxDataProcessingRequired = true;
            needRxSignalBefore = currentTimeUs + needRxSignalMaxDelayUs;
        }
    }
#endif
```

**Timing relationship, stated precisely:**
- `RXLOSS_TRIGGER_INTERVAL` (ELRS serial RXLOSS) = `150 * 1000` us — unchanged.
- `msp_override_timeout_ms` (our watchdog) = `200` ms default.
- The watchdog governs **override trust / handover**, not the ELRS RXLOSS timer. If MSP goes stale
  while ELRS is healthy: override turns off at ≤200 ms (§3a) and ELRS flies — **no failsafe**, because
  the ELRS provider is valid. If BOTH are stale: ELRS's own 150 ms RXLOSS drives the normal failsafe
  state machine and disarms. Both outcomes match `fork_model.py` (step 4 = handover; step 2 = failsafe
  disarm).

---

## 4. #13416 fix — MSP override must NOT stop motors after arm (V&V-3)

**File:** `src/main/rx/rx.c`
**Function:** `static void detectAndApplySignalLossBehaviour(void)` (called from
`calculateRxChannelsAndUpdateFailsafe()`).

**The bug (verified mechanism):** with MSP override layered on a serial provider, if the operator is
not transmitting on the ELRS serial RX, `rxSignalReceived` goes false at 150 ms. Then
`detectAndApplySignalLossBehaviour()` computes `rxFlightChannelsValid = rxSignalReceived && !boxFailsafeSwitchIsOn`,
and for each flight channel past its `validRxSignalTimeout[channel]` (300 ms) it substitutes
`getRxfailValue()`, with **THROTTLE forced to `failsafeConfig()->failsafe_throttle`** — motors cut even
though MSP is correctly overwriting `rcData[]`. This is precisely issue #13416 (RAW_RC correct, MOTORS
dead). PR #13380's keep-alive (§3b) is the stock partial fix, but it only fires when
`msp_override_failsafe` is set AND `BOXMSPOVERRIDE` is asserted at that instant.

**CHANGE — when a channel is MSP-overridden AND the heartbeat is fresh, treat it as valid and skip the
failsafe substitution for that channel:**

**WHY:** the THROTTLE-to-`failsafe_throttle` line is the exact place stock kills the motors. For a
channel the Pi is actively and freshly driving, the correct sample is the MSP value, not
`getRxfailValue()`. We gate strictly on `rxMspOverrideHeartbeatFresh()` so this can NEVER hold motors
alive on a dead Pi — that's the #13374/#13416 safety boundary. This realizes
`fork_model.update()` step (3): "MSP fresh -> armed motors keep being driven" `[fork_model.py:96-99]`.

Locate the per-channel loop. Conceptually stock looks like (names per current master; match the
function, not the line):

```c
for (channel = 0; channel < rxChannelCount; channel++) {
    ...
    bool thisChannelValid = rxFlightChannelsValid && isPulseValid(sample);
    if (thisChannelValid) {
        validRxSignalTimeout[channel] = currentTimeMs + MAX_INVALID_PULSE_TIME_MS;
    }
    if (!thisChannelValid) {
        if (cmp32(currentTimeMs, validRxSignalTimeout[channel]) < 0) {
            sample = rcData[channel];                 // hold last good
        } else {
            sample = getRxfailValue(channel);         // THROTTLE -> failsafe_throttle  <-- #13416
            ...
        }
    }
    rcData[channel] = sample;
}
```

Insert the override-fresh override of `thisChannelValid`:

```c
for (channel = 0; channel < rxChannelCount; channel++) {
    ...
    bool thisChannelValid = rxFlightChannelsValid && isPulseValid(sample);

#if defined(USE_RX_MSP_OVERRIDE)
    // FPV-AI fork (#13416 fix / V&V-3): a channel the Pi is actively + freshly overriding is VALID.
    // The MSP value (already in `sample` via rxMspOverrideReadRawRc) must NOT be replaced by
    // getRxfailValue()/failsafe_throttle. Gated on a FRESH heartbeat so a dead Pi never holds motors.
    if (IS_RC_MODE_ACTIVE(BOXMSPOVERRIDE)
        && (rxConfig()->msp_override_channels_mask & (1U << channel))
        && rxMspOverrideHeartbeatFresh(micros())
        // SAFETY (adversarial-review CRITICAL fix): the validity exemption must NOT apply when
        // the FC is in ACTIVE failsafe or the operator has forced failsafe via the switch
        // (boxFailsafeSwitchIsOn). The real master loop has a failsafeIsActive() branch and an
        // UNCONDITIONAL `if (boxFailsafeSwitchIsOn) sample = getRxfailValue()` branch; without these
        // two guards the exemption would hold THROTTLE at the MSP value during an operator
        // BOXFAILSAFE kill (the V&V-1 path) or any active failsafe -- defeating the kill. Gate on
        // master's actual signals so the operator's failsafe/kill always wins.
        && !failsafeIsActive()
        && !boxFailsafeSwitchIsOn) {
        thisChannelValid = true;
    }
#endif

    if (thisChannelValid) {
        validRxSignalTimeout[channel] = currentTimeMs + MAX_INVALID_PULSE_TIME_MS;
    }
    if (!thisChannelValid) {
        if (cmp32(currentTimeMs, validRxSignalTimeout[channel]) < 0) {
            sample = rcData[channel];
        } else {
            sample = getRxfailValue(channel);
            ...
        }
    }
    rcData[channel] = sample;
}
```

**Bound the blast radius:** because the mask excludes arm/kill AUX (§0, enforced in §5), this override
of validity applies ONLY to RPYT (+ optional AI AUX). The ELRS arm/kill channels are never marked
"valid by MSP" — they follow the live ELRS link and the real failsafe path, which is what keeps V&V-1
intact. And because the gate requires a fresh heartbeat, a stale Pi instantly loses this exemption and
the normal failsafe substitution resumes — control returns to ELRS / failsafe.

> **Do not** add a disarm path here. Per the research and #13416's lesson: the MSP/override path must
> never itself stop motors or disarm. Disarm authority belongs to (a) the ELRS-driven `BOXARM`/kill in
> `fc/core.c` and (b) the `failsafe.c` state machine. Keeping these separate avoids double-handling.

---

## 5. Channel-mask safety enforcement (the precondition for V&V-1)

**File:** `src/main/rx/rx.c`
**Function:** `void rxInit(void)` — at the end, after the provider switch and after
`rxMspOverrideInit()` is called (under `USE_RX_MSP_OVERRIDE`).

**WHY:** V&V-1 ("ELRS AUX-kill disarms WHILE MSP overrides") is only structurally possible if the arm
and kill AUX channels are **never** in `msp_override_channels_mask`. A misconfiguration that put them in
the mask would let the Pi overwrite the operator's kill — catastrophic for a kinetic build. We refuse to
let that configuration take effect.

Add a compile-time mapping of the ELRS arm/kill AUX channel indices and clear them from the mask at
init (and reject at config-save in CLI). Channel indices: AUX1 = index 4, AUX2 = index 5 (RPYT = 0–3).
These mirror `ForkConfig.arm_aux_us` (AUX1) and `ForkConfig.kill_aux_us` (AUX2) in `fork_model.py`.

```c
#if defined(USE_RX_MSP_OVERRIDE)
// FPV-AI fork: the ELRS arm AUX (AUX1=idx4) and kill AUX (AUX2=idx5) must NEVER be overridden by MSP,
// or the operator loses independent disarm/kill authority (V&V-1). Default-deny: strip them from the
// mask regardless of what was configured. Mirrors fork_model.py, where elrs_kill is read ONLY from the
// live ELRS channels and is dominant over MSP override [fork_model.py:83-88].
#define FPV_AI_ELRS_ARM_CHANNEL_INDEX  4   // AUX1
#define FPV_AI_ELRS_KILL_CHANNEL_INDEX 5   // AUX2
    const uint32_t forbiddenMask = (1U << FPV_AI_ELRS_ARM_CHANNEL_INDEX)
                                 | (1U << FPV_AI_ELRS_KILL_CHANNEL_INDEX);
    if (rxConfigMutable()->msp_override_channels_mask & forbiddenMask) {
        rxConfigMutable()->msp_override_channels_mask &= ~forbiddenMask;
        // Raise a DEDICATED, STICKY arm-blocking fault so the misconfig is visible on the OSD and the
        // craft refuses to arm until the operator fixes the mask.
        // CORRECTED (adversarial review MAJOR): do NOT use ARMING_DISABLED_RX_FAILSAFE here -- it is a
        // DYNAMIC flag the RX/failsafe subsystem sets and CLEARS every cycle from live RX health, so a
        // one-shot set in rxInit() is immediately overwritten and the protection vanishes. Use a new
        // dedicated flag that nothing auto-clears:
        setArmingDisabled(ARMING_DISABLED_MSP_MASK_BAD); // new sticky flag; add to armingDisableFlags_e
    }
#endif
```

Mirror this as a hard reject in the CLI setter (`src/main/cli/settings.c` /
`src/main/cli/cli.c` `set` handler for `msp_override_channels_mask`) so the bad value can't be saved at
all. **WHY both:** belt-and-suspenders — the CLI reject prevents persisting the unsafe value; the
`rxInit()` strip protects against a config blob flashed/restored out-of-band.

---

## 6. Arm-switch low→high EDGE + ELRS-kill re-arm-inhibit latch (V&V-1)

**File:** `src/main/fc/core.c`
**Functions:** `updateArmingStatus(void)`, `void tryArm(void)`, `void disarm(flightLogDisarmReason_e reason)`.

### 6a. Confirm the stock edge guard (mostly already correct — we make it strict)

**Verified stock `updateArmingStatus()` logic:**

```c
if (!isUsingSticksForArming()) {
    static bool hadRx = false;
    const bool haveRx = isRxReceivingSignal();
    const bool justGotRxBack = !hadRx && haveRx;
    if (justGotRxBack && IS_RC_MODE_ACTIVE(BOXARM)) {
        setArmingDisabled(ARMING_DISABLED_NOT_DISARMED);     // RX came back with arm already HIGH -> block
    } else if (haveRx && !IS_RC_MODE_ACTIVE(BOXARM)) {
        unsetArmingDisabled(ARMING_DISABLED_NOT_DISARMED);   // arm switch observed LOW -> allow next edge
    }
    hadRx = haveRx;
}
...
if (isArmingDisabled() && !ignoreGyro && !ignoreThrottle && IS_RC_MODE_ACTIVE(BOXARM)) {
    setArmingDisabled(ARMING_DISABLED_ARM_SWITCH);
} else if (!IS_RC_MODE_ACTIVE(BOXARM)) {
    unsetArmingDisabled(ARMING_DISABLED_ARM_SWITCH);
}
```

This already enforces a low→high edge: a switch held HIGH while any disable is present latches
`ARMING_DISABLED_ARM_SWITCH` and only clears once `BOXARM` is observed LOW. **WHY this matters for us:**
it is the firmware analogue of `fork_model._arm_update()`'s rule — arm only on a rising edge with the
inhibit cleared `[fork_model.py:105-115]`. We keep it and add an explicit boot-time inhibit so a craft
that powers up with the arm channel already HIGH cannot auto-arm.

**CHANGE — set the inhibit at init:** in `init()`/`tryArm` setup or at the top of the first
`updateArmingStatus()` pass, ensure `ARMING_DISABLED_NOT_DISARMED` (or a dedicated new flag, §6c) is set
on boot so the first arm always requires a confirmed LOW→HIGH edge. Stock sets `ARMING_DISABLED_BOOT_GRACE_TIME`;
we additionally assert the not-disarmed inhibit until the arm switch is seen LOW once.

### 6b. ELRS independent kill — read it directly, make it dominant + latched

**WHY:** `fork_model.update()` evaluates the ELRS kill FIRST, disarms immediately, and **latches the
re-arm inhibit** so the kill survives even a subsequent ELRS dropout `[fork_model.py:83-88]`. We add a
dedicated read of the ELRS kill AUX (AUX2, index 5 — guaranteed NOT MSP-overridable per §5) and wire it
to an immediate disarm + a latched inhibit.

Two implementation options. **CORRECTED (adversarial review MAJOR): 6b-ii is PREFERRED.** Mapping the
operator kill onto `BOXFAILSAFE` (6b-i) conflates it with Betaflight's normal RX-loss/panic switch —
the SAME `boxFailsafeSwitchIsOn` signal the §4 gate keys off — creating cross-talk between "operator
kill" and "RX failsafe". Use the dedicated, independently-auditable `ARMING_DISABLED_OPERATOR_KILL`
path (6b-ii) so the kill is its own reason and never entangles with RX-loss handling. 6b-i is kept
below only as a fallback if a custom flag is undesirable.

**6b-i (DISCOURAGED — fallback only): map the ELRS kill AUX to `BOXFAILSAFE` in KILL mode.**
Set `failsafe_switch_mode = KILL` (`FAILSAFE_SWITCH_MODE_KILL`) and assign `BOXFAILSAFE` to the ELRS
AUX2. Verified behavior of `failsafeUpdateState()`: in `FAILSAFE_IDLE`, when the failsafe switch is on
and mode is KILL, it sets `failsafeState.active = true`, enables `FAILSAFE_MODE`, jumps straight to
`FAILSAFE_LANDED`, which calls `disarm(DISARM_REASON_FAILSAFE)` and
`setArmingDisabled(ARMING_DISABLED_FAILSAFE)`. That `ARMING_DISABLED_FAILSAFE` is the latch: re-arm is
inhibited until the failsafe RX-loss monitoring/recovery window clears AND a fresh BOXARM low→high edge
occurs. This is the firmware analogue of the sticky latch in `fork_model` and `hwkill.operator_kill()`.

> Because `BOXFAILSAFE` is read from the **live ELRS serial channel** and AUX2 is excluded from
> `msp_override_channels_mask` (§5), MSP override can never suppress this kill — satisfying V&V-1 even
> while MSP is actively overriding RPYT.

**6b-ii (PREFERRED — dedicated, independently-auditable kill, no RX-failsafe entanglement):** add a new
`ARMING_DISABLED_OPERATOR_KILL` flag and handle the kill in `updateArmingStatus()`:

```c
// FPV-AI fork: independent ELRS kill (AUX2). Read DIRECTLY from rcData (live ELRS, never MSP-overridden
// because AUX2 is excluded from msp_override_channels_mask). Dominant + latched, mirrors
// fork_model.update() step 1 [fork_model.py:83-88].
#define FPV_AI_ELRS_KILL_CHANNEL  (AUX2)        // = rcData index 5
#define FPV_AI_KILL_THRESHOLD_US  1700          // mirrors ForkConfig.kill_aux_us
static bool elrsKillLatched = false;            // sticky until a deliberate re-arm edge after release

if (rcData[FPV_AI_ELRS_KILL_CHANNEL] >= FPV_AI_KILL_THRESHOLD_US) {
    elrsKillLatched = true;
    if (ARMING_FLAG(ARMED)) {
        disarm(DISARM_REASON_SWITCH);           // immediate disarm even mid-MSP-override (V&V-1)
    }
}
if (elrsKillLatched) {
    setArmingDisabled(ARMING_DISABLED_OPERATOR_KILL);   // latch
    // Release the latch ONLY when kill is low AND the arm switch is observed LOW (a deliberate
    // re-commit). This is the fork_model rule: kill clears, then a fresh arm low->high edge is required.
    if (rcData[FPV_AI_ELRS_KILL_CHANNEL] < FPV_AI_KILL_THRESHOLD_US && !IS_RC_MODE_ACTIVE(BOXARM)) {
        elrsKillLatched = false;
        unsetArmingDisabled(ARMING_DISABLED_OPERATOR_KILL);
    }
}
```

Add `ARMING_DISABLED_OPERATOR_KILL` to the `armingDisableFlags_e` enum in `src/main/fc/runtime_config.h`
and to the OSD/CLI flag-name tables (so it shows up in `status`). **WHY a distinct flag:** kinetic
post-incident analysis must be able to distinguish "operator pressed kill" from "RX failsafe" on the
blackbox.

### 6c. The `disarm()` gate is unchanged but relied upon

**Verified:** `disarm(flightLogDisarmReason_e reason)` calls `DISABLE_ARMING_FLAG(ARMED);` — the single
gate the motor mixer keys off. We do not modify `disarm()`; both kill paths (6b-i, 6b-ii) route through
it. **WHY note it:** it confirms our kill is authoritative at the motor-output layer regardless of what
MSP override is doing to `rcData[RPYT]`.

---

## 7. The three V&V gates, mapped to these changes

| Gate | Requirement | Implemented by | `fork_model.py` anchor |
|------|-------------|----------------|------------------------|
| **V&V-1** | ELRS AUX-kill disarms WHILE MSP overrides; latches re-arm inhibit | §5 (kill AUX excluded from mask) + §6b (dominant, latched kill via BOXFAILSAFE-KILL or OPERATOR_KILL) | `[fork_model.py:83-88]` |
| **V&V-2** | MSP heartbeat loss → RXFAIL within ~200 ms → ELRS handover | §1 (timeout cfg) + §2 (validated ingress) + §3a (override OFF on stale) + §3b (no keep-alive on stale) | `[fork_model.py:91-103]` |
| **V&V-3** | MSP override does NOT stop motors after arm (#13416/#13374) | §4 (fresh-override channel treated valid; THROTTLE not forced to failsafe) + §3b (keep-alive on fresh) | `[fork_model.py:96-99]` |
| arm edge | arm requires low→high edge; no auto-re-arm | §6a (stock edge guard + boot inhibit) | `[fork_model.py:105-115]` |

**Bench order (props OFF, then tethered, before ANY thrust):** run the three V&V tests on hardware and
confirm they reproduce the `test_fork_model.py` results. The independent HW-kill MCU (separate
deliverable) must be present and verified BELOW the FC before any powered test — it is the guaranteed
backstop and does not depend on this fork.

---

## 8. Required build symbols

Ensure the target's `target.h` / `common_defaults_post.h` define:

```c
#define USE_RX_MSP            // MSP-as-RC ingress (rxMspFrameReceive + mspFrame[])
#define USE_RX_MSP_OVERRIDE   // the override merge path — REQUIRED, this is the whole design
#define USE_SERIALRX_CRSF     // ELRS / CRSF serial RX (the base provider)
```

Most full-flash 4.x targets already enable all three. Verify with `make TARGET=<t> DEBUG=...` and grep
the generated config. If a slim target omits `USE_RX_MSP_OVERRIDE`, add it to the target — without it
none of §3/§4 compiles and the design collapses to stock #8292 exclusivity.

---

## 9. Files touched (summary)

| File | Change |
|------|--------|
| `src/main/pg/rx.h` | add `msp_override_timeout_ms` to `rxConfig_s` (§1a) |
| `src/main/pg/rx_pg.c` | default `msp_override_timeout_ms = 200` (§1a) |
| `src/main/rx/rx.h` | prototypes for heartbeat helpers (§1b) |
| `src/main/rx/rx.c` | heartbeat state + `rxMspOverrideHeartbeatFresh/NoteHeartbeat` (§1b); fresh-gate the keep-alive block in `rxFrameCheck()` (§3b); fresh-override channel validity in `detectAndApplySignalLossBehaviour()` (§4); mask-safety strip in `rxInit()` (§5) |
| `src/main/msp/msp.c` | validate frame + stamp heartbeat in `MSP_SET_RAW_RC` (§2) |
| `src/main/rx/msp_override.c` | add `&& rxMspOverrideHeartbeatFresh(micros())` to `rxMspOverrideReadRawRc()` (§3a) |
| `src/main/cli/settings.c` | bind `msp_override_timeout_ms`; reject arm/kill bits in `msp_override_channels_mask` (§1a, §5) |
| `src/main/fc/core.c` | boot inhibit + ELRS-kill dominant/latched handling in `updateArmingStatus()` (§6) |
| `src/main/fc/runtime_config.h` | add `ARMING_DISABLED_OPERATOR_KILL` (§6b-ii, preferred) + `ARMING_DISABLED_MSP_MASK_BAD` (§5) to `armingDisableFlags_e`; add matching names to `armingDisableFlagNames[]` |

---

## 10. What is NOT changed, and why

- **`rxInit()` provider cascade** — left intact. We deliberately keep `RX_PROVIDER_SERIAL`. Adding
  `RX_PROVIDER_MSP` as a second provider would break the single-provider invariant and is the wrong fix
  for #8292.
- **`disarm()`** — left intact. It is the trusted motor gate; we route through it, we don't change it.
- **`rxMspFrameReceive()`** — left intact. Heartbeat validation is layered at the MSP ingress (§2), not
  inside the frame copy.
- **No MSP-path disarm.** Per #13416's lesson, the override path never stops motors or disarms;
  disarm authority stays with ELRS (`fc/core.c`) and the failsafe state machine (`failsafe.c`).
