//
// Created by consti10 on 07.10.23.
// Uses WBTxRx to listen to all (openhd and non openhd) traffic
//
#include "../src/WBTxRx.h"
#include "../src/wifibroadcast_spdlog.h"

int main(int argc, char *const *argv) {
  std::string card = "wlxac9e17596103";
  bool pcap_setdirection = true;
  int opt;
  while ((opt = getopt(argc, argv, "w:d")) != -1) {
    switch (opt) {
      case 'w':
        card = optarg;
        break;
      case 'd':
        pcap_setdirection = false;
        break;
      default: /* '?' */
      show_usage:
        fprintf(stderr, "test_listen -w [wifi card to listen on] %s\n",
                argv[0]);
        exit(1);
    }
  }

  std::vector<wifibroadcast::WifiCard> cards;
  wifibroadcast::WifiCard tmp_card{card, 1};
  cards.push_back(tmp_card);
  WBTxRx::Options options_txrx{};
  // options_txrx.pcap_rx_set_direction= false;
  options_txrx.pcap_rx_set_direction = pcap_setdirection;
  options_txrx.log_all_received_validated_packets = true;
  options_txrx.rx_radiotap_debug_level = 3;
  options_txrx.advanced_debugging_rx = true;
  auto radiotap_header_holder_tx = std::make_shared<RadiotapHeaderTxHolder>();
  std::shared_ptr<WBTxRx> txrx =
      std::make_shared<WBTxRx>(cards, options_txrx, radiotap_header_holder_tx);

  txrx->start_receiving();

  auto lastLog = std::chrono::steady_clock::now();
  while (true) {
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    // auto txStats=txrx->get_tx_stats();
    auto rxStats = txrx->get_rx_stats();
    auto rx_stats_card0 = txrx->get_rx_stats_for_card(0);
    auto rx_rf_stats_card0 = txrx->get_rx_rf_stats_for_card(0);
    // std::cout<<txStats<<"\n";
    std::cout << rxStats << "\n";
    std::cout << rx_stats_card0 << std::endl;
    std::cout << rx_rf_stats_card0 << std::endl;
  }
}