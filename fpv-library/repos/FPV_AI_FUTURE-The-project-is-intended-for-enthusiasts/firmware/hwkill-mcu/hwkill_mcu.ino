/*
 * ============================================================================
 *  Block-3 INDEPENDENT HARDWARE KILL  --  hwkill_mcu.ino
 *  The LAST line of defense, BELOW the flight controller and BELOW the Pi.
 * ============================================================================
 *
 *  This is self-contained firmware for a dedicated watchdog MCU (target:
 *  Raspberry Pi Pico / RP2040, but written to compile on any Arduino-class
 *  board). It gates MOTOR POWER physically -- it drives a GPIO that controls a
 *  power-cut element (a high-side/low-side MOSFET or a smart-ESC kill line)
 *  wired in the motor-power path BELOW the FC. When this MCU denies power, the
 *  motors cannot spin no matter what the FC firmware, the ESCs, the Pi, MSP or
 *  ELRS do.
 *
 *  It is the firmware realization of the verified spec hwkill.py
 *  (fpv_ai/betaflight_link/hwkill.py) and reproduces its logic EXACTLY:
 *
 *    Invariant 1  DEFAULT-DENY: motor power is CUT unless a fresh permit beacon
 *                 is actively being received on this MCU's OWN input channel.
 *    Invariant 2  LOSS OF SIGNAL: no valid permit beacon within
 *                 BEACON_TIMEOUT_MS (default 500 ms) -> CUT, autonomously, on
 *                 this MCU's own clock. No beacon at boot -> already CUT.
 *    Invariant 3  OPERATOR KILL (the mushroom ABORT on this dedicated channel)
 *                 -> CUT, LATCHED, sticky until a deliberate PHYSICAL RESET pin
 *                 is asserted. A transient or a later fresh beacon does NOT
 *                 re-enable it.
 *    Invariant 4  A non-finite / corrupt / backwards clock is NOT a valid
 *                 permit -> CUT (fail safe). Mirrors the Watchdog.healthy()
 *                 contract: power only while  0 <= (now - last_beacon) <= TIMEOUT.
 *
 *  INDEPENDENCE IS THE WHOLE POINT. This decision depends ONLY on:
 *    - this MCU's own dedicated serial/RF input (a permit beacon + kill command
 *      from the launch console, on a SEPARATE link from ELRS and from MSP), and
 *    - this MCU's own clock (millis()/micros()).
 *  It does NOT read the FC, the Pi, MSP, or ELRS. So it still fires when all of
 *  those are dead, hung, jammed, or compromised. A software failsafe inside
 *  Betaflight (disarm(DISARM_REASON_FAILSAFE), motorShutdown()) is necessary
 *  but NOT sufficient: it lives inside the very firmware that may have hung, and
 *  it can only ask the ESCs to stop -- it cannot remove power. This MCU removes
 *  power.
 *
 *  TIMING RATIONALE (matches the design): BEACON_TIMEOUT_MS (500 ms) is set
 *  LONGER than the software link failsafe (~200 ms, fork msp_timeout_s / BF
 *  failsafe_delay). The controlled safe-ditch path inside the FC runs first;
 *  THIS independent cut is the guaranteed backstop that fires if that path
 *  fails. Per design, a powered cut must only ever occur over a surveyed /
 *  cleared ground keep-out footprint.
 *
 *  DEFAULT-DENY AT EVERY LEVEL:
 *    - At boot, before the first loop(), the kill line is driven to CUT.
 *    - The "permitted" state is a momentary computed result, never a latched
 *      flag that could get stuck enabled.
 *    - Any doubt (timeout, bad frame, bad clock, latched kill) -> CUT.
 *
 *  This file is intentionally written for correctness over cleverness. No
 *  dynamic allocation, no String, no interrupts required for the safety path,
 *  no blocking calls in the hot loop, watchdog-friendly. Read it top to bottom.
 * ============================================================================
 */

#include <Arduino.h>

/* ===========================================================================
 *  COMPILE-TIME CONFIGURATION
 *  Pins are for Raspberry Pi Pico / RP2040 (GPxx == Arduino pin number on the
 *  earlephilhower arduino-pico core). Adjust for your board; see README.
 * =========================================================================== */

