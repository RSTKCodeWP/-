//
// Created by consti10 on 05.10.23.
// A lot of simple util code for debugging / printing
//

#ifndef WIFIBROADCAST_RADIOTAP_UTIL_HPP
#define WIFIBROADCAST_RADIOTAP_UTIL_HPP

#include "../wifibroadcast_spdlog.h"
#include "RadiotapHeaderTx.hpp"
namespace radiotap::util {

static std::string toStringRadiotapFlags(uint8_t flags) {
  std::stringstream ss;
  ss << "All IEEE80211_RADIOTAP flags: [";
  if (flags & IEEE80211_RADIOTAP_F_CFP) {
    ss << "CFP,";
  }
  if (flags & IEEE80211_RADIOTAP_F_SHORTPRE) {
    ss << "SHORTPRE,";
  }
  if (flags & IEEE80211_RADIOTAP_F_WEP) {
    ss << "WEP,";
  }
  if (flags & IEEE80211_RADIOTAP_F_FRAG) {
    ss << "FRAG,";
  }
  if (flags & IEEE80211_RADIOTAP_F_FCS) {
    ss << "FCS,";
  }
  if (flags & IEEE80211_RADIOTAP_F_DATAPAD) {
    ss << "DATAPAD,";
  }
  if (flags & IEEE80211_RADIOTAP_F_BADFCS) {
    ss << "BADFCS";
  }
  ss << "]";
  return ss.str();
}
// http://www.radiotap.org/fields/Channel.html
static std::string toStringRadiotapChannel(uint16_t frequency, uint16_t flags) {
  std::stringstream ss;
  ss << "All Radiotap channel values: [";
  ss << "Frequency[" << (int)frequency << "],";
  if (flags & IEEE80211_CHAN_CCK) {
    ss << "CHAN_CCK,";
  }
  if (flags & IEEE80211_CHAN_OFDM) {
    ss << "CHAN_OFDM,";
  }
  if (flags & IEEE80211_CHAN_2GHZ) {
    ss << "CHAN_2GHZ,";
  }
  if (flags & IEEE80211_CHAN_5GHZ) {
    ss << "CHAN_5GHZ,";
  }
  if (flags & IEEE80211_CHAN_DYN) {
    ss << "CHAN_DYN,";
  }
  if (flags & IEEE80211_CHAN_HALF) {
    ss << "CHAN_HALF,";
  }
  if (flags & IEEE80211_CHAN_QUARTER) {
    ss << "CHAN_QUARTER,";
  }
  ss << "]";
  return ss.str();
}
// http://www.radiotap.org/fields/RX%20flags.html
static std::string toStringRadiotapRXFlags(uint16_t rxFlags) {
  std::stringstream ss;
  ss << "All IEEE80211_RADIOTAP_RX_FLAGS values: [";
  if (rxFlags & IEEE80211_RADIOTAP_F_RX_BADPLCP) {
    ss << "RX_BADPLCP,";
  }
  ss << "]";
  return ss.str();
}
// http://www.radiotap.org/fields/TX%20flags.html
static std::string toStringRadiotapTXFlags(const uint16_t txFlags) {
  std::stringstream ss;
  ss << "All TX FLAGS: [";
  if (txFlags & IEEE80211_RADIOTAP_F_TX_FAIL) {
    ss << "TX_FAIL,";
  }
  if (txFlags & IEEE80211_RADIOTAP_F_TX_CTS) {
    ss << "TX_CTS,";
  }
  if (txFlags & IEEE80211_RADIOTAP_F_TX_RTS) {
    ss << "TX_RTS,";
  }
  if (txFlags & IEEE80211_RADIOTAP_F_TX_NOACK) {
    ss << "TX_NOACK,";
  }
  ss << "]";
  return ss.str();
}

// http://www.radiotap.org/fields/MCS.html
static std::string toStringRadiotapMCS(uint8_t known, uint8_t flags,
                                       uint8_t mcs) {
  std::stringstream ss;
  ss << "MCS Stuff: [";
  if (known & IEEE80211_RADIOTAP_MCS_HAVE_BW) {
    ss << "HAVE_BW[";
    uint8_t bandwidth = flags & IEEE80211_RADIOTAP_MCS_BW_MASK;
    switch (bandwidth) {
      case IEEE80211_RADIOTAP_MCS_BW_20:
        ss << "BW_20";
        break;
      case IEEE80211_RADIOTAP_MCS_BW_40:
        ss << "BW_40";
        break;
      case IEEE80211_RADIOTAP_MCS_BW_20L:
        ss << "BW_20L";
        break;
      case IEEE80211_RADIOTAP_MCS_BW_20U:
        ss << "BW_20U";
        break;
      default:
        ss << "Unknown";
    }
    ss << "],";
  }
  if (known & IEEE80211_RADIOTAP_MCS_HAVE_MCS) {
    ss << "HAVE_MCS[" << (int)mcs << "],";
  }
  if (known & IEEE80211_RADIOTAP_MCS_HAVE_GI) {
    uint8_t gi = flags & IEEE80211_RADIOTAP_MCS_SGI;
    ss << "HAVE_GI[" << (gi == 0 ? "long" : "short") << "],";
  }
  if (known & IEEE80211_RADIOTAP_MCS_HAVE_FMT) {
    uint8_t fmt = flags & IEEE80211_RADIOTAP_MCS_FMT_GF;
    ss << "HAVE_FMT[" << (fmt == 0 ? "mixed" : "greenfield") << "],";
  }
  if (known & IEEE80211_RADIOTAP_MCS_HAVE_FEC) {
    uint8_t fec_type = flags & IEEE80211_RADIOTAP_MCS_FEC_LDPC;
    ss << "HAVE_FEC[" << (fec_type == 0 ? "BBC" : "LDPC") << "]";
  }
  if (known & IEEE80211_RADIOTAP_MCS_HAVE_STBC) {
    uint8_t stbc = flags << IEEE80211_RADIOTAP_MCS_STBC_SHIFT;
    ss << "HAVE_STBC[" << (int)stbc << "],";
  }
  ss << "]";
  return ss.str();
}

static std::string radiotap_header_to_string(const uint8_t *pkt, int pktlen) {
  struct ieee80211_radiotap_iterator iterator {};
  std::stringstream ss;
  int ret = ieee80211_radiotap_iterator_init(
      &iterator, (ieee80211_radiotap_header *)pkt, pktlen, NULL);
  if (ret) {
    ss << "ill-formed ieee80211_radiotap header " << ret;
    return ss.str();
  }
  ss << "Debuging Radiotap Header \n";
  while (ret == 0) {
    ret = ieee80211_radiotap_iterator_next(&iterator);
    if (iterator.is_radiotap_ns) {
      // ss<<"Is in namespace\n";
    }
    if (ret) {
      continue;
    }
    const int curr_arg_size = iterator.this_arg_size;
    /* see if this argument is something we can use */
    switch (iterator.this_arg_index) {
      case IEEE80211_RADIOTAP_TSFT:
        ss << "IEEE80211_RADIOTAP_TSFT:" << curr_arg_size << "\n";
        break;
      case IEEE80211_RADIOTAP_FLAGS:
        // ss<<"IEEE80211_RADIOTAP_FLAGS\n";
        ss << toStringRadiotapFlags(*iterator.this_arg) << "\n";
        break;
      case IEEE80211_RADIOTAP_RATE:
        ss << "IEEE80211_RADIOTAP_RATE:" << (int)(*iterator.this_arg) << "\n";
        break;
      case IEEE80211_RADIOTAP_DBM_ANTSIGNAL: {
        // This field	contains a single signed 8-bit value that indicates
        //	     the RF signal power at the	antenna, in decibels difference
        // from 	     1mW.
        int8_t value = *(int8_t *)iterator.this_arg;
        ss << "IEEE80211_RADIOTAP_DBM_ANTSIGNAL:" << (int)value
           << "dBm size:" << curr_arg_size << "\n";
      } break;
      case IEEE80211_RADIOTAP_ANTENNA:
        ss << "IEEE80211_RADIOTAP_ANTENNA:" << (int)(*iterator.this_arg)
           << "\n";
        break;
      case IEEE80211_RADIOTAP_CHANNEL:
        // ss<<"IEEE80211_RADIOTAP_CHANNEL\n";
        {
          auto *frequency = (uint16_t *)iterator.this_arg;
          auto *flags = (uint16_t *)&iterator.this_arg[2];
          ss << toStringRadiotapChannel(*frequency, *flags) << " \n";
        }
        break;
      case IEEE80211_RADIOTAP_MCS:
        // ss<<"IEEE80211_RADIOTAP_MCS\n";
        {
          uint8_t known = iterator.this_arg[0];
          uint8_t flags = iterator.this_arg[1];
          uint8_t mcs = iterator.this_arg[2];
          ss << toStringRadiotapMCS(known, flags, mcs) << "\n";
        }
        break;
      case IEEE80211_RADIOTAP_RX_FLAGS:
        // ss<<"IEEE80211_RADIOTAP_RX_FLAGS\n";
        ss << toStringRadiotapRXFlags(*iterator.this_arg) << "\n";
        break;
      case IEEE80211_RADIOTAP_TX_FLAGS:
        // ss<<"IEEE80211_RADIOTAP_TX_FLAGS\n";
        ss << toStringRadiotapTXFlags(*iterator.this_arg) << "\n";
        break;
      case IEEE80211_RADIOTAP_AMPDU_STATUS:
        ss << "EEE80211_RADIOTAP_AMPDU_STATUS\n";
        break;
      case IEEE80211_RADIOTAP_VHT:
        ss << "IEEE80211_RADIOTAP_VHT\n";
        break;
      case IEEE80211_RADIOTAP_TIMESTAMP:
        ss << "IEEE80211_RADIOTAP_TIMESTAMP\n";
        break;
      case IEEE80211_RADIOTAP_LOCK_QUALITY: {
        uint16_t value;
        std::memcpy(&value, iterator.this_arg, 1);
        ss << "IEEE80211_RADIOTAP_LOCK_QUALITY" << (int)value << "\n";
      } break;
      case IEEE80211_RADIOTAP_DBM_ANTNOISE: {
        int8_t value;
        std::memcpy(&value, iterator.this_arg, 1);
        ss << "IEEE80211_RADIOTAP_DBM_ANTNOISE:" << (int)value << "\n";
      }
      default:
        ss << "Unknown radiotap argument:" << (int)iterator.this_arg_index
           << "\n";
        break;
    }
  } /* while more rt headers */
  return ss.str();
}

}  // namespace radiotap::util

