//
// Created by consti10 on 25.07.23.
//

#ifndef WIFIBROADCAST_DUMMYSTREAMGENERATOR_HPP
#define WIFIBROADCAST_DUMMYSTREAMGENERATOR_HPP

#include <cstdint>
#include <functional>
#include <thread>
#include <utility>

#include "RandomBufferPot.hpp"
#include "SchedulingHelper.hpp"

/**
 * Generates as close as possible a stream of data packets with a target packets
 * per second packet rate.
 */
class DummyStreamGenerator {
 public:
  typedef std::function<void(const uint8_t* data, int data_len)>
      OUTPUT_DATA_CALLBACK;

  DummyStreamGenerator(OUTPUT_DATA_CALLBACK cb, int packet_size)
      : m_cb(std::move(cb)), m_packet_size(packet_size) {
    m_random_buffer_pot =
        std::make_unique<RandomBufferPot>(1000, m_packet_size);
  };
  ~DummyStreamGenerator() { stop(); }

  void set_target_pps(int pps) { m_target_pps = pps; }

  void start() {
    m_terminate = false;
    m_producer_thread =
        std::make_unique<std::thread>([this]() { loop_generate_data(); });
  }
  void stop() {
    m_terminate = true;
    if (m_producer_thread) {
      m_producer_thread->join();
      m_producer_thread = nullptr;
    }
  }
  void loop_generate_data() {
    SchedulingHelper::set_thread_params_max_realtime("DummyStreamGenerator");
    std::chrono::steady_clock::time_point last_packet =
        std::chrono::steady_clock::now();
    const uint64_t delay_between_packets_ns = 1000 * 1000 * 1000 / m_target_pps;
    const auto delay_between_packets =
        std::chrono::nanoseconds(delay_between_packets_ns);
    wifibroadcast::log::get_default()->debug(
        "Target pps:{} delta between packets:{}", m_target_pps,
        MyTimeHelper::R(delay_between_packets));
    while (!m_terminate) {
      last_packet = std::chrono::steady_clock::now();
      // wifibroadcast::log::get_default()->debug("Delay between packets:
      // {}",std::chrono::duration_cast<std::chrono::nanoseconds>(delay_between_packets).count());
      auto buff = m_random_buffer_pot->get_next_buffer();
      m_cb(buff->data(), buff->size());
      const auto next_packet_tp =
          last_packet + delay_between_packets -
          std::chrono::nanoseconds(200);  // minus Xns to better hit the target
      if (std::chrono::steady_clock::now() >= next_packet_tp) {
        // wifibroadcast::log::get_default()->warn("Cannot keep up with the
        // wanted tx pps");
        n_times_cannot_keep_up_wanted_pps++;
      }
      while (std::chrono::steady_clock::now() < next_packet_tp) {
        // busy wait
      }
    }
  }
  int n_times_cannot_keep_up_wanted_pps = 0;

 private:
  const int m_packet_size = 1400;
  const OUTPUT_DATA_CALLBACK m_cb;
  int m_target_pps = 100;
  std::unique_ptr<std::thread> m_producer_thread;
  std::unique_ptr<RandomBufferPot> m_random_buffer_pot;
  bool m_terminate = false;
};

#endif  // WIFIBROADCAST_DUMMYSTREAMGENERATOR_HPP
