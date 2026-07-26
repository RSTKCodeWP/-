// lora_tx.cpp

#include "lora_tx.h"

void initLoRa() {

    LoRa.setPins(
        LORA_SS,
        LORA_RST,
        LORA_DIO0
    );

    if (!LoRa.begin(LORA_FREQ)) {

        Serial.println("LoRa Init Failed");

        while (1);
    }

    Serial.println("LoRa Initialized");
}

void sendControlPacket(ControlPacket &packet) {

    LoRa.beginPacket();

    LoRa.write(
        (uint8_t*)&packet,
        sizeof(packet)
    );

    LoRa.endPacket();
}