// what people used for whatever reason once on OpenHD / EZ-Wifibroadcast
namespace OldRadiotapHeaders {
// https://github.com/OpenHD/Open.HD/blob/2.0/wifibroadcast-base/tx_telemetry.c#L123
static uint8_t u8aRadiotapHeader[] = {
    0x00, 0x00,              // <-- radiotap version
    0x0c, 0x00,              // <- radiotap header length
    0x04, 0x80, 0x00, 0x00,  // <-- radiotap present flags
    0x00,                    // datarate (will be overwritten later)
    0x00, 0x00, 0x00};
static uint8_t u8aRadiotapHeader80211n[] = {
    0x00, 0x00,              // <-- radiotap version
    0x0d, 0x00,              // <- radiotap header length
    0x00, 0x80, 0x08, 0x00,  // <-- radiotap present flags (tx flags, mcs)
    0x08, 0x00,              // tx-flag
    0x37,                    // mcs have: bw, gi, stbc ,fec
    0x30,                    // mcs: 20MHz bw, long guard interval, stbc, ldpc
    0x00,  // mcs index 0 (speed level, will be overwritten later)
};

// this is what's used in
// https://github.com/OpenHD/Open.HD/blob/master/wifibroadcast-rc-Ath9k/rctx.cpp
static std::array<uint8_t, 13> radiotap_rc_ath9k = {
    0,  // <-- radiotap version      (0x00)
    0,  // <-- radiotap version      (0x00)

    13,  // <- radiotap header length (0x0d)
    0,   // <- radiotap header length (0x00)

    0,    // <-- radiotap present flags(0x00)
    128,  // <-- RADIOTAP_TX_FLAGS +   (0x80)
    8,    // <-- RADIOTAP_MCS          (0x08)
    0,    //                           (0x00)

    8,   // <-- RADIOTAP_F_TX_NOACK   (0x08)
    0,   //                           (0x00)
    55,  // <-- bitmap                (0x37)
    48,  // <-- flags                 (0x30)
    0,   // <-- mcs_index             (0x00)
};
}  // namespace OldRadiotapHeaders
#endif  // WIFIBROADCAST_RADIOTAP_UTIL_HPP
