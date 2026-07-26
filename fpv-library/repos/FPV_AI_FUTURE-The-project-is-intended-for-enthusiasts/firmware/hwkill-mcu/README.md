# Block-3 Independent Hardware-Kill MCU

`hwkill_mcu.ino` — self-contained firmware for a **dedicated watchdog MCU** that
physically gates motor power **below the flight controller**. It is the last
line of defense in the Block-3 kinetic night-thermal interceptor, and it is the
firmware realization of the verified spec
[`fpv_ai/betaflight_link/hwkill.py`](../../) (`HardwareKill`).

> **One sentence:** if no fresh *permit beacon* is present on this MCU's own RF
> link, or the operator pressed the mushroom, the motors lose power — regardless
> of what Betaflight, the ESCs, the Raspberry Pi, MSP, or ELRS are doing.

---

## 1. Why this exists (safety rationale)

A software failsafe is **necessary but not sufficient**. Betaflight *does* have a
failsafe — in the current master source it runs
`failsafeUpdateState()` (`src/main/flight/failsafe.c`), reaches `FAILSAFE_LANDED`,
and calls `disarm(DISARM_REASON_FAILSAFE)` + `setArmingDisabled(ARMING_DISABLED_FAILSAFE)`,
after which the motor layer (`src/main/drivers/motor.c`: `motorShutdown()`,
`motorDisable()`) tells the ESCs to stop. **But every one of those calls lives
inside the FC firmware and only *asks the ESCs* to stop.** None of it helps if:

- the FC firmware **hangs** (the scheduler that calls `failsafeUpdateState()`
  stops running) — issue #13416 / #13374 territory, where an MSP override or a
  failsafe-while-valid-MSP edge case can leave motors driven;
- the FC is mid-reboot, mis-flashed, or the MSP fork has a bug;
- an **ESC ignores or latches** the stop command (some 4-in-1 / smart ESCs hold
  last throttle on signal loss until reconfigured);
- the **Raspberry Pi (the AI) hangs** while it owns throttle via MSP;
- the dedicated **RF link is jammed** and the operator must abort.

This MCU answers all of those because it does **not depend on any of them**. It
**removes power** at the wire, on its **own clock**, from its **own RF link**.
It is wired in the motor-power path *below* the FC, so when it denies power the
motors cannot spin no matter what anything above it commands.

**Independence is the whole point.** This firmware never reads the FC, the Pi,
MSP, or ELRS. It listens only to its own dedicated permit-beacon channel and its
own timer.

### The four invariants (identical to `hwkill.py`)

| # | Invariant | Spec method | Firmware |
|---|-----------|-------------|----------|
| 1 | **DEFAULT-DENY** — power CUT unless a fresh permit beacon is actively received | `motor_power_enabled` returns `beacon.healthy()` | `beacon_seen=false` at boot → CUT; gate driven CUT in `setup()` before anything |
| 2 | **LOSS OF SIGNAL** — no valid beacon within `beacon_timeout` → CUT, autonomously | `Watchdog.healthy(now)` | `beacon_is_fresh()`: `now - last <= BEACON_TIMEOUT_MS` on the MCU's own clock |
| 3 | **OPERATOR KILL** — mushroom ABORT → CUT, **latched** until physical reset; a fresh beacon does **not** re-enable | `operator_kill()` / `reset()` | `g.latched` sticky; only `PIN_RESET_LATCH` held low clears it |
| 4 | **BAD CLOCK** — non-finite / backwards clock is not a permit → CUT | `0.0 <= (now-last) <= timeout` | wrap-safe unsigned delta; a "future"/backwards beacon → huge delta → CUT |

`BEACON_TIMEOUT_MS = 500` matches `HardwareKillConfig.beacon_timeout_s = 0.5`,
deliberately **longer** than the ~200 ms software link failsafe so the
controlled safe-ditch runs first and this independent cut is the guaranteed
backstop.

> **Operational constraint (design):** a *powered* cut may only ever occur over
> a surveyed / cleared ground keep-out footprint. The MCU guarantees the cut;
> mission planning guarantees *where* it lands.

