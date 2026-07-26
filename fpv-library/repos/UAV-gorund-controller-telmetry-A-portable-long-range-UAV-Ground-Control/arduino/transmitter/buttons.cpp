// buttons.cpp

#include "buttons.h"

void initButtons() {

    pinMode(ARM_BUTTON, INPUT_PULLUP);
    pinMode(MODE_BUTTON, INPUT_PULLUP);
    pinMode(RTH_BUTTON, INPUT_PULLUP);
}

void readButtons(ControlPacket &packet) {

    packet.arm = !digitalRead(ARM_BUTTON);

    packet.mode = !digitalRead(MODE_BUTTON);

    packet.rth = !digitalRead(RTH_BUTTON);
}