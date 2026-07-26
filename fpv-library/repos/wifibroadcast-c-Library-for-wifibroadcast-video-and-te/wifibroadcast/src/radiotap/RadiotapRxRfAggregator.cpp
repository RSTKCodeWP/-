//
// Created by consti10 on 05.10.23.
//

#include "RadiotapRxRfAggregator.h"

void RadiotapRxRfAggregator::add_if_valid(
    const radiotap::rx::KeyRfIndicators& indicators,
    RadiotapRxRfAggregator::KeyRfAggregators& agg,
    RadiotapRxRfAggregator::AggKeyRfIndicators& curr) {
  if (indicators.radiotap_dbm_antsignal.has_value()) {
    const auto radiotap_dbm_antsignal =
        indicators.radiotap_dbm_antsignal.value();
    auto opt_minmaxavg =
        agg.rssi_dbm.add_and_recalculate_if_needed(radiotap_dbm_antsignal);
    if (opt_minmaxavg.has_value()) {
      curr.rssi_dbm = opt_minmaxavg->avg;
    }
  }
  if (indicators.radiotap_dbm_antnoise.has_value()) {
    const auto radiotap_dbm_antnoise = indicators.radiotap_dbm_antnoise.value();
    auto opt_minmaxavg =
        agg.noise_dbm.add_and_recalculate_if_needed(radiotap_dbm_antnoise);
    if (opt_minmaxavg.has_value()) {
      curr.noise_dbm = opt_minmaxavg->avg;
    }
  }
  if (indicators.radiotap_lock_quality.has_value()) {
    const auto radiotap_lock_quality = indicators.radiotap_lock_quality.value();
    agg.signal_quality.add_signal_quality(radiotap_lock_quality);
    curr.card_signal_quality_perc =
        agg.signal_quality.get_current_signal_quality();
  }
}

void RadiotapRxRfAggregator::on_valid_openhd_packet(
    const radiotap::rx::ParsedRxRadiotapPacket& packet) {
  add_if_valid(packet.rf_adapter, m_agg_adapter, m_current_rx_stats.adapter);
  for (int i = 0; i < packet.rf_paths.size() && i < 2; i++) {
    const auto& rf_path = packet.rf_paths[i];
    auto& agg = i == 0 ? m_agg_antenna1 : m_agg_antenna2;
    auto& curr =
        i == 0 ? m_current_rx_stats.antenna1 : m_current_rx_stats.antenna2;
    add_if_valid(rf_path, agg, curr);
  }
  // if(m_wifi_cards[wlan_idx].type==wifibroadcast::WIFI_CARD_TYPE_RTL8812AU){
  //  RTL8812AU BUG - general value cannot be used, use max of antennas instead
  //   this_wifi_card_stats.card_dbm=std::max(this_wifi_card_stats.antenna1_dbm,this_wifi_card_stats.antenna2_dbm);
  // }*/
}

void RadiotapRxRfAggregator::set_debug_invalid_values(bool enable) {
  m_agg_adapter.rssi_dbm.set_debug_invalid_rssi(enable, 0);
  m_agg_adapter.noise_dbm.set_debug_invalid_rssi(enable, 0);
  m_agg_adapter.signal_quality.set_debug_invalid_signal_quality(enable);
}

void RadiotapRxRfAggregator::reset() {
  m_current_rx_stats = {};
  m_agg_adapter.reset();
  m_agg_antenna1.reset();
  m_agg_antenna2.reset();
}

std::string RadiotapRxRfAggregator::card_key_rf_indicators_to_string(
    const RadiotapRxRfAggregator::CardKeyRfIndicators& indicators) {
  return fmt::format(
      "RxRfStats[Adapter: {}:{}:{} | Antenna1: {}:{}:{} | Antenna2: {}:{}:{}]",
      indicators.adapter.rssi_dbm, indicators.adapter.noise_dbm,
      indicators.adapter.card_signal_quality_perc, indicators.antenna1.rssi_dbm,
      indicators.antenna1.noise_dbm,
      indicators.antenna1.card_signal_quality_perc,
      indicators.antenna2.rssi_dbm, indicators.antenna2.noise_dbm,
      indicators.antenna2.card_signal_quality_perc);
}

void RadiotapRxRfAggregator::debug_every_one_second() {
  const auto now = std::chrono::steady_clock::now();
  if (now - m_last_debug_log >= std::chrono::seconds(1)) {
    auto current = get_current();
    wifibroadcast::log::get_default()->debug(
        "{}",
        RadiotapRxRfAggregator::card_key_rf_indicators_to_string(current));
    m_last_debug_log = now;
  }
}

void RadiotapRxRfAggregator::KeyRfAggregators::reset() {
  rssi_dbm.reset();
  noise_dbm.reset();
  signal_quality.reset();
}
