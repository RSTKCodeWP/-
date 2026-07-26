// joystick.cpp

#include "joystick.h"

void initJoystick() {

    pinMode(JOY1_X, INPUT);
    pinMode(JOY1_Y, INPUT);

    pinMode(JOY2_X, INPUT);
    pinMode(JOY2_Y, INPUT);
}

void readJoystick(ControlPacket &packet) {

    packet.throttle = analogRead(JOY1_Y);

    packet.yaw = map(
        analogRead(JOY1_X),
        0,
        1023,
        -100,
        100
    );

    packet.pitch = map(
        analogRead(JOY2_Y),
        0,
        1023,
        -100,
        100
    );

    packet.roll = map(
        analogRead(JOY2_X),
        0,
        1023,
        -100,
        100
    );
}