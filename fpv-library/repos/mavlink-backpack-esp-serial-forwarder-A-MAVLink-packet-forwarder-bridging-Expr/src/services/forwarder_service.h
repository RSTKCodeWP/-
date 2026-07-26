#ifndef FORWARDERSERVICE_H
#define FORWARDERSERVICE_H

#include <WiFiUdp.h>
#include <esp_now.h>

class ForwarderService {
  WiFiUDP &udp;

public:
  ForwarderService(WiFiUDP &udp);
  void serialToUdp();
  void udpToSerial();
};

#endif