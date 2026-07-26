//
// Created by consti10 on 13.09.23.
//

#ifndef WIFIBROADCAST_RADIOTAPHEADERHOLDER_H
#define WIFIBROADCAST_RADIOTAPHEADERHOLDER_H

#include <mutex>

#include "../wifibroadcast_spdlog.h"
#include "RadiotapHeaderTx.hpp"

/**
 * Thread-safe holder for a (TX) radiotap header.
 * ( getter / setter) -
 * We modify the tx radiotap header in openhd at run time.
 * This kind of "atomic behaviour" is enough for openhd wifibroadcast.
 * TODO: Use std::atomic instead of std::mutex
 */
class RadiotapHeaderTxHolder {
 public:
  explicit RadiotapHeaderTxHolder() {
    m_console = wifibroadcast::log::get_default();
  }
  void thread_safe_set(RadiotapHeaderTx::UserSelectableParams params) {
    m_radioTapHeaderParams = params;
    update_locked();
  }
  RadiotapHeaderTx thread_safe_get() {
    std::lock_guard<std::mutex> guard(m_radiotap_header_mutex);
    return m_radiotap_header;
  }

 public:
  void update_mcs_index(uint8_t mcs_index) {
    m_console->debug("update_mcs_index {}", mcs_index);
    m_radioTapHeaderParams.mcs_index = mcs_index;
    update_locked();
  }
  void update_channel_width(int width_mhz) {
    m_console->debug("update_channel_width {}", width_mhz);
    m_radioTapHeaderParams.bandwidth = width_mhz;
    update_locked();
  }
  void update_stbc(int stbc) {
    m_console->debug("update_stbc {}", stbc);
    if (stbc < 0 || stbc > 3) {
      m_console->warn("Invalid stbc index");
      return;
    }
    m_radioTapHeaderParams.stbc = stbc;
    update_locked();
  }
  void update_guard_interval(bool short_gi) {
    m_radioTapHeaderParams.short_gi = short_gi;
    update_locked();
  }
  void update_ldpc(bool ldpc) {
    m_radioTapHeaderParams.ldpc = ldpc;
    update_locked();
  }
  void update_set_flag_tx_no_ack(bool enable) {
    m_radioTapHeaderParams.set_flag_tx_no_ack = enable;
    update_locked();
  }

 private:
  void update_locked() {
    auto header = RadiotapHeaderTx{m_radioTapHeaderParams};
    // Swap out the actual header (thread-safe)
    std::lock_guard<std::mutex> guard(m_radiotap_header_mutex);
    m_radiotap_header = header;
  }

 private:
  std::shared_ptr<spdlog::logger> m_console;
  RadiotapHeaderTx::UserSelectableParams m_radioTapHeaderParams{};
  RadiotapHeaderTx m_radiotap_header{RadiotapHeaderTx::UserSelectableParams{}};
  std::mutex m_radiotap_header_mutex;
};

#endif  // WIFIBROADCAST_RADIOTAPHEADERHOLDER_H
