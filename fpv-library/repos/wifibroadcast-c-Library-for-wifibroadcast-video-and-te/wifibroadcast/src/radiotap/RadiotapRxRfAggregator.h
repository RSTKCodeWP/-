//
// Created by consti10 on 05.10.23.
//

#ifndef WIFIBROADCAST_RADIOTAPRXRFAGGREGATOR_H
#define WIFIBROADCAST_RADIOTAPRXRFAGGREGATOR_H

#include <chrono>

#include "RSSIAccumulator.hpp"
#include "RadiotapHeaderRx.hpp"
#include "SignalQualityAccumulator.hpp"

/**
 * Aggregates all key rf metrics.
 */
class RadiotapRxRfAggregator {
 public:
  // Aggregated (average) key rf metrics
  struct AggKeyRfIndicators {
    // -128 = invalid, [-127..-1] otherwise
    int8_t rssi_dbm = -128;
    int8_t noise_dbm = -128;
    // [0,100] if valid, -1 otherwise
    int8_t card_signal_quality_perc = -1;
  };
  struct CardKeyRfIndicators {
    // ------------- PER ADAPTER ------------
    AggKeyRfIndicators adapter;
    // -------------- PER ANTENNA ----------
    AggKeyRfIndicators antenna1;
    AggKeyRfIndicators antenna2;
  };
  // Called every time a valid openhd packet is received
  void on_valid_openhd_packet(
      const radiotap::rx::ParsedRxRadiotapPacket& packet);
  // debugging of the 'invalid values reported by driver' issue
  void set_debug_invalid_values(bool enable);
  // Reset all rf metrics
  void reset();
  // TODO: Thread safety ?
  CardKeyRfIndicators get_current() { return m_current_rx_stats; }
  static std::string card_key_rf_indicators_to_string(
      const CardKeyRfIndicators& indicators);
  void debug_every_one_second();

 private:
  struct KeyRfAggregators {
    RSSIAccumulator rssi_dbm;
    RSSIAccumulator noise_dbm;
    SignalQualityAccumulator signal_quality;
    void reset();
  };
  static void add_if_valid(const radiotap::rx::KeyRfIndicators& indicators,
                           RadiotapRxRfAggregator::KeyRfAggregators& agg,
                           RadiotapRxRfAggregator::AggKeyRfIndicators& curr);
  KeyRfAggregators m_agg_adapter;
  KeyRfAggregators m_agg_antenna1;
  KeyRfAggregators m_agg_antenna2;
  CardKeyRfIndicators m_current_rx_stats{};
  std::chrono::steady_clock::time_point m_last_debug_log =
      std::chrono::steady_clock::now();
};

static std::ostream& operator<<(
    std::ostream& strm,
    const RadiotapRxRfAggregator::CardKeyRfIndicators& data) {
  strm << RadiotapRxRfAggregator::card_key_rf_indicators_to_string(data);
  return strm;
}

#endif  // WIFIBROADCAST_RADIOTAPRXRFAGGREGATOR_H
