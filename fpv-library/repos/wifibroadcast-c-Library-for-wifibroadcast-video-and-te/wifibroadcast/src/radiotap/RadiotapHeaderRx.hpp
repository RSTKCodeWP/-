//
// Created by consti10 on 05.10.23.
//

#ifndef WIFIBROADCAST_RADIOTAPHEADERPARSER_H
#define WIFIBROADCAST_RADIOTAPHEADERPARSER_H

#include <optional>

#include "../Ieee80211Header.hpp"
#include "RadiotapHeaderTx.hpp"

// Code for parsing the radiotap header coming from rtl8812au / rtl8812bu /
// other monitor mode wifi drivers

namespace radiotap::rx {

static constexpr int8_t DBM_INVALID = -128;         // INT8_MIN
static constexpr uint16_t QUALITY_INVALID = 65535;  // UINT16_MAX;

// NOTE: We use std::nullopt to indicate that the card doesn't report this value
struct KeyRfIndicators {
  // https://www.radiotap.org/fields/Antenna%20signal.html
  // IEEE80211_RADIOTAP_DBM_ANTSIGNAL
  std::optional<int8_t> radiotap_dbm_antsignal = std::nullopt;
  // IEEE80211_RADIOTAP_DBM_ANTNOISE
  std::optional<int8_t> radiotap_dbm_antnoise = std::nullopt;
  // IEEE80211_RADIOTAP_LOCK_QUALITY
  std::optional<uint16_t> radiotap_lock_quality = std::nullopt;
};

struct ParsedRxRadiotapPacket {
  const Ieee80211HeaderRaw *ieee80211Header;
  const uint8_t *payload;
  const std::size_t payloadSize;
  // --- Values generic (not per rf-path) ---
  bool radiotap_f_bad_fcs = false;
  KeyRfIndicators rf_adapter;
  // --- Values per rf-path -----
  // first one: antenna 1 (if reported by card), second one: antenna 2 (if
  // reported by card) ...
  std::vector<KeyRfIndicators> rf_paths;
};

// Returns std::nullopt if radiotap was unable to parse the header
// else return the *parsed information*
// This method is intentionally simple in that it only looks for data relevant
// to us (right now) inside the radiotap header.
static std::optional<ParsedRxRadiotapPacket> process_received_radiotap_packet(
    const uint8_t *pkt, const int pkt_len) {
  // int pktlen = hdr.caplen;
  int pktlen = pkt_len;
  //
  // Copy the value of this flag once present and process it after the loop is
  // done
  uint8_t tmp_copy_IEEE80211_RADIOTAP_FLAGS = 0;
  struct ieee80211_radiotap_iterator iterator {};
  // With AR9271 I get 39 as length of the radio-tap header
  // With my internal laptop wifi chip I get 36 as length of the radio-tap
  // header.
  int ret = ieee80211_radiotap_iterator_init(
      &iterator, (ieee80211_radiotap_header *)pkt, pktlen, nullptr);
  if (ret) {
    printf("malformed radiotap header (init returns %d)\n", ret);
    return std::nullopt;
  }

  // This is the best way I came up with of how to seperate the per-adaper and
  // per-rf-path rf metrics from one of another It assumes the driver reports
  // them in order - per-adapter first, then per-rf-paths (for as many rf paths
  // there are) AND the driver reports signal (noise,lock) if given for the
  // adapter and rf paths(s) alltogether Seems to be the case for all drivers,
  // definitely for the openhd supported ones.
  std::vector<int8_t> radiotap_dbm_antsignal;
  radiotap_dbm_antsignal.reserve(5);
  std::vector<int8_t> radiotap_dbm_antnoise;
  radiotap_dbm_antnoise.reserve(5);
  std::vector<uint16_t> radiotap_lock_quality;
  radiotap_lock_quality.reserve(5);

  int8_t n_antennas = 0;
  while (ret == 0) {
    ret = ieee80211_radiotap_iterator_next(&iterator);
    if (ret) {
      continue;
    }
    /* see if this argument is something we can use */
    switch (iterator.this_arg_index) {
      case IEEE80211_RADIOTAP_ANTENNA: {
        const auto antenna_idx = (int8_t)iterator.this_arg[0];
        const int8_t antenna_nr = antenna_idx + 1;
        if (antenna_nr > n_antennas) n_antennas = antenna_nr;
      } break;
      case IEEE80211_RADIOTAP_DBM_ANTSIGNAL: {
        int8_t value;
        std::memcpy(&value, iterator.this_arg, 1);
        radiotap_dbm_antsignal.push_back(value);
      } break;
      case IEEE80211_RADIOTAP_DBM_ANTNOISE: {
        int8_t value;
        std::memcpy(&value, iterator.this_arg, 1);
        radiotap_dbm_antnoise.push_back(value);
      } break;
      case IEEE80211_RADIOTAP_FLAGS:
        tmp_copy_IEEE80211_RADIOTAP_FLAGS = *(uint8_t *)(iterator.this_arg);
        break;
      case IEEE80211_RADIOTAP_LOCK_QUALITY: {
        uint16_t value = 0;
        // NOTE: Here we only copy 8 bits - the value is reported in radiotap as
        // uint16_t type, but only in the 0..100 range, so uint8_t would be
        // sufficient (and works)
        std::memcpy(&value, iterator.this_arg, 1);
        radiotap_lock_quality.push_back(value);
      } break;
      default:
        break;
    }
  } /* while more rt headers */
  if (ret != -ENOENT) {
    printf("Cannot parse radiotap header %d\n", ret);
    return std::nullopt;
  }
  bool has_radiotap_f_bad_fcs = false;
  if (tmp_copy_IEEE80211_RADIOTAP_FLAGS & IEEE80211_RADIOTAP_F_BADFCS) {
    // wifibroadcast::log::get_default()->warn("Got packet with bad fsc\n";
    has_radiotap_f_bad_fcs = true;
  }
  // the fcs is at the end of the packet
  if (tmp_copy_IEEE80211_RADIOTAP_FLAGS & IEEE80211_RADIOTAP_F_FCS) {
    //<<"Packet has IEEE80211_RADIOTAP_F_FCS";
    pktlen -= 4;
  }
  // assert(iterator._max_length==hdr.caplen);
  /* discard the radiotap header part */
  pkt += iterator._max_length;
  pktlen -= iterator._max_length;
  KeyRfIndicators adapter;
  // First fill in the adapter
  if (!radiotap_dbm_antsignal.empty()) {
    adapter.radiotap_dbm_antsignal = radiotap_dbm_antsignal[0];
  }
  if (!radiotap_dbm_antnoise.empty()) {
    adapter.radiotap_dbm_antnoise = radiotap_dbm_antnoise[0];
  }
  if (!radiotap_lock_quality.empty()) {
    adapter.radiotap_lock_quality = radiotap_lock_quality[0];
  }
  // Then per rf-path
  std::vector<KeyRfIndicators> rf_paths;
  rf_paths.resize(n_antennas);
  for (int i = 0; i < n_antennas; i++) {
    const int idx = i + 1;
    if (radiotap_dbm_antsignal.size() > idx) {
      rf_paths[i].radiotap_dbm_antsignal = radiotap_dbm_antsignal[idx];
    }
    if (radiotap_dbm_antnoise.size() > idx) {
      rf_paths[i].radiotap_dbm_antnoise = radiotap_dbm_antnoise[idx];
    }
    if (radiotap_lock_quality.size() > idx) {
      rf_paths[i].radiotap_lock_quality = radiotap_lock_quality[idx];
    }
  }
  const Ieee80211HeaderRaw *ieee80211Header = (Ieee80211HeaderRaw *)pkt;
  const uint8_t *payload = pkt + Ieee80211HeaderRaw::SIZE_BYTES;
  const std::size_t payloadSize =
      (std::size_t)pktlen - Ieee80211HeaderRaw::SIZE_BYTES;
  return ParsedRxRadiotapPacket{ieee80211Header,        payload, payloadSize,
                                has_radiotap_f_bad_fcs, adapter, rf_paths};
}

static std::string key_rf_indicators_to_string(
    const KeyRfIndicators &indicators) {
  std::stringstream ss;
  ss << "{";
  if (indicators.radiotap_dbm_antsignal.has_value()) {
    ss << (int)indicators.radiotap_dbm_antsignal.value() << " dBm : ";
  } else {
    ss << "N/A dBm : ";
  }
  if (indicators.radiotap_dbm_antnoise.has_value()) {
    ss << (int)indicators.radiotap_dbm_antnoise.value() << " dBm : ";
  } else {
    ss << "N/A dBm : ";
  }
  if (indicators.radiotap_lock_quality.has_value()) {
    ss << (int)indicators.radiotap_lock_quality.value() << " %";
  } else {
    ss << "N/A %";
  }
  ss << "}";
  return ss.str();
}

static std::string all_rf_path_to_string(
    const std::vector<KeyRfIndicators> &all_rf_path) {
  std::stringstream ss;
  ss << "RF Paths:";
  if (all_rf_path.empty()) {
    ss << "[Empty]";
    return ss.str();
  }
  int idx = 0;
  for (const auto &rf_path : all_rf_path) {
    ss << key_rf_indicators_to_string(rf_path);
    idx++;
  }
  return ss.str();
}

static std::string parsed_radiotap_to_string(
    const ParsedRxRadiotapPacket &parsed) {
  std::stringstream ss;
  ss << "{signal:noise:lock}\n";
  ss << "Adapter:" << key_rf_indicators_to_string(parsed.rf_adapter) << "\n";
  ss << all_rf_path_to_string(parsed.rf_paths);
  return ss.str();
}

}  // namespace radiotap::rx

#endif  // WIFIBROADCAST_RADIOTAPHEADERPARSER_H
