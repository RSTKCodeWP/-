//
// Created by consti10 on 02.07.23.
//

#ifndef WIFIBROADCAST_WBSTREAMTXUDP_H
#define WIFIBROADCAST_WBSTREAMTXUDP_H

#include "../WBStreamRx.h"
#include "SocketHelper.hpp"

/**
 * Uses UDP for data in instead of callback
 */
class WBStreamTxUDP {
 public:
  WBStreamTxUDP(std::shared_ptr<WBTxRx> txrx, WBStreamTx::Options options,
                int fec_k, int in_udp_port) {
    radiotap_header_holder = std::make_shared<RadiotapHeaderTxHolder>();
    wb_tx = std::make_unique<WBStreamTx>(txrx, options, radiotap_header_holder);
    last_udp_in_packet_ts_ms = MyTimeHelper::get_curr_time_ms();
    // we need to buffer packets due to udp
    std::vector<std::shared_ptr<std::vector<uint8_t>>> block;
    auto cb_udp_in = [this, &options, &block, &fec_k](
                         const uint8_t *payload,
                         const std::size_t payloadSize) {
      last_udp_in_packet_ts_ms = MyTimeHelper::get_curr_time_ms();
      if (options.enable_fec) {
        // We need to buffer data here for FEC
        auto packet = std::make_shared<std::vector<uint8_t>>(
            payload, payload + payloadSize);
        block.push_back(packet);
        if (block.size() == fec_k) {
          wb_tx->try_enqueue_block(block, 100, 20);
          block.resize(0);
        }
      } else {
        auto packet = std::make_shared<std::vector<uint8_t>>(
            payload, payload + payloadSize);
        wb_tx->try_enqueue_packet(packet);
      }
    };
    m_udp_in = std::make_unique<SocketHelper::UDPReceiver>(
        SocketHelper::ADDRESS_LOCALHOST, in_udp_port, cb_udp_in);
    m_udp_in->runInBackground();
    auto console = wifibroadcast::log::create_or_get(
        fmt::format("udp{}->radio_port{}", in_udp_port, options.radio_port));
    console->info("Expecting data on localhost:{}", in_udp_port);
    if (options.enable_fec) {
      console->warn("This buffers {} packets on udp in !", fec_k);
    }
  }
  std::unique_ptr<WBStreamTx> wb_tx;
  std::shared_ptr<RadiotapHeaderTxHolder> radiotap_header_holder;
  std::unique_ptr<SocketHelper::UDPReceiver> m_udp_in;
  // helps to catch a common newbie mistake of forgetting that this buffers in
  // packets
  int last_udp_in_packet_ts_ms;

 private:
};

#endif  // WIFIBROADCAST_WBSTREAMTXUDP_H