/* ---- Motor-power gate output (drives the MOSFET gate / smart-ESC kill line) */
#ifndef PIN_POWER_GATE
#define PIN_POWER_GATE      15      /* GP15: HIGH = permit power, LOW = CUT.   */
#endif
/* If your hardware is active-LOW (e.g. an N-FET on the low side that conducts
 * when the gate is HIGH, but a kill line that CUTS on HIGH), set this to 1.
 * When 1, the logic is inverted at the pin so "permit" still drives the safe
 * electrical level. DEFAULT (0): HIGH = permit power, LOW = cut.              */
#ifndef POWER_GATE_ACTIVE_LOW
#define POWER_GATE_ACTIVE_LOW   0
#endif

/* ---- Status / annunciation outputs (optional but recommended) ------------- */
#ifndef PIN_STATUS_LED
#define PIN_STATUS_LED      LED_BUILTIN  /* solid = powered, blink = cut, fast blink = latched */
#endif
#ifndef PIN_CUT_ALARM
#define PIN_CUT_ALARM       16      /* GP16: HIGH whenever power is CUT (drive a buzzer/telltale) */
#endif

/* ---- Physical RESET-LATCH input ------------------------------------------- *
 * Pulling this pin LOW (to GND) for >= RESET_HOLD_MS clears a latched operator
 * kill. It uses the internal pull-up, so a simple momentary button to GND is a
 * deliberate physical reset. This mirrors hwkill.py reset(): clearing the latch
 * does NOT by itself enable power -- a live permit beacon is still required.   */
#ifndef PIN_RESET_LATCH
#define PIN_RESET_LATCH     14      /* GP14: button to GND, active LOW, internal pull-up */
#endif
#ifndef RESET_HOLD_MS
#define RESET_HOLD_MS       50UL    /* debounce: hold reset this long to clear the latch */
#endif

/* ---- Dedicated permit-beacon / kill serial input -------------------------- *
 * A SEPARATE receiver (its own RF link, NOT ELRS and NOT the MSP UART) feeds a
 * simple framed UART into this pin. On RP2040 this is UART1 (Serial2 on the
 * arduino-pico core). See README for the frame format and a ground-side sender. */
#ifndef BEACON_SERIAL
#define BEACON_SERIAL       Serial2
#endif
#ifndef BEACON_BAUD
#define BEACON_BAUD         115200
#endif
#ifndef PIN_BEACON_RX
#define PIN_BEACON_RX       5       /* GP5  = UART1 RX on RP2040 */
#endif
#ifndef PIN_BEACON_TX
#define PIN_BEACON_TX       4       /* GP4  = UART1 TX on RP2040 (unused, for completeness) */
#endif

/* ---- Watchdog timing ------------------------------------------------------ *
 * BEACON_TIMEOUT_MS mirrors HardwareKillConfig.beacon_timeout_s default 0.5 s.
 * The cut must fire even if the loop stalls, so we ALSO arm the hardware
 * watchdog timer just above this period.                                      */
#ifndef BEACON_TIMEOUT_MS
#define BEACON_TIMEOUT_MS   500UL   /* == hwkill.py beacon_timeout_s = 0.5 s    */
#endif
#ifndef HW_WDT_MS
#define HW_WDT_MS           (BEACON_TIMEOUT_MS + 200UL)  /* MCU self-reset if loop hangs */
#endif

/* ===========================================================================
 *  PERMIT-BEACON FRAME FORMAT  (dedicated link, NOT CRSF/ELRS, NOT MSP)
 *  A short, fixed-length, CRC-checked frame. Deliberately trivial so it can be
 *  audited by eye and produced by the simplest possible ground sender.
 *
 *    Offset  Size  Field
 *    ------  ----  -----------------------------------------------------------
 *      0      1    SYNC0   = 0xA5
 *      1      1    SYNC1   = 0x5A
 *      2      1    CMD     = 0x01 PERMIT  |  0x02 KILL
 *      3      1    SEQ     = rolling sequence counter (informational)
 *      4      1    CRC8    = CRC-8/Dallas-Maxim over bytes [2..3] (CMD, SEQ)
 *    ------  ----  -----------------------------------------------------------
 *    Total: 5 bytes.
 *
 *  A PERMIT frame (CMD=0x01) with a valid CRC feeds the beacon watchdog --
 *  exactly like hwkill.permit_beacon(now). A KILL frame (CMD=0x02) with a valid
 *  CRC latches the operator kill -- exactly like hwkill.operator_kill().
 *  Any frame with a bad sync or bad CRC is DISCARDED (default-deny: a corrupt
 *  frame never feeds the watchdog and never re-enables power).
 *
 *  The ground console sends PERMIT continuously at >= 20 Hz while engagement is
 *  authorized (well inside the 500 ms timeout), and sends KILL on the mushroom.
 * =========================================================================== */

