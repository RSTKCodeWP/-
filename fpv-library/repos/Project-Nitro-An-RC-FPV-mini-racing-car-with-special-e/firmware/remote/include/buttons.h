#pragma once
#include "rc_types.h"
#include <stdint.h>
#include <stdbool.h>

// Button IDs — must match PIN_MAP order in buttons.cpp
enum BtnId : uint8_t {
    BTN_ID_UP = 0, BTN_ID_DOWN, BTN_ID_LEFT, BTN_ID_RIGHT,
    BTN_ID_OK, BTN_ID_BACK,
    BTN_ID_SHOOT, BTN_ID_BOOST, BTN_ID_HEALTH, BTN_ID_SHIELD,
    BTN_ID_ONOFF, BTN_ID_CONNECT,
    BTN_COUNT
};

enum BtnPressType : uint8_t { BTN_SHORT = 0, BTN_LONG = 1 };

struct BtnEvent {
    BtnId        btn;
    BtnPressType type;
};

void     buttons_init();
void     buttons_tick();              // call every ~10ms
bool     buttons_poll(BtnEvent* out); // non-blocking, returns false if empty
bool     buttons_held(BtnId btn);     // true while physically held
