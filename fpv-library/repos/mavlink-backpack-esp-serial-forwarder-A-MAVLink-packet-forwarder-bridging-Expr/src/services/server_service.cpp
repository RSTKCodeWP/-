#include "server_service.h"

ServerService::ServerService(PrefService &prefs) : preferences(prefs), webServer(80) {}

void ServerService::setup(String ssid, String password)
{
  webServer.on(HOME_PATH, HTTP_GET, std::bind(&ServerService::handleRoot, this));
  webServer.on(SET_WIFI_PATH, HTTP_POST, std::bind(&ServerService::handleSaveWiFiCredentials, this));
  webServer.begin();
  currentSsid = ssid;
  currentPassword = password;
  Serial.println("Web server started.");
}

void ServerService::handle()
{
  webServer.handleClient();
}

void ServerService::handleRoot()
{
  Serial.println("Handling root page...");

  String html = "<!DOCTYPE html><html><body>"
                "<h2>MAVLink Serial Forwarder</h2>"
                "<form action='" +
                SET_WIFI_PATH + "' method='POST'>"
                                "SSID:<br><input name='ssid' value='" +
                currentSsid + "'><br/>"
                       "Password:<br><input type='password' name='password' value='" +
                currentPassword + "' >"
                           "<br><br>"
                           "<input type='submit' value='Save & Reboot'>"
                           "</form>"
                           "</body></html>";

  webServer.send(200, "text/html", html);
}

void ServerService::handleSaveWiFiCredentials()
{
  Serial.println("Handling POST request");
  String ssidInput = webServer.arg("ssid");
  String passwordInput = webServer.arg("password");
  ssidInput.trim();
  passwordInput.trim();
  if (ssidInput.length() == 0)
  {
    webServer.send(400, "text/plain", "SSID cannot be empty");
    return;
  }
  if (passwordInput.length() == 0)
  {
    webServer.send(400, "text/plain", "Password must be at least 8 characters");
    return;
  }

  preferences.saveBackpackWifiCredentials(ssidInput, passwordInput);

  Serial.println("Applying new WiFi credentials and restarting...");

  String html = "<!DOCTYPE html><html><body>"
                "<h2>WiFi Credentials Saved!</h2>"
                "<p>The new WiFi credentials have been saved. The device is now rebooting to apply the changes.</p>"
                "<p>Please wait a moment and then reconnect to the WiFi network.</p>"
                "<p>You may need to refresh this page (or navigate to 10.10.0.1) after the reboot.</p>"
                "</body></html>";
  webServer.send(200, "text/html", html);
  delay(2000);
  ESP.restart();
}