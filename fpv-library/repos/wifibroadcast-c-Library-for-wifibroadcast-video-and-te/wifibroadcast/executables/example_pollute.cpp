//
// Created by consti10 on 09.08.23.
//

#include "../src/HelperSources/RandomBufferPot.hpp"
#include "../src/WBStreamRx.h"
#include "../src/WBStreamTx.h"
#include "../src/WBTxRx.h"
#include "../src/wifibroadcast_spdlog.h"

/**
 * Simple demo application that pollutes a given wifi space
 * with a lot of packets with a non-openhd fixed MAC address.
 */
int main(int argc, char *const *argv) {
  std::string card = "wlx244bfeb71c05";
  int sleep_time_ms = 10;  // 100 pps
  int opt;
  while ((opt = getopt(argc, argv, "w:s:")) != -1) {
    switch (opt) {
      case 'w':
        card = optarg;
        break;
      case 's':
        sleep_time_ms = std::atoi(optarg);
        break;
      default: /* '?' */
      show_usage:
        fprintf(stderr,
                "Example pollute %s [-w wifi card to use] [-s sleep time "
                "bwteen packets, in milliseconds]\n",
                argv[0]);
        exit(1);
    }
  }

  // Create the Tx-RX
  std::vector<wifibroadcast::WifiCard> cards;
  wifibroadcast::WifiCard tmp_card{card, 1};
  cards.push_back(tmp_card);
  WBTxRx::Options options_txrx{};
  options_txrx.pcap_rx_set_direction = true;
  options_txrx.enable_non_openhd_mode = true;
  options_txrx.tx_without_pcap = false;
  options_txrx.debug_tx_injection_time = true;
  options_txrx.tx_without_pcap = true;

  auto radiotap_header_holder = std::make_shared<RadiotapHeaderTxHolder>();
  std::shared_ptr<WBTxRx> txrx =
      std::make_shared<WBTxRx>(cards, options_txrx, radiotap_header_holder);
  // We do not need receive in this mode
  // txrx->start_receiving();
  wifibroadcast::log::get_default()->debug("Example pollute {}ms",
                                           sleep_time_ms);

  auto lastLog = std::chrono::steady_clock::now();
  int packet_index = 0;
  while (true) {
    auto message = GenericHelper::createRandomDataBuffer(1024);
    packet_index++;

    auto header = radiotap_header_holder->thread_safe_get();
    txrx->tx_inject_packet(0, (uint8_t *)message.data(), message.size(), header,
                           false);
    // About 100pps
    std::this_thread::sleep_for(std::chrono::milliseconds(sleep_time_ms));

    const auto elapsed_since_last_log =
        std::chrono::steady_clock::now() - lastLog;
    if (elapsed_since_last_log > std::chrono::seconds(4)) {
      lastLog = std::chrono::steady_clock::now();
      auto txStats = txrx->get_tx_stats();
      std::cout << txStats << std::endl;
    }
  }
}