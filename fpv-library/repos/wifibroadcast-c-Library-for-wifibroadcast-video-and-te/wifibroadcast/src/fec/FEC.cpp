//
// Created by consti10 on 30.06.23.
//

#include "FEC.h"

#include <spdlog/spdlog.h>

#include <cmath>

#include "../wifibroadcast_spdlog.h"
#include "RxBlock.h"

uint32_t calculate_n_secondary_fragments(uint32_t n_primary_fragments,
                                         uint32_t fec_overhead_perc) {
  if (fec_overhead_perc <= 0) return 0;
  const float n_secondary = static_cast<float>(n_primary_fragments) *
                            static_cast<float>(fec_overhead_perc) / 100.0f;
  if (n_secondary <= 1.0) {
    // Always calculate at least one FEC packet
    return 1;
  }
  return std::lroundf(n_secondary);
}

unsigned int calculateN(const unsigned int k, const unsigned int percentage) {
  return k + calculate_n_secondary_fragments(k, percentage);
}

void fec_stream_print_fec_optimization_method() { print_optimization_method(); }