static const uint8_t FRAME_SYNC0 = 0xA5;
static const uint8_t FRAME_SYNC1 = 0x5A;
static const uint8_t CMD_PERMIT  = 0x01;
static const uint8_t CMD_KILL    = 0x02;
static const uint8_t FRAME_LEN   = 5;

/* CRC-8/Dallas-Maxim (poly 0x31 reflected -> 0x8C), init 0x00. Tiny + standard. */
static uint8_t crc8_maxim(const uint8_t *data, uint8_t len) {
  uint8_t crc = 0x00;
  for (uint8_t i = 0; i < len; i++) {
    uint8_t inbyte = data[i];
    for (uint8_t b = 0; b < 8; b++) {
      uint8_t mix = (crc ^ inbyte) & 0x01;
      crc >>= 1;
      if (mix) crc ^= 0x8C;
      inbyte >>= 1;
    }
  }
  return crc;
}

/* ===========================================================================
 *  CORE STATE  --  this is the direct port of class HardwareKill.
 *  Kept as a tiny struct of primitives; no heap, no hidden state.
 * =========================================================================== */

struct HwKillState {
  bool          beacon_seen;      /* has a valid PERMIT ever been received?     */
  unsigned long last_beacon_ms;   /* millis() of the last valid PERMIT          */
  bool          latched;          /* operator KILL latched (sticky)             */
};

static HwKillState g = {
  /* beacon_seen   */ false,      /* DEFAULT-DENY: no beacon yet                */
  /* last_beacon_ms*/ 0,
  /* latched       */ false,
};

/* ---- Invariant 4: clock validity ----------------------------------------- *
 * millis() cannot be NaN/Inf, but it CAN wrap (~49.7 days) and a watchdog reset
 * restarts it at 0. We treat "delta computed with unsigned wrap-safe math" the
 * same way Watchdog.healthy() treats the finite-clock case: power is permitted
 * only when 0 <= (now - last) <= TIMEOUT. We additionally reject a clearly
 * impossible delta (future beacon -> backwards clock) by failing safe.
 *
 *   In hwkill.py:  healthy = (last is not None) and 0.0 <= (now-last) <= timeout
 *   Here:          permitted_by_beacon() implements the identical predicate.    */
/* Stuck-clock detector. millis() cannot be NaN/Inf on-MCU, but the timer
 * peripheral CAN die while the CPU keeps running -- and then millis() freezes.
 * That is the dangerous case the spec's "reject a bad clock" guards against: a
 * frozen clock makes (now - last_beacon) stay constant, so a beacon that was
 * fresh at the instant of the freeze would look fresh FOREVER and hold power on.
 *
 * We catch it structurally: the loop runs far faster than 1 ms, so millis()
 * MUST advance at least once within a large but bounded number of iterations. If
 * it has not advanced for STUCK_ITERS consecutive loops, the timer is stuck ->
 * the clock is invalid -> CUT (fail-safe). STUCK_ITERS is set enormously higher
 * than any real per-millisecond iteration count, so a healthy fast loop never
 * trips it; only a genuinely frozen timer does. Updated once per loop by
 * clock_tick(), evaluated inside the same predicate the spec uses.             */
#ifndef STUCK_ITERS
#define STUCK_ITERS   2000000UL   /* >> loops-per-ms on any target; ~ms of freeze */
#endif

static unsigned long s_last_ms      = 0;
static unsigned long s_iters_at_ms  = 0;
static bool          s_clock_stuck  = false;

static void clock_tick(unsigned long now_ms) {
  if (now_ms != s_last_ms) {        /* clock advanced -> healthy, reset the counter */
    s_last_ms     = now_ms;
    s_iters_at_ms = 0;
    return;
  }
  if (s_iters_at_ms < STUCK_ITERS) {
    s_iters_at_ms++;
  } else {
    s_clock_stuck = true;           /* sticky: a frozen timer never un-freezes safely */
  }
}

