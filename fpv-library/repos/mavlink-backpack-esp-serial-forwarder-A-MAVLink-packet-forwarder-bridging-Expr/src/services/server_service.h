#ifndef SERVER_SERVICE_H
#define SERVER_SERVICE_H

#include <WebServer.h>
#include "pref_service.h"

class ServerService {
  const String HOME_PATH = "/";
  const String SET_WIFI_PATH = "/set-wifi";

  PrefService &preferences;
  WebServer webServer;

  String currentSsid = "";
  String currentPassword = "";

public:
  ServerService(PrefService &preferences);
  void setup(String ssid, String password);
  void handle();
private:
  void handleRoot();
  void handleSaveWiFiCredentials();
};

#endif