---

## 2. Where it sits in the stack

```
   Launch console  ──(dedicated RF: PERMIT beacon @20Hz + KILL on mushroom)──►  [ HW-KILL MCU ]
   (separate from ELRS, separate from MSP)                                            │
                                                                                       │ drives
   Operator ELRS radio ──► ELRS RX ──► Betaflight FC ──► ESC(s) ──► MOTORS            │ PIN_POWER_GATE
   Raspberry Pi (AI)   ──► MSP UART ──►      ▲                         ▲              │
                                             │                         └──────────────┘
                                       (commands only)        power gated HERE (MOSFET / smart-ESC kill line)
```

The HW-kill gate is **in series with the motor-power feed, physically below the
FC and ESCs**. Everything above it can only *command*; this MCU controls whether
there is *power to command with*.

---

## 3. Pinout (Raspberry Pi Pico / RP2040 default)

> Pin numbers are RP2040 `GPxx` (= Arduino pin number on the earlephilhower
> arduino-pico core). All are `#define`-overridable at the top of the `.ino`.
> For an AVR/Arduino board, remap to any digital pins (and a hardware UART).

| Signal | `#define` | Default | Direction | Purpose |
|--------|-----------|---------|-----------|---------|
| **Motor-power gate** | `PIN_POWER_GATE` | GP15 | OUT | Drives the MOSFET gate / smart-ESC kill line. **HIGH = permit power, LOW = CUT** (set `POWER_GATE_ACTIVE_LOW=1` to invert) |
| Cut alarm | `PIN_CUT_ALARM` | GP16 | OUT | HIGH whenever power is CUT (buzzer/telltale) |
| Status LED | `PIN_STATUS_LED` | `LED_BUILTIN` | OUT | solid=powered, slow blink=cut, fast blink=latched |
| **Physical reset-latch** | `PIN_RESET_LATCH` | GP14 | IN (pull-up) | Momentary button to **GND**, held ≥`RESET_HOLD_MS` clears a latched kill |
| Beacon UART RX | `PIN_BEACON_RX` | GP5 (UART1 RX / `Serial2`) | IN | Dedicated permit-beacon receiver data line |
| Beacon UART TX | `PIN_BEACON_TX` | GP4 (UART1 TX) | OUT | unused (for completeness) |
| GND | — | — | — | **Common ground with the FC/ESC power stage and the beacon RX is mandatory** |

### Power-gate wiring (cut motor power BELOW the FC)

Pick **one** of these, sized for your motor current. The MCU output is the
*control* signal; the **switching element carries motor current**, never the MCU pin.

**A. Smart-ESC kill line (preferred if your ESC has one).**
Wire `PIN_POWER_GATE` → the ESC's dedicated kill/enable input (via a level
shifter / opto if voltages differ). Set polarity with `POWER_GATE_ACTIVE_LOW` so
that "permit" = ESC-enabled and "cut" = ESC-disabled. No high-current switching
on the board.

**B. High-side P-FET / load switch (cuts the whole motor-power rail).**
Use a logic-level high-side switch (e.g. a P-FET driven by a small N-FET, or an
integrated load switch IC) in the **+battery feed to the ESC(s)**.
`PIN_POWER_GATE` HIGH → switch ON (permit); LOW → switch OFF (cut). This is the
cleanest "power removed" guarantee. Add a flyback/TVS across the motor rail and a
gate pulldown so the switch defaults OFF if the MCU is unpowered.

**C. Low-side N-FET (simplest, single-ESC / brushed).**
N-FET in the **ESC/motor ground return**, gate ← `PIN_POWER_GATE` (with a
~100 kΩ gate-to-GND pulldown so it is OFF unless actively driven). HIGH = conduct
(permit), LOW = open (cut).

> **Fail-safe-by-construction:** choose the polarity + pulldown so that
> **no MCU, dead MCU, or floating gate ⇒ CUT.** The firmware also *actively*
> drives CUT at boot before configuring anything else.

