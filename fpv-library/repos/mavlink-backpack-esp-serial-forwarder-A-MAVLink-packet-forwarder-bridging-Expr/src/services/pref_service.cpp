#include "pref_service.h"

PrefService::PrefService(Preferences &prefs) : preferences(prefs) {}

void PrefService::saveBackpackWifiCredentials(String ssid, String password)
{
  preferences.begin("backpack_wifi", false);
  preferences.putString("ssid", ssid);
  preferences.putString("password", password);
  preferences.end();
  Serial.println("Backpack WiFi credentials saved.");
}

String PrefService::loadBackpackSsid()
{
  String ssid = "";
  preferences.begin("backpack_wifi", true);
  ssid = preferences.getString("ssid", "");
  preferences.end();
  Serial.println("Backpack WiFi SSID loaded: " + ssid);
  return ssid;
}

String PrefService::loadBackpackPassword()
{
  String password = "";
  preferences.begin("backpack_wifi", true);
  password = preferences.getString("password", "");
  preferences.end();
  Serial.println("Backpack WiFi password loaded: " + password);
  return password;
}

