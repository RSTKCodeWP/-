#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_now.h>
#include <WebServer.h>

#include "services/led_service.h"
#include "services/pref_service.h"
#include "services/server_service.h"
#include "services/network_service.h"
#include "services/forwarder_service.h"

const int SERIAL_BAUD = 57600;
const int MAVLINK_PORT = 14550;
const int LED_PIN = 2;

const String apSsid = "MAVLink Serial Forwarder";
const String apPassword = "mavlink123";
const IPAddress apIP(10, 10, 0, 1);

WiFiUDP udp;
Preferences preferences;

LedService ledService(LED_PIN, 100);
PrefService prefService(preferences);
ServerService serverService(prefService);
NetworkService networkService(apIP, apSsid, apPassword);
ForwarderService forwarderService(udp);

void setup()
{
  Serial.begin(SERIAL_BAUD);
  Serial.println("Starting...");

  String backpackSsid = prefService.loadBackpackSsid();
  String backpackPassword = prefService.loadBackpackPassword();

  ledService.setup();
  networkService.createAccessPoint();
  serverService.setup(backpackSsid, backpackPassword);
  networkService.connectToBackpackWiFi(backpackSsid, backpackPassword);

  if (networkService.isConnectedToBackpack())
  {
    udp.begin(MAVLINK_PORT);
    Serial.println("Listening on UDP port " + String(MAVLINK_PORT));
  }
  else
  {
    Serial.println();
    Serial.println("Failed to connect to Backpack WiFi.");
    Serial.println("Check if backpack WiFi ('" + backpackSsid + "') is available or connect to '" +
                   apSsid + "' network and open " + networkService.getApIp().toString() +
                   " in order to configure backpack SSID and password.");
  }

  Serial.println("Setup finished. Entering main loop...");
}

void loop()
{
  serverService.handle();
  ledService.update(networkService.isConnectedToBackpack());

  if (networkService.isConnectedToBackpack())
  {
    forwarderService.udpToSerial();
    forwarderService.serialToUdp();
  }

  delay(1);
}