// config.h

#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// LoRa Pins
#define LORA_SS    53
#define LORA_RST   9
#define LORA_DIO0  2

#define LORA_FREQ 433E6

// PWM Output Pins
#define THROTTLE_PIN 3
#define YAW_PIN      5
#define PITCH_PIN    6
#define ROLL_PIN     9

// Failsafe Timeout
#define FAILSAFE_TIMEOUT 1000

struct ControlPacket {

    int throttle;
    int yaw;
    int pitch;
    int roll;

    bool arm;
    bool mode;
    bool rth;
};

#endif