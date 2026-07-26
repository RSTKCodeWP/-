#ifndef PREFSERVICE_H
#define PREFSERVICE_H

#include <Preferences.h>

class PrefService {
  Preferences preferences;

public:
  PrefService(Preferences &preferences);
  void saveBackpackWifiCredentials(String ssid, String password);
  String loadBackpackSsid();
  String loadBackpackPassword();
};

#endif