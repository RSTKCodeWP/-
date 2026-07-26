#include "RxBlock.h"

#include "FEC.h"

RxBlock::RxBlock(const unsigned int maxNFragmentsPerBlock,
                 const uint64_t blockIdx1)
    : blockIdx(blockIdx1),
      fragment_map(
          maxNFragmentsPerBlock,
          FRAGMENT_STATUS_UNAVAILABLE),  // after creation of the RxBlock every
                                         // f. is marked as unavailable
      blockBuffer(maxNFragmentsPerBlock) {
  assert(fragment_map.size() == blockBuffer.size());
}

bool RxBlock::hasFragment(const int fragment_idx) {
  assert(fragment_idx < fragment_map.size());
  return fragment_map[fragment_idx] == FRAGMENT_STATUS_AVAILABLE;
}

bool RxBlock::allPrimaryFragmentsHaveBeenForwarded() const {
  if (m_n_primary_fragments_in_block == -1) return false;
  return nAlreadyForwardedPrimaryFragments == m_n_primary_fragments_in_block;
}

bool RxBlock::allPrimaryFragmentsCanBeRecovered() const {
  // return false if k is not known for this block yet (which means we didn't
  // get a secondary fragment yet, since each secondary fragment contains k)
  if (m_n_primary_fragments_in_block == -1) return false;
  // ready for FEC step if we have as many secondary fragments as we are missing
  // on primary fragments
  if (m_n_available_primary_fragments + m_n_available_secondary_fragments >=
      m_n_primary_fragments_in_block)
    return true;
  return false;
}

bool RxBlock::allPrimaryFragmentsAreAvailable() const {
  if (m_n_primary_fragments_in_block == -1) return false;
  return m_n_available_primary_fragments == m_n_primary_fragments_in_block;
}

void RxBlock::addFragment(const uint8_t* data, const std::size_t dataLen) {
  auto* hdr_p = (FECPayloadHdr*)data;
  FECPayloadHdr& header = *hdr_p;
  assert(!hasFragment(header.fragment_idx));
  assert(header.block_idx == blockIdx);
  assert(fragment_map[header.fragment_idx] == FRAGMENT_STATUS_UNAVAILABLE);
  assert(header.fragment_idx < blockBuffer.size());
  fragment_copy_payload(header.fragment_idx, data, dataLen);
  // mark it as available
  fragment_map[header.fragment_idx] = FRAGMENT_STATUS_AVAILABLE;

  // each fragment inside a block should report the same n of primary fragments
  if (m_n_primary_fragments_in_block == -1) {
    m_n_primary_fragments_in_block = header.n_primary_fragments;
  } else {
    assert(m_n_primary_fragments_in_block == header.n_primary_fragments);
  }
  const bool is_primary_fragment =
      header.fragment_idx < header.n_primary_fragments;
  if (is_primary_fragment) {
    m_n_available_primary_fragments++;
  } else {
    m_n_available_secondary_fragments++;
    const auto payload_len_including_size =
        dataLen - sizeof(FECPayloadHdr) + sizeof(uint16_t);
    // all secondary fragments shall have the same size
    if (m_size_of_secondary_fragments == -1) {
      m_size_of_secondary_fragments = payload_len_including_size;
    } else {
      assert(m_size_of_secondary_fragments == payload_len_including_size);
    }
  }
  if (firstFragmentTimePoint == std::nullopt) {
    firstFragmentTimePoint = std::chrono::steady_clock::now();
  }
}

void RxBlock::fragment_copy_payload(const int fragment_idx, const uint8_t* data,
                                    const std::size_t dataLen) {
  uint8_t* buff = blockBuffer[fragment_idx].data();
  // NOTE: FECPayloadHdr::data_size needs to be included during the fec decode
  // step
  const uint8_t* payload_p = data + sizeof(FECPayloadHdr) - sizeof(uint16_t);
  auto payload_s = dataLen - sizeof(FECPayloadHdr) + sizeof(uint16_t);
  // write the data (doesn't matter if FEC data or correction packet)
  memcpy(buff, payload_p, payload_s);
  // set the rest to zero such that FEC works
  memset(buff + payload_s, 0, MAX_PAYLOAD_BEFORE_FEC - payload_s);
}

