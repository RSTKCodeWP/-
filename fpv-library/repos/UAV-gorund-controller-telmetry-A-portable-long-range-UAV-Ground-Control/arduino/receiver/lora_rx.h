// lora_rx.h

#ifndef LORA_RX_H
#define LORA_RX_H

#include <SPI.h>
#include <LoRa.h>
#include "config.h"

void initLoRaReceiver();

bool receiveControlPacket(
    ControlPacket &packet
);

#endif