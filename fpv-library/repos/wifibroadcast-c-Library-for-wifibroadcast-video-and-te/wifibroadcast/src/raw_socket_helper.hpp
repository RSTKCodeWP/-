//
// Created by consti10 on 16.08.23.
//

#ifndef WIFIBROADCAST_RAW_SOCKET_HELPER_HPP
#define WIFIBROADCAST_RAW_SOCKET_HELPER_HPP

#include <net/if.h>
#include <netpacket/packet.h>
#include <sys/ioctl.h>

#include "SocketHelper.hpp"
#include "wifibroadcast_spdlog.h"

// taken from
// https://github.com/OpenHD/Open.HD/blob/2.0/wifibroadcast-base/tx_rawsock.c#L86
// open wifi interface using a socket (somehow this works ?!)
static int open_wifi_interface_as_raw_socket(const std::string &wifi) {
  auto console = wifibroadcast::log::create_or_get("raw_sock");
  struct sockaddr_ll ll_addr {};
  struct ifreq ifr {};
  int sock = socket(AF_PACKET, SOCK_RAW, 0);
  if (sock == -1) {
    console->error("open socket failed {} {}", wifi.c_str(), strerror(errno));
  }

  ll_addr.sll_family = AF_PACKET;
  ll_addr.sll_protocol = 0;
  ll_addr.sll_halen = ETH_ALEN;

  strncpy(ifr.ifr_name, wifi.c_str(), IFNAMSIZ);

  if (ioctl(sock, SIOCGIFINDEX, &ifr) < 0) {
    console->error("ioctl(SIOCGIFINDEX) failed");
  }

  ll_addr.sll_ifindex = ifr.ifr_ifindex;

  if (ioctl(sock, SIOCGIFHWADDR, &ifr) < 0) {
    console->error("ioctl(SIOCGIFHWADDR) failed");
  }

  memcpy(ll_addr.sll_addr, ifr.ifr_hwaddr.sa_data, ETH_ALEN);

  if (bind(sock, (struct sockaddr *)&ll_addr, sizeof(ll_addr)) == -1) {
    close(sock);
    console->error("bind failed");
  }
  SocketHelper::debug_send_rcv_timeout(sock, console);
  // const auto wanted_send_timeout=std::chrono::milliseconds(20);
  // console->debug("Setting send timeout to
  // {}",MyTimeHelper::R(wanted_send_timeout));
  // SocketHelper::set_socket_send_rcv_timeout(sock,std::chrono::milliseconds(20),
  // true);
  //  debug the timeout after setting
  // SocketHelper::debug_send_rcv_timeout(sock,console);
  //  buff size
  SocketHelper::set_socket_send_rcv_buffsize(sock, 1510 * 1, true);
  SocketHelper::debug_send_rcv_buffsize(sock, console);
  // const int wanted_sendbuff_bytes=128*1024*1024;
  // SocketHelper::set_socket_send_rcv_buffsize(sock,wanted_sendbuff_bytes,
  // true);
  //  buff size end
  console->debug("{} socket opened", wifi);
  return sock;
}

#endif  // WIFIBROADCAST_RAW_SOCKET_HELPER_HPP
