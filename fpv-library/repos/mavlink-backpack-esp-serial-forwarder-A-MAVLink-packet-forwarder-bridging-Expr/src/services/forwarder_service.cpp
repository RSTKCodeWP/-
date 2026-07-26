#include "forwarder_service.h"

ForwarderService::ForwarderService(WiFiUDP &udp) : udp(udp) {}

void ForwarderService::serialToUdp()
{
  char serialBuffer[512];
  int serialIndex = 0;

  while (Serial.available())
  {
    char c = Serial.read();
    serialBuffer[serialIndex++] = c;

    // Optional: flush buffer if too large
    if (serialIndex >= sizeof(serialBuffer))
    {
      break;
    }

    delay(1);
  }

  if (serialIndex > 0)
  {
    udp.beginPacket(udp.remoteIP(), udp.remotePort());
    udp.write((uint8_t *)serialBuffer, serialIndex);
    udp.endPacket();
    serialIndex = 0;
  }
}

void ForwarderService::udpToSerial()
{
  int packetSize = udp.parsePacket();
  if (packetSize)
  {
    char packetBuffer[512];
    int len = udp.read(packetBuffer, sizeof(packetBuffer));
    if (len > 0)
    {
      packetBuffer[len] = 0;
      Serial.write((uint8_t *)packetBuffer, len);
    }
  }
}