#ifndef NETWORKSERVICE_H
#define NETWORKSERVICE_H

#include <WiFi.h>

class NetworkService {
  const String apSsid;
  const String apPassword;
  const IPAddress apIP;

public:
  NetworkService(IPAddress apIP, String ssid, String password);
  void createAccessPoint();
  void connectToBackpackWiFi(String ssid, String password);
  bool isConnectedToBackpack();
  IPAddress getApIp();
};

#endif
