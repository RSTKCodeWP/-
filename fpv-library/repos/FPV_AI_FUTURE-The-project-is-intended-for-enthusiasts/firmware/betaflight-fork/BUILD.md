# Betaflight FPV-AI Fork — Build & Flash Guide (Block-3)

This builds the FPV-AI fork described in `PATCH.md`. It is **safety-critical kinetic firmware**. Do not
deviate, and do not skip the bench V&V gates before any powered test.

> **CRITICAL — line numbers will not match.** `PATCH.md` anchors every change on a **function name and
> quoted surrounding code**, not on absolute line numbers. Betaflight's `master` moves constantly. The
> first build step below pins a known tag so the function bodies in `PATCH.md` match what you edit.
> After checkout, locate each change by `grep`-ing for the function name, NOT by jumping to a line.

---

## 0. Prerequisites

- Linux or macOS (WSL2 works). ~3 GB free.
- `git`, `make`, `ruby` (config generation), and the ARM toolchain `arm-none-eabi-gcc`.
  - Betaflight's `make arm_sdk_install` will fetch a pinned toolchain for you — preferred over a
    system toolchain to avoid version skew.
- A flashing tool: **Betaflight Configurator** (GUI, recommended for first flash) or `dfu-util`.

```bash
# Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y git make ruby dfu-util
# macOS
brew install git make ruby dfu-util
```

---

## 1. Clone and PIN the exact Betaflight tag

**Do not build off a moving `master`.** Pick the release your fleet/Configurator expects and pin it.
Recommended baseline: the latest `4.5.x` stable tag (it contains PR #13380 — `msp_override_failsafe` +
`rxMspOverrideFrameStatus()` — which `PATCH.md` builds on).

```bash
git clone https://github.com/betaflight/betaflight.git
cd betaflight

# List candidate tags and pick one (example shown; choose your actual fleet version):
git tag --list '4.5.*' | sort -V | tail
git checkout 4.5.1            # <-- PIN. Record this exact tag in your build log.
git switch -c fpv-ai-fork     # work on a named branch

# Install the pinned ARM toolchain Betaflight expects:
make arm_sdk_install
```

**Record the pinned commit** so the fork is reproducible:

```bash
git rev-parse HEAD            # paste this into the build log / engagement record
```

> If your fleet runs 4.6.x or a different tag, pin that instead. Then re-verify each `PATCH.md` snippet
> against the checked-out source — the function names are stable across 4.5/4.6 but exact bodies may
> differ slightly (see §6).

---

## 2. Identify your target

List targets and pick the one matching your flight controller:

```bash
make targets        # or: ls src/main/target
```

Confirm the target enables the three required symbols (`PATCH.md` §8):

```bash
grep -RnE 'USE_RX_MSP\b|USE_RX_MSP_OVERRIDE|USE_SERIALRX_CRSF' \
  src/main/target/<YOUR_TARGET>/ src/main/target/common_post.h src/main/config/
```

If `USE_RX_MSP_OVERRIDE` is **not** present for your target, add it to the target's `target.h` (or the
common config) — without it the entire fork design (override merge path) does not compile. ELRS/CRSF
support (`USE_SERIALRX_CRSF`) and `USE_RX_MSP` are enabled on essentially all full-flash 4.5 targets.

---

## 3. Apply the changes

Work through `PATCH.md` **section by section**, locating each edit by function name. Suggested order
(dependencies first):

```bash
# 1. Config field + default + CLI binding (PATCH.md §1, §5 CLI reject)
$EDITOR src/main/pg/rx.h          # add msp_override_timeout_ms to rxConfig_s
$EDITOR src/main/pg/rx_pg.c       # default = 200
$EDITOR src/main/cli/settings.c   # bind msp_override_timeout_ms; reject arm/kill bits in mask

# 2. Heartbeat state + helpers (PATCH.md §1b) and prototypes
$EDITOR src/main/rx/rx.h          # prototypes
$EDITOR src/main/rx/rx.c          # mspOverrideLastHeartbeatUs + Fresh()/NoteHeartbeat()

# 3. Heartbeat ingress + validation (PATCH.md §2)
$EDITOR src/main/msp/msp.c        # MSP_SET_RAW_RC: validate frame, rxMspOverrideNoteHeartbeat()

# 4. Watchdog: override OFF on stale (PATCH.md §3a, §3b)
$EDITOR src/main/rx/msp_override.c  # add && rxMspOverrideHeartbeatFresh(micros())
$EDITOR src/main/rx/rx.c            # rxFrameCheck() keep-alive: require fresh heartbeat

# 5. #13416 fix (PATCH.md §4)
$EDITOR src/main/rx/rx.c            # detectAndApplySignalLossBehaviour(): fresh-override -> valid

# 6. Mask safety strip (PATCH.md §5)
$EDITOR src/main/rx/rx.c            # rxInit(): strip arm/kill bits from msp_override_channels_mask

# 7. Arm edge + ELRS kill latch (PATCH.md §6)
$EDITOR src/main/fc/core.c          # updateArmingStatus(): boot inhibit + dominant/latched ELRS kill
$EDITOR src/main/fc/runtime_config.h # (optional) ARMING_DISABLED_OPERATOR_KILL
```

Helper to find each anchor quickly:

```bash
grep -RnE 'rxMspOverrideReadRawRc|detectAndApplySignalLossBehaviour|rxFrameCheck|updateArmingStatus|MSP_SET_RAW_RC|rxInit' src/main
```

Commit in small, reviewable steps (one `PATCH.md` section per commit) so a safety reviewer can diff
each change against its rationale.

---

## 4. Build

```bash
make TARGET=<YOUR_TARGET>
# parallel:
make TARGET=<YOUR_TARGET> -j$(nproc)
```