---

## 4. Permit-beacon frame format (dedicated link)

A short, fixed-length, CRC-checked frame — deliberately trivial so it can be
audited by eye. This is **not** CRSF/ELRS and **not** MSP; it rides a *separate*
RF link / receiver feeding the beacon UART.

```
 Offset  Size  Field
 ------  ----  ---------------------------------------------------------------
   0      1    SYNC0 = 0xA5
   1      1    SYNC1 = 0x5A
   2      1    CMD   = 0x01 PERMIT  |  0x02 KILL
   3      1    SEQ   = rolling counter (informational)
   4      1    CRC8  = CRC-8/Dallas-Maxim over bytes [2..3]  (CMD, SEQ)
 ------  ----  ---------------------------------------------------------------
 Total: 5 bytes, 115200 8N1 by default.
```

- A valid **PERMIT** frame feeds the watchdog — exactly `permit_beacon(now)`.
- A valid **KILL** frame latches the operator kill — exactly `operator_kill()`.
- Bad sync / bad CRC / unknown CMD → **discarded** (never feeds, never permits).

The console must send **PERMIT continuously at ≥ 20 Hz** (every ≤ 50 ms) while
engagement is authorized — comfortably inside the 500 ms timeout even with
several dropped frames — and send **KILL** on the mushroom press.

---

## 5. Ground-side sender (matching reference sketch)

Drop-in Arduino sketch for the **launch-console side** transmitter MCU. It sends
PERMIT at 50 Hz while an arm/authorize input is held, and KILL while the mushroom
is pressed (KILL takes priority). The CRC and frame layout match the receiver
byte-for-byte.

```cpp
/* hwkill_beacon_sender.ino  --  launch-console permit-beacon transmitter.
 * Wire BEACON_TX into the dedicated RF transmitter that pairs with the
 * receiver feeding the HW-kill MCU. NOT ELRS, NOT MSP. */
#include <Arduino.h>

#define BEACON_TX        Serial1      // hardware UART to the RF tx module
#define BEACON_BAUD      115200
#define PIN_AUTHORIZE    2            // button/keyswitch to GND: held = engagement permitted
#define PIN_MUSHROOM     3            // mushroom ABORT to GND: pressed = KILL
#define SEND_PERIOD_MS   20UL         // 50 Hz  (<< 500 ms receiver timeout)

static const uint8_t SYNC0 = 0xA5, SYNC1 = 0x5A;
static const uint8_t CMD_PERMIT = 0x01, CMD_KILL = 0x02;

static uint8_t crc8_maxim(const uint8_t *d, uint8_t n) {
  uint8_t c = 0x00;
  for (uint8_t i = 0; i < n; i++) {
    uint8_t in = d[i];
    for (uint8_t b = 0; b < 8; b++) {
      uint8_t mix = (c ^ in) & 1; c >>= 1; if (mix) c ^= 0x8C; in >>= 1;
    }
  }
  return c;
}

static void send_frame(uint8_t cmd, uint8_t seq) {
  uint8_t body[2] = { cmd, seq };
  uint8_t f[5] = { SYNC0, SYNC1, cmd, seq, crc8_maxim(body, 2) };
  BEACON_TX.write(f, 5);
}

void setup() {
  pinMode(PIN_AUTHORIZE, INPUT_PULLUP);
  pinMode(PIN_MUSHROOM,  INPUT_PULLUP);
  BEACON_TX.begin(BEACON_BAUD);
}

void loop() {
  static unsigned long last = 0;
  static uint8_t seq = 0;
  unsigned long now = millis();
  if (now - last < SEND_PERIOD_MS) return;
  last = now;

  bool mushroom  = (digitalRead(PIN_MUSHROOM)  == LOW);   // pressed = abort
  bool authorize = (digitalRead(PIN_AUTHORIZE) == LOW);   // held    = permit

  if (mushroom) {
    send_frame(CMD_KILL, seq++);          // KILL dominates; latches at receiver
  } else if (authorize) {
    send_frame(CMD_PERMIT, seq++);        // keep power permitted
  }
  // else: send NOTHING -> receiver times out in 500 ms -> CUT (default-deny)
}
```

