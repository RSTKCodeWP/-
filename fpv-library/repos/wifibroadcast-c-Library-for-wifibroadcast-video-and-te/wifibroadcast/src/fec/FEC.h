//
// Created by consti10 on 19.03.21.
//

#ifndef WIFIBROADCAST_FEC_H
#define WIFIBROADCAST_FEC_H

#include <array>
#include <iostream>
#include <vector>

#include "../../lib/fec/fec_base.h"
#include "FECConstants.hpp"
#include "Helper.hpp"

// c++ wrapper around fec library
// NOTE: When working with FEC, people seem to use the terms block, fragments
// and more in different context(s). To avoid confusion,I decided to use the
// following notation: A block is formed by K primary and N-K secondary
// fragments. Each of these fragments must have the same size. Therefore,
// fragmentSize is the size of each fragment in this block (for some reason,
// this is called blockSize in the underlying c fec implementation). A primary
// fragment is a data packet A secondary fragment is a data correction (FEC)
// packet Note: for the fec_decode() step, it doesn't matter how many secondary
// fragments were created during the fec_encode() step - only thing that matters
// is how many secondary fragments you received (either enough for fec_decode()
// or not enough for fec_decode() ) Also note: you obviously cannot use the same
// secondary fragment more than once

// Note: By using "blockBuffer" as input the fecEncode / fecDecode function(s)
// don't need to allocate any new memory.
//  Also note, indices in blockBuffer can refer to either primary or secondary
//  fragments. Whereas when calling fec_decode(), secondary fragment numbers
//  start from 0, not from nPrimaryFragments. These declarations are written
//  such that you can do "variable block size" on tx and rx.

/**
 * @param fragmentSize size of each fragment to use for the FEC encoding step.
 * FEC only works on packets the same size
 * @param blockBuffer (big) data buffer. The nth element is to be treated as the
 * nth fragment of the block, either as primary or secondary fragment. During
 * the FEC step, @param nPrimaryFragments fragments are used to calculate
 * nSecondaryFragments FEC blocks. After the FEC step,beginning at position
 * @param nPrimaryFragments ,@param nSecondaryFragments are stored at the
 * following positions, each of size @param fragmentSize
 */
template <std::size_t S>
void fecEncode(unsigned int fragmentSize,
               std::vector<std::array<uint8_t, S>> &blockBuffer,
               unsigned int nPrimaryFragments,
               unsigned int nSecondaryFragments) {
  assert(fragmentSize <= S);
  assert(nPrimaryFragments + nSecondaryFragments <= blockBuffer.size());
  auto primaryFragmentsP =
      GenericHelper::convertToP_const(blockBuffer, 0, nPrimaryFragments);
  auto secondaryFragmentsP = GenericHelper::convertToP(
      blockBuffer, nPrimaryFragments, blockBuffer.size() - nPrimaryFragments);
  secondaryFragmentsP.resize(nSecondaryFragments);
  // const auto before=std::chrono::steady_clock::now();
  fec_encode2(fragmentSize, primaryFragmentsP, secondaryFragmentsP);
  // const auto delta=std::chrono::steady_clock::now()-before;
  // std::cout<<"fec_encode step
  // took:"<<std::chrono::duration_cast<std::chrono::microseconds>(delta).count()<<"us\n";
}

/**
 * @param fragmentSize size of each fragment
 * @param blockBuffer blockBuffer (big) data buffer. The nth element is to be
 * treated as the nth fragment of the block, either as primary or secondary
 * fragment.
 * @param nPrimaryFragments n of primary fragments used during encode step
 * @param fragmentStatusList information which (primary or secondary fragments)
 * were received. values from [0,nPrimaryFragments[ are treated as primary
 * fragments, values from [nPrimaryFragments,size[ are treated as secondary
 * fragments.
 * @return indices of reconstructed primary fragments
 */
template <std::size_t S>
std::vector<unsigned int> fecDecode(
    unsigned int fragmentSize, std::vector<std::array<uint8_t, S>> &blockBuffer,
    const unsigned int nPrimaryFragments,
    const std::vector<bool> &fragmentStatusList) {
  assert(fragmentSize <= S);
  assert(fragmentStatusList.size() <= blockBuffer.size());
  assert(fragmentStatusList.size() == blockBuffer.size());
  std::vector<unsigned int> indicesMissingPrimaryFragments;
  std::vector<uint8_t *> primaryFragmentP(nPrimaryFragments);
  for (unsigned int idx = 0; idx < nPrimaryFragments; idx++) {
    if (fragmentStatusList[idx] == FRAGMENT_STATUS_UNAVAILABLE) {
      indicesMissingPrimaryFragments.push_back(idx);
    }
    primaryFragmentP[idx] = blockBuffer[idx].data();
  }
  // find enough secondary fragments
  std::vector<uint8_t *> secondaryFragmentP;
  std::vector<unsigned int> secondaryFragmentIndices;
  for (int i = 0; i < fragmentStatusList.size() - nPrimaryFragments; i++) {
    const auto idx = nPrimaryFragments + i;
    if (fragmentStatusList[idx] == FRAGMENT_STATUS_AVAILABLE) {
      secondaryFragmentP.push_back(blockBuffer[idx].data());
      secondaryFragmentIndices.push_back(i);
    }
  }
  // make sure we got enough secondary fragments
  assert(secondaryFragmentP.size() >= indicesMissingPrimaryFragments.size());
  // assert if fecDecode is called too late (e.g. more secondary fragments than
  // needed for fec
  assert(indicesMissingPrimaryFragments.size() == secondaryFragmentP.size());
  // do fec step
  fec_decode2(fragmentSize, primaryFragmentP, indicesMissingPrimaryFragments,
              secondaryFragmentP, secondaryFragmentIndices);
  return indicesMissingPrimaryFragments;
}

/**
 * For dynamic block sizes, we switched to a FEC overhead "percentage" value.
 * e.g. the final data throughput ~= original data throughput * fec overhead
 * percentage Rounds up / down (.5), but always at least 1
 */
uint32_t calculate_n_secondary_fragments(uint32_t n_primary_fragments,
                                         uint32_t fec_overhead_perc);

/**
 * calculate n from k and percentage as used in FEC terms
 * (k: number of primary fragments, n: primary + secondary fragments)
 */
uint32_t calculateN(uint32_t k, uint32_t percentage);

void fec_stream_print_fec_optimization_method();

// quick math regarding sequence numbers:
// uint32_t holds max 4294967295 . At 10 000 pps (packets per seconds) (which is
// already completely out of reach) this allows the tx to run for 429496.7295
// seconds
// 429496.7295 / 60 / 60 = 119.304647083 hours which is also completely overkill
// for OpenHD (and after this time span, a "reset" of the sequence number
// happens anyways) unsigned 24 bits holds 16777215 . At 1000 blocks per second
// this allows the tx to create blocks for 16777.215 seconds or 4.6 hours. That
// should cover a flight (and after 4.6h a reset happens, which means you might
// lose a couple of blocks once every 4.6 h ) and 8 bits holds max 255.

#endif  // WIFIBROADCAST_FEC_H
