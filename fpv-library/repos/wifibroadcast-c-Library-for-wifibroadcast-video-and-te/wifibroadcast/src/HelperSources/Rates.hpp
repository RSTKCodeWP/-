//
// Created by consti10 on 25.07.23.
//

#ifndef WIFIBROADCAST_RATES_H
#define WIFIBROADCAST_RATES_H

#include <vector>

namespace wifibroadcast {

// Theoretical rate(s)
struct Rate {
  int rate_20mhz_kbits;
  int rate_40mhz_kbits;
};

// From https://mcsindex.com/
static std::vector<Rate> theoretical_rates_5G() {
  return {
      Rate{6500, 13500},    // mcs0 (VHT0)
      Rate{13000, 27000},   // mcs1 (VHT1)
      Rate{19500, 40500},   // mcs2
      Rate{26000, 54000},   // mcs3
      Rate{39000, 81000},   // mcs4
      Rate{52000, 108000},  // mcs5
      Rate{58500, 121500},  // mcs6
      Rate{65000, 135000},  // mcs7
      Rate{13000, 27000},   // mcs8  (VHT0 + SS2)
      Rate{26000, 54000},   // mcs9  (VHT1 + SS2)
      Rate{39000, 81000},   // mcs10 (VHT2 + SS2)
      Rate{52000, 108000},  // mcs11 (VHT3 + SS2)
  };
}
static Rate get_theoretical_rate_5G(int mcs) {
  const auto rates = theoretical_rates_5G();
  if (mcs < 0) return {-1, 1};
  if (mcs < rates.size()) {
    return rates[mcs];
  }
  return rates[rates.size() - 1];
}

// Those values come from running the "increase bitrate until tx errors" test 3
// times and taking the lowest (sensible) value of those runs STBC on, LDPC on,
// GUARD LONG ASUS STICK & x86 i7 laptop
static std::vector<Rate> openhd_rtl8812au_5G_practical_rates() {
  return {
      Rate{6100, 11700},   // MCS 0
      Rate{11000, 20600},  // MCS 1
      Rate{16000, 28400},  // MCS 2
      Rate{20000, 33400},  // MCS 3
      Rate{26000, 36900},  // MCS 4
      Rate{28000, 43500},  // MCS 5
      Rate{33000, 48000},  // MCS 6
      Rate{38000, 53000},  // MCS 7
      Rate{11700, 16700},  // MCS 8  (VHT0 + SS2)
      Rate{20000, 30000},  // MCS 9  (VHT1 + SS2)
      Rate{25000, 37000},  // MCS 10 (VHT2 + SS2)
      Rate{30000, 51000},  // MCS 11 (VHT3 + SS2)
  };
}

static Rate get_practical_rate_5G(int mcs) {
  const auto rates = openhd_rtl8812au_5G_practical_rates();
  if (mcs < 0) return {-1, 1};
  if (mcs < rates.size()) {
    return rates[mcs];
  }
  return rates[rates.size() - 1];
}

}  // namespace wifibroadcast

#endif  // WIFIBROADCAST_RATES_H
