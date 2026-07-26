// lora_tx.h

#ifndef LORA_TX_H
#define LORA_TX_H

#include <SPI.h>
#include <LoRa.h>
#include "config.h"

void initLoRa();
void sendControlPacket(ControlPacket &packet);

#endif