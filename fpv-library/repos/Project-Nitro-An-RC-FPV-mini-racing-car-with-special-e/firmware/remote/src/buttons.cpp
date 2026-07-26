// =============================================================================
//  buttons.cpp — RC button handler
//  Debounces all 12 buttons, detects short press and long press.
//  Call buttons_tick() every loop from Core 0.
// =============================================================================

#include "buttons.h"
#include "rc_types.h"
#include <Arduino.h>

// ---------------------------------------------------------------------------
// Button descriptor table
// ---------------------------------------------------------------------------
static const uint8_t PIN_MAP[BTN_COUNT] = {
    BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT,
    BTN_OK, BTN_BACK,
    BTN_SHOOT, BTN_BOOST, BTN_HEALTH, BTN_SHIELD,
    BTN_ONOFF, BTN_CONNECT
};

// Runtime state per button
struct BtnState {
    bool     lastRaw;       // raw GPIO last read
    bool     stable;        // debounced stable state (true = pressed)
    uint32_t changeMs;      // millis when raw changed
    uint32_t pressMs;       // millis when stable press began
    bool     reported;      // short-press already reported this press
    bool     longReported;  // long-press already reported this press
};

static BtnState s_btn[BTN_COUNT] = {};

// Event ring buffer
#define EVT_BUF_SIZE 16
static BtnEvent s_evtBuf[EVT_BUF_SIZE];
static uint8_t  s_evtHead = 0;
static uint8_t  s_evtTail = 0;

static void push_event(BtnEvent evt) {
    uint8_t next = (s_evtHead + 1) % EVT_BUF_SIZE;
    if (next == s_evtTail) return; // full — drop oldest
    s_evtBuf[s_evtHead] = evt;
    s_evtHead = next;
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
void buttons_init() {
    for (int i = 0; i < BTN_COUNT; i++) {
        uint8_t pin = PIN_MAP[i];
        // GPIO 34,35,36,39 are input-only — no internal pull-up
        if (pin == BTN_HEALTH || pin == BTN_SHIELD ||
            pin == BTN_ONOFF  || pin == BTN_CONNECT) {
            pinMode(pin, INPUT); // external 10kΩ pull-up to 3V3 required on PCB
        } else {
            pinMode(pin, INPUT_PULLUP);
        }
        s_btn[i] = {};
    }
}

// ---------------------------------------------------------------------------
// Tick — call every ~10ms from Core 0
// ---------------------------------------------------------------------------
void buttons_tick() {
    uint32_t now = millis();
    for (int i = 0; i < BTN_COUNT; i++) {
        uint8_t pin = PIN_MAP[i];
        // Active LOW — pressed = LOW = true after inversion
        bool raw = (digitalRead(pin) == LOW);
        BtnState& b = s_btn[i];

        // Detect raw change — start debounce timer
        if (raw != b.lastRaw) {
            b.lastRaw  = raw;
            b.changeMs = now;
        }

        // Debounce: only accept stable state after DEBOUNCE_MS
        if ((now - b.changeMs) >= DEBOUNCE_MS) {
            if (raw != b.stable) {
                b.stable = raw;

                if (b.stable) {
                    // Just became pressed
                    b.pressMs     = now;
                    b.reported    = false;
                    b.longReported= false;
                } else {
                    // Just released
                    if (!b.reported && !b.longReported) {
                        // Short press — report on release
                        BtnEvent e;
                        e.btn  = (BtnId)i;
                        e.type = BTN_SHORT;
                        push_event(e);
                    }
                    b.reported = true;
                }
            }
        }

        // Long press detection while held
        if (b.stable && !b.longReported &&
            (now - b.pressMs) >= LONG_PRESS_MS) {
            b.longReported = true;
            b.reported     = true;
            BtnEvent e;
            e.btn  = (BtnId)i;
            e.type = BTN_LONG;
            push_event(e);
        }
    }
}

// ---------------------------------------------------------------------------
// Poll — returns false if no event pending
// ---------------------------------------------------------------------------
bool buttons_poll(BtnEvent* out) {
    if (s_evtHead == s_evtTail) return false;
    *out = s_evtBuf[s_evtTail];
    s_evtTail = (s_evtTail + 1) % EVT_BUF_SIZE;
    return true;
}

// Raw stable state query (for held-down drive buttons)
bool buttons_held(BtnId btn) {
    return s_btn[(int)btn].stable;
}