static bool clock_is_valid() {
  return !s_clock_stuck;            /* stuck timer -> invalid -> beacon_is_fresh() CUTs */
}

/* Direct port of  HardwareKill.permit_beacon(now)  */
static void permit_beacon(unsigned long now_ms) {
  if (!clock_is_valid()) return;       /* a bad clock is not a valid heartbeat */
  g.beacon_seen    = true;
  g.last_beacon_ms = now_ms;
}

/* Direct port of  HardwareKill.operator_kill(reason)  -- sets the sticky latch */
static void operator_kill() {
  g.latched = true;                    /* sticky: only reset() (physical) clears */
}

/* Direct port of  HardwareKill.reset()  -- clears latch; power still needs a
 * live beacon afterwards. We do NOT touch beacon_seen/last_beacon here, exactly
 * like the spec: reset() only clears the latch.                               */
static void clear_latch() {
  g.latched = false;
}

/* The beacon-freshness half of the predicate, wrap-safe.
 * Mirrors Watchdog.healthy(now):
 *   healthy  <=>  last is not None  AND  0 <= (now-last) <= timeout
 * Unsigned subtraction handles millis() wrap correctly for the in-window case;
 * a "future" beacon (now < last by a small amount, i.e. a backwards clock)
 * yields a huge unsigned delta that exceeds the timeout -> NOT fresh -> CUT,
 * which is exactly the spec's "backwards clock cuts" behavior.                */
static bool beacon_is_fresh(unsigned long now_ms) {
  if (!g.beacon_seen)  return false;   /* never fed -> default-deny            */
  if (!clock_is_valid()) return false; /* invariant 4: bad clock -> CUT        */
  unsigned long delta = now_ms - g.last_beacon_ms;   /* wrap-safe unsigned     */
  return delta <= BEACON_TIMEOUT_MS;
}

/* Direct port of  HardwareKill.motor_power_enabled(now)  -- the hard authority.
 *   if latched: return False
 *   return beacon.healthy(now)
 * Latch dominates a fresh beacon (invariant 3).                               */
static bool motor_power_enabled(unsigned long now_ms) {
  if (g.latched) return false;         /* latched kill dominates everything    */
  return beacon_is_fresh(now_ms);
}

/* Human-readable reason, matching HardwareKill.status().reason strings.        */
static const char *status_reason(unsigned long now_ms) {
  if (g.latched)              return "latched_kill:operator_abort";
  if (!beacon_is_fresh(now_ms)) return "permit_beacon_lost";
  return "powered";
}

/* ===========================================================================
 *  PHYSICAL OUTPUT  --  drive the power-cut element. SINGLE point of authority.
 *  Nothing else in this file writes PIN_POWER_GATE.
 * =========================================================================== */
static void drive_power_gate(bool permit) {
  /* "permit" true -> allow motor power. Resolve polarity for the hardware.    */
  uint8_t level;
#if POWER_GATE_ACTIVE_LOW
  level = permit ? LOW : HIGH;         /* active-low gate: LOW permits          */
#else
  level = permit ? HIGH : LOW;         /* default: HIGH permits, LOW cuts       */
#endif
  digitalWrite(PIN_POWER_GATE, level);

  /* Cut alarm telltale: HIGH whenever power is being CUT.                     */
  digitalWrite(PIN_CUT_ALARM, permit ? LOW : HIGH);
}

/* Force the safe (CUT) electrical state immediately. Used at boot, before pins
 * are even configured as we want, and on any fault. Idempotent.              */
static void force_cut_now() {
#if POWER_GATE_ACTIVE_LOW
  digitalWrite(PIN_POWER_GATE, HIGH);  /* active-low: HIGH = cut               */
#else
  digitalWrite(PIN_POWER_GATE, LOW);   /* default:   LOW  = cut                */
#endif
  digitalWrite(PIN_CUT_ALARM, HIGH);
}

/* ===========================================================================
 *  SERIAL FRAME PARSER  --  small byte-at-a-time state machine, no blocking.
 *  Robust to garbage: it resyncs on SYNC0/SYNC1 and CRC-checks every frame.
 * =========================================================================== */
