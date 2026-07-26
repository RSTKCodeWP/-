// pwm_output.cpp

#include "pwm_output.h"

Servo throttleServo;
Servo yawServo;
Servo pitchServo;
Servo rollServo;

void initPWMOutputs() {

    throttleServo.attach(THROTTLE_PIN);
    yawServo.attach(YAW_PIN);
    pitchServo.attach(PITCH_PIN);
    rollServo.attach(ROLL_PIN);
}

void updatePWMOutputs(
    ControlPacket &packet
) {

    int throttlePWM = map(
        packet.throttle,
        0,
        1023,
        1000,
        2000
    );

    int yawPWM = map(
        packet.yaw,
        -100,
        100,
        1000,
        2000
    );

    int pitchPWM = map(
        packet.pitch,
        -100,
        100,
        1000,
        2000
    );

    int rollPWM = map(
        packet.roll,
        -100,
        100,
        1000,
        2000
    );

    throttleServo.writeMicroseconds(throttlePWM);

    yawServo.writeMicroseconds(yawPWM);

    pitchServo.writeMicroseconds(pitchPWM);

    rollServo.writeMicroseconds(rollPWM);
}