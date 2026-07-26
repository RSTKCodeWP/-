#ifndef ATAK_CLIENT_H
#define ATAK_CLIENT_H

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>

class ATAKClient {
private:
    WiFiUDP udp;
    IPAddress multicastIP;
    uint16_t multicastPort;
    String uid;
    String callsign;
    bool isConnected;

    String generateTimeStr(uint32_t offsetSec = 0);
    void sendCoT(const String& cotMessage);

public:
    ATAKClient();
    
    bool begin(const char* ip = "239.2.3.1", uint16_t port = 6969, const char* nodeCallsign = "SkySweep32");
    
    void sendHeartbeat(float lat, float lon, float alt, float course = 0.0);
    void sendThreat(const char* threatId, float lat, float lon, float alt, const char* type = "a-u-A", const char* targetCallsign = "UAV", float course = 0.0);
};

extern ATAKClient atakClient;

#endif // ATAK_CLIENT_H
