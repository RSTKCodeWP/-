// failsafe.h

#ifndef FAILSAFE_H
#define FAILSAFE_H

#include "config.h"

void checkFailsafe(
    unsigned long lastPacketTime
) {

    if (
        millis() - lastPacketTime >
        FAILSAFE_TIMEOUT
    ) {

        Serial.println(
            "FAILSAFE ACTIVATED"
        );

        // Emergency stop logic
        // Return-To-Home logic
        // Motor shutdown logic

        analogWrite(THROTTLE_PIN, 0);
    }
}

#endif