//
// Created by consti10 on 07.01.24.
//

#include <iostream>

#include "../src/WBTxRx.h"
#include "Helper.hpp"

static std::vector<std::shared_ptr<std::vector<uint8_t>>>
pull_all_buffered_packets(DummyLink& dummyLink) {
  std::vector<std::shared_ptr<std::vector<uint8_t>>> rx_packets;
  while (true) {
    auto packet = dummyLink.rx_radiotap();
    if (!packet) break;
    rx_packets.push_back(packet);
  }
  return rx_packets;
}

static void test_dummy_socket_impl() {
  auto dummy_air = std::make_shared<DummyLink>(true);
  auto dummy_gnd = std::make_shared<DummyLink>(false);
  dummy_gnd->set_drop_mode(0);
  auto dummy_packets1 = GenericHelper::createRandomDataBuffers(20, 1024, 1024);
  auto dummy_packets2 = GenericHelper::createRandomDataBuffers(20, 1024, 1024);
  for (auto& packet : dummy_packets1) {
    dummy_air->tx_radiotap(packet.data(), packet.size());
  }
  for (auto& packet : dummy_packets2) {
    dummy_gnd->tx_radiotap(packet.data(), packet.size());
  }
  // wait until all packets are received (hopefully)
  std::this_thread::sleep_for(std::chrono::seconds(1));
  auto rx_air = pull_all_buffered_packets(*dummy_air);
  auto rx_gnd = pull_all_buffered_packets(*dummy_gnd);
  GenericHelper::assertVectorsOfVectorsEqual(rx_gnd, dummy_packets1);
  GenericHelper::assertVectorsOfVectorsEqual(rx_air, dummy_packets2);
  std::cout << "Done test_dummy_socket_impl" << std::endl;
}

static std::shared_ptr<WBTxRx> make_txrx(bool air) {
  auto card = wifibroadcast::create_card_emulate(air);
  std::vector<wifibroadcast::WifiCard> cards;
  cards.push_back(card);
  WBTxRx::Options options_txrx{};
  options_txrx.log_all_received_validated_packets = true;
  options_txrx.rx_radiotap_debug_level = 3;
  options_txrx.advanced_debugging_rx = true;
  options_txrx.use_gnd_identifier = !air;
  options_txrx.log_all_received_packets = true;
  auto radiotap_header_holder_tx = std::make_shared<RadiotapHeaderTxHolder>();
  std::shared_ptr<WBTxRx> txrx =
      std::make_shared<WBTxRx>(cards, options_txrx, radiotap_header_holder_tx);
  //
  return txrx;
}

static void test_wb_tx_rx_dummy() {
  auto tx_rx_air = make_txrx(true);
  auto tx_rx_gnd = make_txrx(false);
  tx_rx_air->start_receiving();
  tx_rx_gnd->start_receiving();

  auto dummy_packets1 = GenericHelper::createRandomDataBuffers(20, 1024, 1024);
  auto radiotap_header_holder_tx = std::make_shared<RadiotapHeaderTxHolder>();

  for (auto& packet : dummy_packets1) {
    tx_rx_air->tx_inject_packet(5, packet.data(), packet.size(),
                                radiotap_header_holder_tx->thread_safe_get(),
                                true);
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
  }
  // Sleep a bit to make sure all queues are empty
  std::this_thread::sleep_for(std::chrono::seconds(1));
  const auto rx_stats = tx_rx_gnd->get_rx_stats();
  // RX should have received all the packets
  assert(rx_stats.count_p_valid == dummy_packets1.size());
  tx_rx_air->stop_receiving();
  tx_rx_gnd->stop_receiving();
}

int main(int argc, char* const* argv) {
  test_dummy_socket_impl();
  test_wb_tx_rx_dummy();
  return 0;
}
