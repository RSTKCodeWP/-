// receiver.ino

#include "config.h"
#include "lora_rx.h"
#include "pwm_output.h"
#include "failsafe.h"

ControlPacket packet;

unsigned long lastPacketTime = 0;

void setup() {

    Serial.begin(115200);

    initLoRaReceiver();
    initPWMOutputs();

    Serial.println("UAV Receiver Started");
}

void loop() {

    if (receiveControlPacket(packet)) {

        lastPacketTime = millis();

        updatePWMOutputs(packet);

        Serial.print("Throttle: ");
        Serial.println(packet.throttle);

        Serial.print("Yaw: ");
        Serial.println(packet.yaw);

        Serial.print("Pitch: ");
        Serial.println(packet.pitch);

        Serial.print("Roll: ");
        Serial.println(packet.roll);
    }

    checkFailsafe(lastPacketTime);
}