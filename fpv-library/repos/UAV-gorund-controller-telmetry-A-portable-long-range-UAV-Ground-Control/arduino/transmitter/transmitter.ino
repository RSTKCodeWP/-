// transmitter.ino

#include "config.h"
#include "joystick.h"
#include "buttons.h"
#include "lora_tx.h"

ControlPacket packet;

void setup() {

    Serial.begin(115200);

    initJoystick();
    initButtons();
    initLoRa();

    Serial.println("UAV Ground Controller Started");
}

void loop() {

    readJoystick(packet);
    readButtons(packet);

    sendControlPacket(packet);

    Serial.print("Throttle: ");
    Serial.println(packet.throttle);

    delay(50);
}