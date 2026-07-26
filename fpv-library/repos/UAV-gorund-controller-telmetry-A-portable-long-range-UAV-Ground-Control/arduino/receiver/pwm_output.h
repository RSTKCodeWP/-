// pwm_output.h

#ifndef PWM_OUTPUT_H
#define PWM_OUTPUT_H

#include <Servo.h>
#include "config.h"

void initPWMOutputs();

void updatePWMOutputs(
    ControlPacket &packet
);

#endif