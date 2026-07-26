#include "network_service.h"
#include <Arduino.h>

NetworkService::NetworkService(IPAddress ip, String ssid, String password) : apIP(ip), apSsid(ssid), apPassword(password) {}

void NetworkService::createAccessPoint()
{
  WiFi.mode(WIFI_AP_STA);
  WiFi.disconnect();
  WiFi.softAPConfig(apIP, apIP, IPAddress(255, 255, 255, 0));
  WiFi.softAP(apSsid, apPassword);
  Serial.println("WiFi AP Started.");
}

void NetworkService::connectToBackpackWiFi(String ssid, String password)
{
  WiFi.begin(ssid, password);
  Serial.print("Connecting to Backpack WiFi");

  int retry = 0;
  while (!isConnectedToBackpack() && retry < 10)
  {
    delay(1000);
    Serial.print(".");
    ++retry;
  }

  if (isConnectedToBackpack())
  {
    Serial.println();
    Serial.println("WiFi connected!");
  }
}

bool NetworkService::isConnectedToBackpack()
{
  return WiFi.status() == WL_CONNECTED;
}

IPAddress NetworkService::getApIp()
{
  return apIP;
}