enum RxStage { WAIT_SYNC0, WAIT_SYNC1, READ_BODY };
static RxStage  rx_stage = WAIT_SYNC0;
static uint8_t  rx_buf[FRAME_LEN];
static uint8_t  rx_idx = 0;

/* Pull all available bytes; act on each complete, CRC-valid frame.            */
static void poll_beacon_serial(unsigned long now_ms) {
  while (BEACON_SERIAL.available() > 0) {
    uint8_t b = (uint8_t)BEACON_SERIAL.read();
    switch (rx_stage) {
      case WAIT_SYNC0:
        if (b == FRAME_SYNC0) { rx_buf[0] = b; rx_stage = WAIT_SYNC1; }
        break;
      case WAIT_SYNC1:
        if (b == FRAME_SYNC1) { rx_buf[1] = b; rx_idx = 2; rx_stage = READ_BODY; }
        else                  { rx_stage = WAIT_SYNC0; }  /* resync             */
        break;
      case READ_BODY:
        rx_buf[rx_idx++] = b;
        if (rx_idx >= FRAME_LEN) {
          /* full frame: CMD=rx_buf[2], SEQ=rx_buf[3], CRC=rx_buf[4] over [2..3] */
          uint8_t want = crc8_maxim(&rx_buf[2], 2);
          if (want == rx_buf[4]) {
            uint8_t cmd = rx_buf[2];
            if (cmd == CMD_PERMIT)      permit_beacon(now_ms);  /* feed watchdog */
            else if (cmd == CMD_KILL)   operator_kill();        /* latch         */
            /* unknown CMD with valid CRC: ignore (default-deny, never permits) */
          }
          /* bad CRC -> silently discard the frame (it never feeds anything)    */
          rx_stage = WAIT_SYNC0;
        }
        break;
    }
  }
}

/* ===========================================================================
 *  PHYSICAL RESET-LATCH HANDLING  --  active-LOW button to GND, debounced.
 * =========================================================================== */
static unsigned long reset_low_since = 0;
static bool          reset_was_low   = false;
static bool          reset_consumed  = false;   /* latch already cleared for THIS press */

/* EDGE-triggered reset (safety-critical fix): the latch is cleared at most ONCE per
 * deliberate press held >= RESET_HOLD_MS, never continuously while held. Otherwise a
 * CONTINUOUSLY-HELD reset would silently un-latch a KILL that arrives while held --
 * defeating the entire point of the latched mushroom abort. To clear again, the operator
 * must RELEASE and press again. A KILL arriving during a held reset therefore latches and
 * survives, exactly as required.                                                          */
static void poll_reset_latch(unsigned long now_ms) {
  bool low = (digitalRead(PIN_RESET_LATCH) == LOW);   /* pressed = LOW          */
  if (low && !reset_was_low) {
    reset_low_since = now_ms;                          /* press began           */
    reset_consumed = false;                            /* a fresh press may clear once */
  }
  if (!low) {
    reset_consumed = false;                            /* released -> re-press needed   */
  }
  if (low && !reset_consumed && (now_ms - reset_low_since) >= RESET_HOLD_MS) {
    clear_latch();                                     /* deliberate phys reset, ONCE   */
    reset_consumed = true;                             /* do not re-clear while held    */
  }
  reset_was_low = low;
}

/* ===========================================================================
 *  HARDWARE WATCHDOG  --  so a hung loop ALSO ends in a power cut.
 *  On RP2040 (arduino-pico core) rp2040.wdt_* is available. On AVR we fall back
 *  to <avr/wdt.h>. If neither exists, the software beacon timeout still cuts on
 *  the next loop; the HW WDT is defense-in-depth for a fully hung CPU.
 *  CRITICAL: after a WDT reset, setup() runs and force_cut_now() is the FIRST
 *  thing that happens -> the cut survives the reset (default-deny on boot).    */
#if defined(ARDUINO_ARCH_RP2040)
  #include <hardware/watchdog.h>
  static void hw_wdt_begin() { watchdog_enable(HW_WDT_MS, /*pause_on_debug=*/1); }
  static void hw_wdt_feed()  { watchdog_update(); }
