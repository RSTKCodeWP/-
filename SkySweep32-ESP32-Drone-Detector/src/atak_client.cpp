#include "atak_client.h"
#include <time.h>

ATAKClient atakClient;

ATAKClient::ATAKClient() : multicastPort(0), isConnected(false) {}

bool ATAKClient::begin(const char* ip, uint16_t port, const char* nodeCallsign) {
    multicastIP.fromString(ip);
    multicastPort = port;
    callsign = nodeCallsign;
    
    // Generate a unique ID based on MAC address
    uint8_t mac[6];
    WiFi.macAddress(mac);
    char uidBuf[32];
    snprintf(uidBuf, sizeof(uidBuf), "SkySweep-%02X%02X%02X%02X%02X%02X", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    uid = String(uidBuf);
    
    isConnected = true;
    return true;
}

String ATAKClient::generateTimeStr(uint32_t offsetSec) {
    struct tm timeinfo;
    if(!getLocalTime(&timeinfo)){
        // If time is not set, provide a dummy time (ATAK may reject if too old, but it's a fallback)
        // A better approach is getting time from GPS or NTP.
        return "2023-01-01T00:00:00Z";
    }
    
    time_t now;
    time(&now);
    now += offsetSec;
    struct tm* future = gmtime(&now);
    
    char buf[32];
    snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02dZ",
             future->tm_year + 1900, future->tm_mon + 1, future->tm_mday,
             future->tm_hour, future->tm_min, future->tm_sec);
    return String(buf);
}

void ATAKClient::sendCoT(const String& cotMessage) {
    if (WiFi.status() == WL_CONNECTED && isConnected) {
        udp.beginPacket(multicastIP, multicastPort);
        udp.print(cotMessage);
        udp.endPacket();
    }
}

void ATAKClient::sendHeartbeat(float lat, float lon, float alt, float course) {
    String nowStr = generateTimeStr(0);
    String staleStr = generateTimeStr(120); // stale in 2 minutes
    
    String cot = "<?xml version=\"1.0\"?>";
    cot += "<event version=\"2.0\" uid=\"" + uid + "\" type=\"a-f-G-U-C\" time=\"" + nowStr + "\" start=\"" + nowStr + "\" stale=\"" + staleStr + "\" how=\"m-g\">";
    cot += "<point lat=\"" + String(lat, 6) + "\" lon=\"" + String(lon, 6) + "\" hae=\"" + String(alt, 2) + "\" ce=\"9999999.0\" le=\"9999999.0\"/>";
    cot += "<detail>";
    cot += "<contact callsign=\"" + callsign + "\"/>";
    cot += "<track course=\"" + String(course, 2) + "\" speed=\"0.0\"/>";
    cot += "</detail>";
    cot += "</event>";
    
    sendCoT(cot);
}

void ATAKClient::sendThreat(const char* threatId, float lat, float lon, float alt, const char* type, const char* targetCallsign, float course) {
    String nowStr = generateTimeStr(0);
    String staleStr = generateTimeStr(60); // stale in 1 minute
    
    String cot = "<?xml version=\"1.0\"?>";
    cot += "<event version=\"2.0\" uid=\"" + String(threatId) + "\" type=\"" + String(type) + "\" time=\"" + nowStr + "\" start=\"" + nowStr + "\" stale=\"" + staleStr + "\" how=\"m-r\">";
    cot += "<point lat=\"" + String(lat, 6) + "\" lon=\"" + String(lon, 6) + "\" hae=\"" + String(alt, 2) + "\" ce=\"9999999.0\" le=\"9999999.0\"/>";
    cot += "<detail>";
    cot += "<contact callsign=\"" + String(targetCallsign) + "\"/>";
    cot += "<track course=\"" + String(course, 2) + "\" speed=\"0.0\"/>";
    cot += "</detail>";
    cot += "</event>";
    
    sendCoT(cot);
}