std::vector<uint16_t> RxBlock::pullAvailablePrimaryFragments(
    const bool discardMissingPackets) {
  // note: when pulling the available fragments, we do not need to know how many
  // primary fragments this block actually contains
  std::vector<uint16_t> ret;
  for (int i = nAlreadyForwardedPrimaryFragments;
       i < m_n_available_primary_fragments; i++) {
    if (fragment_map[i] == FRAGMENT_STATUS_UNAVAILABLE) {
      if (discardMissingPackets) {
        continue;
      } else {
        break;
      }
    }
    ret.push_back(i);
  }
  // make sure these indices won't be returned again
  nAlreadyForwardedPrimaryFragments += (int)ret.size();
  return ret;
}

const uint8_t* RxBlock::get_primary_fragment_data_p(const int fragment_index) {
  assert(fragment_map[fragment_index] == FRAGMENT_STATUS_AVAILABLE);
  assert(m_n_primary_fragments_in_block != -1);
  assert(fragment_index < m_n_primary_fragments_in_block);
  // return blockBuffer[fragment_index].data()+sizeof(FECPayloadHdr);
  return blockBuffer[fragment_index].data() + sizeof(uint16_t);
}

const int RxBlock::get_primary_fragment_data_size(const int fragment_index) {
  assert(fragment_map[fragment_index] == FRAGMENT_STATUS_AVAILABLE);
  assert(m_n_primary_fragments_in_block != -1);
  assert(fragment_index < m_n_primary_fragments_in_block);
  uint16_t* len_p = (uint16_t*)blockBuffer[fragment_index].data();
  return *len_p;
}

int RxBlock::reconstructAllMissingData() {
  // wifibroadcast::log::get_default()->debug("reconstructAllMissingData"<<nAvailablePrimaryFragments<<"
  // "<<nAvailableSecondaryFragments<<" "<<fec.FEC_K<<"\n";
  //  NOTE: FEC does only work if nPrimaryFragments+nSecondaryFragments>=FEC_K
  assert(m_n_primary_fragments_in_block != -1);
  assert(m_size_of_secondary_fragments != -1);
  // do not reconstruct if reconstruction is impossible
  assert(getNAvailableFragments() >= m_n_primary_fragments_in_block);
  // also do not reconstruct if reconstruction is not needed
  // const int nMissingPrimaryFragments = m_n_primary_fragments_in_block-
  // m_n_available_primary_fragments;
  auto recoveredFragmentIndices =
      fecDecode(m_size_of_secondary_fragments, blockBuffer,
                m_n_primary_fragments_in_block, fragment_map);
  // now mark them as available
  for (const auto idx : recoveredFragmentIndices) {
    fragment_map[idx] = FRAGMENT_STATUS_AVAILABLE;
  }
  m_n_available_primary_fragments += recoveredFragmentIndices.size();
  // n of reconstructed packets
  return recoveredFragmentIndices.size();
}

std::optional<int> RxBlock::get_missing_primary_packets() const {
  if (m_n_primary_fragments_in_block <= 0) return std::nullopt;
  return m_n_primary_fragments_in_block - getNAvailableFragments();
}

std::string RxBlock::get_missing_primary_packets_readable() const {
  const auto tmp = get_missing_primary_packets();
  if (tmp == std::nullopt) return "?";
  return std::to_string(tmp.value());
}

int RxBlock::get_n_primary_fragments() const {
  return m_n_primary_fragments_in_block;
}
int RxBlock::get_n_forwarded_primary_fragments() const {
  return nAlreadyForwardedPrimaryFragments;
}