Output: `obj/betaflight_<version>_<TARGET>.hex`.

Sanity-check the symbols actually compiled in (not stripped by a slim config):

```bash
grep -RnE 'msp_override_timeout_ms|rxMspOverrideHeartbeatFresh|rxMspOverrideNoteHeartbeat' src/main
# and confirm no #if removed your block:
make TARGET=<YOUR_TARGET> 2>&1 | grep -iE 'warning|error'
```

A clean build with **zero warnings on the touched files** is required before flashing kinetic firmware.

---

## 5. Flash

**Option A — Betaflight Configurator (recommended for first flash):**
1. Configurator → *Firmware Flasher* → *Load Firmware [Local]* → select your built `.hex`.
2. Put the FC in DFU (bootloader) mode (BOOT button, or "No reboot sequence" + the bootloader jumper).
3. *Flash Firmware*. Verify it boots and reports your version in *Setup*.

**Option B — `dfu-util` (CLI):**
```bash
dfu-util -a 0 -s 0x08000000:leave -D obj/betaflight_<version>_<TARGET>.hex   # or the .bin
# (use the .bin variant with the correct load address for your MCU; the Configurator path avoids
#  address mistakes and is safer for a first flash.)
```

---

## 6. Post-flash configuration (CLI)

Set the override topology to match `PATCH.md` / `fork_model.py`. **RPYT only in the mask; arm/kill AUX
excluded.**

```
# Serial RX = ELRS/CRSF on your UART (example UART2):
feature -RX_PARALLEL_PWM
feature -RX_PPM
feature RX_SERIAL
set serialrx_provider = CRSF
serial 1 64 115200 57600 0 115200      # 64 = SERIAL_RX bit; adjust UART index/bauds

# MSP override: RPYT (channels 0-3) only -> mask = 0b1111 = 15. NEVER include AUX1/AUX2.
set msp_override_channels_mask = 15
set msp_override_failsafe = ON
set msp_override_timeout_ms = 200      # FPV-AI fork heartbeat window (mirrors msp_timeout_s=0.2)

# Modes: assign BOXMSPOVERRIDE to a Pi/operator-controlled AUX; assign BOXARM to ELRS AUX1.
# ELRS independent kill (AUX2) -> failsafe KILL mode (PATCH.md §6b-i preferred):
set failsafe_switch_mode = KILL
# (assign BOXFAILSAFE to ELRS AUX2 in the Modes tab / `aux` lines.)

save
```

Confirm the mask-safety strip did its job — if you deliberately try a bad mask, the fork must refuse:

```
set msp_override_channels_mask = 63    # includes AUX1(16)+AUX2(32) -> should be rejected/stripped
get msp_override_channels_mask         # must read back WITHOUT bits 4 and 5 set (i.e. 15, not 63)
status                                 # an arm-blocking fault should be present if a bad blob slipped in
```

---

## 7. Bench V&V — MANDATORY before any thrust (props OFF, then tethered)

Reproduce, on real hardware, the three gates from `test_fork_model.py`. Use the MSP RAW_RC view +
motor test (props removed) and a current clamp / smart-ESC telemetry to watch motor output.

- **V&V-1 — ELRS kill while MSP overrides:** with `BOXMSPOVERRIDE` active and the Pi driving RPYT,
  raise ELRS AUX2 (kill). The FC must disarm **immediately** and **latch** (re-arm requires AUX2 low
  AND an arm-switch low→high re-commit). `PATCH.md` §5 + §6.
- **V&V-2 — MSP heartbeat loss → ELRS handover ≤200 ms:** while overriding, stop the MSP stream.
  Within ~200 ms, override must drop and the masked channels must follow live ELRS sticks (no frozen
  throttle). `PATCH.md` §3.
- **V&V-3 — motors keep running after arm under MSP override (#13416):** arm via ELRS, engage
  `BOXMSPOVERRIDE`, drive throttle via MSP with the operator NOT touching ELRS sticks. Motors must
  follow the MSP throttle and must **not** cut to `failsafe_throttle`. `PATCH.md` §4.
- **Arm edge:** power up with the arm switch already HIGH — the craft must **refuse** to arm until the
  switch is cycled LOW then HIGH. `PATCH.md` §6a.

Only after all four pass on the bench, AND the independent HW-kill MCU (separate deliverable) is
verified BELOW the FC, may you proceed to a tethered powered test over a surveyed/cleared keep-out
footprint.

---

## 8. Re-validating against a different Betaflight version

If you pin a tag other than the one `PATCH.md` was authored against (4.5.x master, fetched 2026-06-18),
re-confirm each anchor before editing:

```bash
# Confirm the structures/functions still exist with the expected shape:
grep -n 'msp_override_channels_mask\|msp_override_failsafe' src/main/pg/rx.h
grep -n 'rxMspOverrideReadRawRc' src/main/rx/msp_override.c
grep -n 'IS_RC_MODE_ACTIVE(BOXMSPOVERRIDE)' src/main/rx/rx.c
grep -n 'detectAndApplySignalLossBehaviour\|getRxfailValue\|failsafe_throttle' src/main/rx/rx.c
grep -n 'ARMING_DISABLED_ARM_SWITCH\|ARMING_DISABLED_NOT_DISARMED\|justGotRxBack' src/main/fc/core.c
grep -n 'MSP_SET_RAW_RC\|rxMspFrameReceive' src/main/msp/msp.c
```

If any function was renamed or refactored, update the corresponding `PATCH.md` section and re-derive the
edit from the **current** body before building. Never paste a snippet that no longer matches the
surrounding code — for kinetic firmware, a mismatched merge is a flight hazard.
