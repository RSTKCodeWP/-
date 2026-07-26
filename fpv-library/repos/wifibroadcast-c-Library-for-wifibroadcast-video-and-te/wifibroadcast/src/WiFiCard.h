//
// Created by consti10 on 13.09.23.
//

#ifndef WIFIBROADCAST_WIFICARD_H
#define WIFIBROADCAST_WIFICARD_H

#include <sstream>
#include <string>
#include <vector>

namespace wifibroadcast {
// In OpenHD, we have a quite extensive WiFiCard abstraction -
// in wifibroadcast, we are a bit simpler
// (But we require info for quirks)
// RTL8812AU driver requires a quirk regarding rssi
static constexpr auto WIFI_CARD_TYPE_UNKNOWN = 0;
static constexpr auto WIFI_CARD_TYPE_RTL8812AU = 1;
static constexpr auto WIFI_CARD_TYPE_EMULATE_AIR = 2;
static constexpr auto WIFI_CARD_TYPE_EMULATE_GND = 3;
struct WifiCard {
  std::string name;
  int type;
};
static std::vector<std::string> get_wifi_card_names(
    const std::vector<WifiCard>& cards) {
  std::vector<std::string> ret;
  for (const auto& card : cards) {
    ret.push_back(card.name);
  }
  return ret;
}

static WifiCard create_card_emulate(bool is_air_card) {
  return WifiCard{
      is_air_card ? "emu_air" : "emu_gnd",
      is_air_card ? WIFI_CARD_TYPE_EMULATE_AIR : WIFI_CARD_TYPE_EMULATE_GND};
}
}  // namespace wifibroadcast

#endif  // WIFIBROADCAST_WIFICARD_H