> Note the deliberate behavior: when neither input is asserted the sender stays
> **silent**, so the receiver's loss-of-signal timeout cuts power. Silence is a
> cut, not a permit.

---

## 6. Build & flash

**Raspberry Pi Pico / RP2040** (recommended):

1. Install the **arduino-pico** core (earlephilhower) in the Arduino IDE / `arduino-cli`.
2. Board: *Raspberry Pi Pico*. Open `hwkill_mcu.ino`, verify, upload.
3. The firmware uses `Serial2` (UART1) on GP5/GP4 and the RP2040 hardware
   watchdog (`hardware/watchdog.h`).

**AVR / Arduino (Uno/Nano/Pro Mini):**

- Remap `PIN_*` to available digital pins; route `BEACON_SERIAL` to a hardware
  UART. The `__AVR__` branch enables `<avr/wdt.h>`. Confirm your bootloader does
  not loop on a watchdog reset (use Optiboot).

`arduino-cli` example:

```
arduino-cli compile  --fqbn rp2040:rp2040:rpipico  firmware/hwkill-mcu
arduino-cli upload   --fqbn rp2040:rp2040:rpipico -p /dev/ttyACM0 firmware/hwkill-mcu
```

---

## 7. Bench V&V before any thrust (props OFF)

Mirror the `test_hwkill.py` invariants on the real board, gate-LED + a meter on
the gate / a current-limited dummy load — **never** real props for these:

1. **Default-deny:** power MCU with **no** beacon sender → gate reads CUT immediately and stays CUT.
2. **Loss of signal:** start PERMIT @50 Hz → gate PERMIT. Stop the sender → gate CUTs within ≤ 500 ms (measure it).
3. **Latched kill:** with PERMIT live, press mushroom (KILL) → gate CUTs instantly. Release mushroom and resume PERMIT → gate **stays CUT** (latched). Hold `PIN_RESET_LATCH` to GND ≥50 ms → latch clears; gate goes PERMIT only because PERMIT is still live.
4. **Backwards/hung clock:** force a HW-watchdog reset (block the loop) → board resets into boot-time CUT; verify no momentary permit glitch on the gate during reset.
5. **Bad frame rejection:** inject garbage / corrupt-CRC frames on the beacon UART → gate never permits from them.
6. **Independence:** repeat (1)–(3) with the FC unpowered and again with the FC powered but its RX unplugged — behavior must be identical (the MCU ignores the FC entirely).

Only after all six pass on hardware (props OFF), then tethered, may staged
powered testing proceed over a cleared keep-out footprint, per the Block-3 S0→F2
staging.

---

## 8. Mapping to `hwkill.py` (audit trail)

| `hwkill.py` | `hwkill_mcu.ino` |
|-------------|------------------|
| `HardwareKillConfig.beacon_timeout_s = 0.5` | `BEACON_TIMEOUT_MS = 500` |
| `Watchdog.feed(now)` / `permit_beacon(now)` | `permit_beacon(now_ms)` (sets `beacon_seen`, `last_beacon_ms`) |
| `Watchdog.healthy(now)`: `0 <= now-last <= timeout`, non-finite → False | `beacon_is_fresh()` wrap-safe delta + `clock_is_valid()` |
| `operator_kill(reason)` → `self._latched = True` | `operator_kill()` → `g.latched = true` |
| `reset()` → clears latch only | `clear_latch()` via `PIN_RESET_LATCH` (beacon state untouched) |
| `motor_power_enabled(now)`: latch first, then beacon | `motor_power_enabled(now_ms)`: `if latched return false; return beacon_is_fresh` |
| `status().reason` strings | `status_reason()` returns the same strings |
| `effective_motor_power = fc_commands AND hw_kill` | physical AND: FC commands ESC, MCU controls the power rail |
```
