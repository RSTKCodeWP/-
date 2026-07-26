// lora_rx.cpp

#include "lora_rx.h"

void initLoRaReceiver() {

    LoRa.setPins(
        LORA_SS,
        LORA_RST,
        LORA_DIO0
    );

    if (!LoRa.begin(LORA_FREQ)) {

        Serial.println("LoRa Init Failed");

        while (1);
    }

    Serial.println("LoRa Receiver Initialized");
}

bool receiveControlPacket(
    ControlPacket &packet
) {

    int packetSize = LoRa.parsePacket();

    if (packetSize) {

        LoRa.readBytes(
            (uint8_t*)&packet,
            sizeof(packet)
        );

        return true;
    }

    return false;
}