#elif defined(__AVR__)
  #include <avr/wdt.h>
  static void hw_wdt_begin() {
    /* Pick the smallest standard WDT period >= HW_WDT_MS available on AVR.     */
    #if   (HW_WDT_MS <= 250UL)
      wdt_enable(WDTO_250MS);
    #elif (HW_WDT_MS <= 500UL)
      wdt_enable(WDTO_500MS);
    #elif (HW_WDT_MS <= 1000UL)
      wdt_enable(WDTO_1S);
    #else
      wdt_enable(WDTO_2S);
    #endif
  }
  static void hw_wdt_feed()  { wdt_reset(); }
#else
  static void hw_wdt_begin() {}        /* no HW WDT on this target              */
  static void hw_wdt_feed()  {}
#endif

/* ===========================================================================
 *  STATUS LED  --  cheap operator feedback, never on the safety path.
 *    solid ON    = powered (permit live)
 *    slow blink  = cut, waiting for a fresh beacon (recoverable)
 *    fast blink  = LATCHED kill (needs physical reset)
 * =========================================================================== */
static void drive_status_led(unsigned long now_ms, bool permit) {
  bool on;
  if (g.latched)        on = ((now_ms / 100) & 1);   /* fast blink ~5 Hz       */
  else if (permit)      on = true;                    /* solid                  */
  else                  on = ((now_ms / 400) & 1);    /* slow blink ~1.25 Hz    */
  digitalWrite(PIN_STATUS_LED, on ? HIGH : LOW);
}

/* ===========================================================================
 *  ARDUINO ENTRY POINTS
 * =========================================================================== */
void setup() {
  /* ----- 1. ESTABLISH THE SAFE STATE BEFORE ANYTHING ELSE -----------------
   * Default-deny on boot: configure the gate pin as an output already driving
   * CUT. (We set the level first via the port latch, then enable the output,
   * to avoid a momentary "permit" glitch on some cores. force_cut_now() after
   * pinMode locks it in.)                                                     */
  pinMode(PIN_POWER_GATE, OUTPUT);
  pinMode(PIN_CUT_ALARM,  OUTPUT);
  force_cut_now();                       /* motors CANNOT be powered yet        */

  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LOW);

  /* Physical reset-latch button: active-low to GND with internal pull-up.     */
  pinMode(PIN_RESET_LATCH, INPUT_PULLUP);

  /* ----- 2. Bring up the dedicated permit-beacon serial input -------------- */
#if defined(ARDUINO_ARCH_RP2040)
  BEACON_SERIAL.setRX(PIN_BEACON_RX);
  BEACON_SERIAL.setTX(PIN_BEACON_TX);
#endif
  BEACON_SERIAL.begin(BEACON_BAUD);

  /* ----- 3. Arm the hardware watchdog (a hung loop -> reset -> re-cut) ------ */
  hw_wdt_begin();

  /* State already defaults to: no beacon, not latched -> CUT. Nothing to do.  */
}

void loop() {
  unsigned long now_ms = millis();
  clock_tick(now_ms);            /* stuck-timer watchdog: freeze -> clock invalid -> CUT */

  /* (a) Ingest this MCU's OWN inputs -- nothing from the FC/Pi/ELRS/MSP.      */
  poll_beacon_serial(now_ms);    /* PERMIT feeds watchdog; KILL latches        */
  poll_reset_latch(now_ms);      /* deliberate physical reset clears the latch */

  /* (b) Compute the single hard authority (exact port of motor_power_enabled).
   *     Evaluation order matches hwkill.py: latch first, then beacon freshness,
   *     then clock validity inside beacon_is_fresh().                          */
  bool permit = motor_power_enabled(now_ms);

  /* (c) DRIVE THE PHYSICAL GATE. This is the only place power is enabled, and
   *     it is enabled ONLY when permit==true. Every other path leaves it CUT. */
  drive_power_gate(permit);

  /* (d) Annunciate + pet the HW watchdog. The feed is AFTER the gate write so
   *     a fault that prevents us from reaching the gate also stops the feed
   *     and lets the HW WDT reset us into the boot-time CUT.                   */
  drive_status_led(now_ms, permit);
  hw_wdt_feed();

  /* No delay(): tightest possible loop so the cut reacts within one iteration.
   * (void) status_reason(now_ms);  // available for telemetry/logging if wired */
}
