//
// Created by consti10 on 17.12.22.
//

#ifndef WIFIBROADCAST_SRC_PCAP_HELPER_H_
#define WIFIBROADCAST_SRC_PCAP_HELPER_H_

#ifndef PACKET_QDISC_BYPASS
#define PACKET_QDISC_BYPASS 20  // Quick compile fix for buildroot ARMHF builds
#endif

#include <netpacket/packet.h>
#include <pcap/pcap.h>
#include <sys/socket.h>

#include <string>

namespace wifibroadcast::pcap_helper {

// debugging
static std::string tstamp_types_to_string(int *ts_types, int n) {
  std::stringstream ss;
  ss << "[";
  for (int i = 0; i < n; i++) {
    const char *name = pcap_tstamp_type_val_to_name(ts_types[i]);
    const char *description = pcap_tstamp_type_val_to_description(ts_types[i]);
    ss << name << "=" << description << ",";
  }
  ss << "]";
  return ss.str();
}

// Set timestamp type to PCAP_TSTAMP_HOST if available
static void iteratePcapTimestamps(pcap_t *ppcap) {
  int *availableTimestamps;
  const int nTypes = pcap_list_tstamp_types(ppcap, &availableTimestamps);
  wifibroadcast::log::get_default()->debug(
      "TS types:{}", wifibroadcast::pcap_helper::tstamp_types_to_string(
                         availableTimestamps, nTypes));
  //"N available timestamp types "<<nTypes<<"\n";
  for (int i = 0; i < nTypes; i++) {
    if (availableTimestamps[i] == PCAP_TSTAMP_HOST) {
      wifibroadcast::log::get_default()->debug("Setting timestamp to host");
      pcap_set_tstamp_type(ppcap, PCAP_TSTAMP_HOST);
    }
  }
  pcap_free_tstamp_types(availableTimestamps);
}

// creates a pcap handle for the given wlan and sets common params for wb
// returns nullptr on failure, a valid pcap handle otherwise
static pcap_t *open_pcap_rx(const std::string &wlan) {
  pcap_t *ppcap = nullptr;
  char errbuf[PCAP_ERRBUF_SIZE];
  ppcap = pcap_create(wlan.c_str(), errbuf);
  if (ppcap == nullptr) {
    wifibroadcast::log::get_default()->error(
        "Unable to open interface {} in pcap: {}", wlan.c_str(), errbuf);
    return nullptr;
  }
  iteratePcapTimestamps(ppcap);
  if (pcap_set_snaplen(ppcap, 4096) != 0)
    wifibroadcast::log::get_default()->error("set_snaplen failed");
  if (pcap_set_promisc(ppcap, 1) != 0)
    wifibroadcast::log::get_default()->error("set_promisc failed");
  // if (pcap_set_rfmon(ppcap, 1) !=0)
  // wifibroadcast::log::get_default()->error("set_rfmon failed");
  if (pcap_set_timeout(ppcap, -1) != 0)
    wifibroadcast::log::get_default()->error("set_timeout failed");
  // if (pcap_set_buffer_size(ppcap, 2048) !=0)
  // wifibroadcast::log::get_default()->error("set_buffer_size failed");
  //  Important: Without enabling this mode pcap buffers quite a lot of packets
  //  starting with version 1.5.0 !
  //  https://www.tcpdump.org/manpages/pcap_set_immediate_mode.3pcap.html
  if (pcap_set_immediate_mode(ppcap, true) != 0) {
    wifibroadcast::log::get_default()->warn(
        "pcap_set_immediate_mode failed: {}", pcap_geterr(ppcap));
  }
  if (pcap_activate(ppcap) != 0) {
    wifibroadcast::log::get_default()->error("pcap_activate failed: {}",
                                             pcap_geterr(ppcap));
  }
  if (pcap_setnonblock(ppcap, 1, errbuf) != 0) {
    wifibroadcast::log::get_default()->error("set_nonblock failed: {}", errbuf);
  }
  return ppcap;
}

// copy paste from svpcom
static pcap_t *open_pcap_tx(const std::string &wlan) {
  char errbuf[PCAP_ERRBUF_SIZE];
  pcap_t *p = pcap_create(wlan.c_str(), errbuf);
  if (p == nullptr) {
    wifibroadcast::log::get_default()->error(
        "Unable to open interface {} in pcap: {}", wlan.c_str(), errbuf);
  }
  if (pcap_set_snaplen(p, 4096) != 0)
    wifibroadcast::log::get_default()->warn("set_snaplen failed");
  if (pcap_set_promisc(p, 1) != 0)
    wifibroadcast::log::get_default()->warn("set_promisc failed");
  // if (pcap_set_rfmon(p, 1) !=0)
  // wifibroadcast::log::get_default()->warn("set_rfmon failed";
  //  Used to be -1 at some point, which is undefined behaviour. -1 can cause
  //  issues on older kernels, according to @Pete
  const int timeout_ms = 10;
  if (pcap_set_timeout(p, timeout_ms) != 0)
    wifibroadcast::log::get_default()->warn("set_timeout {} failed",
                                            timeout_ms);
  // if (pcap_set_buffer_size(p, 2048) !=0)
  // wifibroadcast::log::get_default()->warn("set_buffer_size failed";
  //  NOTE: Immediate not needed on TX
  if (pcap_activate(p) != 0) {
    wifibroadcast::log::get_default()->error("pcap_activate failed: {}",
                                             pcap_geterr(p));
  }
  // if (pcap_setnonblock(p, 1, errbuf) != 0)
  // wifibroadcast::log::get_default()->warn(string_format("set_nonblock failed:
  // %s", errbuf));
  return p;
}

static void set_tx_sock_qdisc_bypass(int fd) {
  /* setting PACKET_QDISC_BYPASS to 1 ?? */
  int32_t sock_qdisc_bypass = 1;
  const auto ret = setsockopt(fd, SOL_PACKET, PACKET_QDISC_BYPASS,
                              &sock_qdisc_bypass, sizeof(sock_qdisc_bypass));
  if (ret != 0) {
    wifibroadcast::log::get_default()->warn("Cannot set PACKET_QDISC_BYPASS");
  } else {
    wifibroadcast::log::get_default()->debug("PACKET_QDISC_BYPASS set");
  }
}
static void pcap_set_tx_sock_qdisc_bypass(pcap_t *handle) {
  auto fd = pcap_get_selectable_fd(handle);
  set_tx_sock_qdisc_bypass(fd);
}

}  // namespace wifibroadcast::pcap_helper

#endif  // WIFIBROADCAST_SRC_PCAP_HELPER_H_
