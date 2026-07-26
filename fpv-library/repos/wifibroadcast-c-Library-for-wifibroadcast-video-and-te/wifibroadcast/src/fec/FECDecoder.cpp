#include "FECDecoder.h"

#include <sys/time.h>

#include "../wifibroadcast_spdlog.h"

bool FECDecoder::validate_packet_size(const int data_len) {
  if (data_len < sizeof(FECPayloadHdr)) {
    // packet is too small
    return false;
  }
  if (data_len > MAX_PAYLOAD_BEFORE_FEC) {
    // packet is too big
    return false;
  }
  return true;
}

bool FECDecoder::process_valid_packet(const uint8_t* data, int data_len) {
  assert(validate_packet_size(data_len));
  // reconstruct the data layout
  const FECPayloadHdr* header_p = (FECPayloadHdr*)data;
  /* const uint8_t* payload_p=data+sizeof(FECPayloadHdr);
   const int payload_size=data_len-sizeof(FECPayloadHdr);*/
  if (header_p->fragment_idx >= maxNFragmentsPerBlock) {
    wifibroadcast::log::get_default()->warn("invalid fragment_idx: {}",
                                            header_p->fragment_idx);
    return false;
  }
  process_with_rx_queue(*header_p, data, data_len);
  return true;
}

void FECDecoder::forwardMissingPrimaryFragmentsIfAvailable(
    RxBlock& block, const bool discardMissingPackets) {
  assert(mSendDecodedPayloadCallback);
  // TODO remove me
  if (discardMissingPackets) {
    if (m_enable_log_debug) {
      wifibroadcast::log::get_default()->warn(
          "Forwarding block that is not yet fully finished: {} total: {} "
          "available: {} missing: {}",
          block.getBlockIdx(), block.get_n_primary_fragments(),
          block.getNAvailableFragments(),
          block.get_missing_primary_packets_readable());
    }
  }
  const auto indices =
      block.pullAvailablePrimaryFragments(discardMissingPackets);
  for (auto primaryFragmentIndex : indices) {
    const uint8_t* data =
        block.get_primary_fragment_data_p(primaryFragmentIndex);
    const int data_size =
        block.get_primary_fragment_data_size(primaryFragmentIndex);
    if (data_size > FEC_PACKET_MAX_PAYLOAD_SIZE || data_size <= 0) {
      wifibroadcast::log::get_default()->warn(
          "corrupted packet on FECDecoder out ({}:{}) : {}B",
          block.getBlockIdx(), primaryFragmentIndex, data_size);
    } else {
      mSendDecodedPayloadCallback(data, data_size);
      stats.count_bytes_forwarded += data_size;
    }
  }
}

void FECDecoder::rxQueuePopFront() {
  assert(rx_queue.front() != nullptr);
  if (!rx_queue.front()->allPrimaryFragmentsHaveBeenForwarded()) {
    stats.count_blocks_lost++;
    if (m_enable_log_debug) {
      auto& block = *rx_queue.front();
      wifibroadcast::log::get_default()->debug(
          "Removing block {} {}", block.getBlockIdx(),
          block.get_missing_primary_packets_readable());
    }
  }
  if (m_block_done_cb) {
    auto& block = *rx_queue.front();
    const int n_p_fragments = block.get_n_primary_fragments();
    const int n_p_fragments_forwarded =
        block.get_n_forwarded_primary_fragments();
    m_block_done_cb(block.getBlockIdx(), n_p_fragments,
                    n_p_fragments_forwarded);
  }
  rx_queue.pop_front();
}

void FECDecoder::rxRingCreateNewSafe(const uint64_t blockIdx) {
  // check: make sure to always put blocks into the queue in order !
  if (!rx_queue.empty()) {
    // the newest block in the queue should be equal to block_idx -1
    // but it must not ?!
    if (rx_queue.back()->getBlockIdx() != (blockIdx - 1)) {
      // If we land here, one or more full blocks are missing, which can happen
      // on bad rx links
      // wifibroadcast::log::get_default()->debug("In queue: {} But new:
      // {}",rx_queue.back()->getBlockIdx(),blockIdx);
    }
    // assert(rx_queue.back()->getBlockIdx() == (blockIdx - 1));
  }
  // we can return early if this operation doesn't exceed the size limit
  if (rx_queue.size() < RX_QUEUE_MAX_SIZE) {
    rx_queue.push_back(
        std::make_unique<RxBlock>(maxNFragmentsPerBlock, blockIdx));
    stats.count_blocks_total++;
    return;
  }
  // Ring overflow. This means that there are more unfinished blocks than ring
  // size Possible solutions:
  // 1. Increase ring size. Do this if you have large variance of packet travel
  // time throught WiFi card or network stack.
  //    Some cards can do this due to packet reordering inside, diffent chipset
  //    and/or firmware or your RX hosts have different CPU power.
  // 2. Reduce packet injection speed or try to unify RX hardware.

  // forward remaining data for the (oldest) block, since we need to get rid of
  // it
  auto& oldestBlock = rx_queue.front();
  forwardMissingPrimaryFragmentsIfAvailable(*oldestBlock, true);
  // and remove the block once done with it
  rxQueuePopFront();

  // now we are guaranteed to have space for one new block
  rx_queue.push_back(
      std::make_unique<RxBlock>(maxNFragmentsPerBlock, blockIdx));
  stats.count_blocks_total++;
}

RxBlock* FECDecoder::rxRingFindCreateBlockByIdx(const uint64_t blockIdx) {
  // check if block is already in the ring
  auto found = std::find_if(rx_queue.begin(), rx_queue.end(),
                            [&blockIdx](const std::unique_ptr<RxBlock>& block) {
                              return block->getBlockIdx() == blockIdx;
                            });
  if (found != rx_queue.end()) {
    return found->get();
  }
  // check if block is already known and not in the ring then it is already
  // processed
  if (last_known_block != (uint64_t)-1 && blockIdx <= last_known_block) {
    return nullptr;
  }

  // don't forget to increase the lost blocks counter if we do not add blocks
  // here due to no space in the rx queue (can happen easily if the rx queue has
  // a size of 1)
  const auto n_needed_new_blocks =
      last_known_block != (uint64_t)-1 ? blockIdx - last_known_block : 1;
  if (n_needed_new_blocks > RX_QUEUE_MAX_SIZE) {
    if (m_enable_log_debug) {
      wifibroadcast::log::get_default()->debug(
          "Need {} blocks, exceeds {}", n_needed_new_blocks, RX_QUEUE_MAX_SIZE);
    }
    stats.count_blocks_lost += n_needed_new_blocks - RX_QUEUE_MAX_SIZE;
  }
  // add as many blocks as we need ( the rx ring mustn't have any gaps between
  // the block indices). but there is no point in adding more blocks than
  // RX_RING_SIZE
  const int new_blocks = (int)std::min(n_needed_new_blocks,
                                       (uint64_t)FECDecoder::RX_QUEUE_MAX_SIZE);
  last_known_block = blockIdx;

  for (int i = 0; i < new_blocks; i++) {
    rxRingCreateNewSafe(blockIdx + i + 1 - new_blocks);
  }
  // the new block we've added is now the most recently added element (and since
  // we always push to the back, the "back()" element)
  assert(rx_queue.back()->getBlockIdx() == blockIdx);
  return rx_queue.back().get();
}

void FECDecoder::process_with_rx_queue(const FECPayloadHdr& header,
                                       const uint8_t* data, int data_size) {
  auto blockP = rxRingFindCreateBlockByIdx(header.block_idx);
  // ignore already processed blocks
  if (blockP == nullptr) return;
  // cannot be nullptr
  RxBlock& block = *blockP;
  // ignore already processed fragments
  if (block.hasFragment(header.fragment_idx)) {
    return;
  }
  block.addFragment(data, data_size);
  if (block == *rx_queue.front()) {
    // wifibroadcast::log::get_default()->debug("In front\n";
    //  we are in the front of the queue (e.g. at the oldest block)
    //  forward packets until the first gap
    forwardMissingPrimaryFragmentsIfAvailable(block);
    // We are done with this block if either all fragments have been forwarded
    // or it can be recovered
    if (block.allPrimaryFragmentsHaveBeenForwarded()) {
      // remove block when done with it
      rxQueuePopFront();
      return;
    }
    if (block.allPrimaryFragmentsCanBeRecovered()) {
      // apply fec for this block
      const auto before_encode = std::chrono::steady_clock::now();
      stats.count_fragments_recovered += block.reconstructAllMissingData();
      stats.count_blocks_recovered++;
      m_fec_decode_time.add(std::chrono::steady_clock::now() - before_encode);
      if (m_fec_decode_time.get_delta_since_last_reset() >
          std::chrono::seconds(1)) {
        // wifibroadcast::log::get_default()->debug("FEC decode took
        // {}",m_fec_decode_time.getAvgReadable());
        stats.curr_fec_decode_time = m_fec_decode_time.getMinMaxAvg();
        m_fec_decode_time.reset();
      }
      forwardMissingPrimaryFragmentsIfAvailable(block);
      assert(block.allPrimaryFragmentsHaveBeenForwarded());
      // remove block when done with it
      rxQueuePopFront();
      return;
    }
    return;
  } else {
    // wifibroadcast::log::get_default()->debug("Not in front\n";
    //  we are not in the front of the queue but somewhere else
    //  If this block can be fully recovered or all primary fragments are
    //  available this triggers a flush
    if (block.allPrimaryFragmentsAreAvailable() ||
        block.allPrimaryFragmentsCanBeRecovered()) {
      // send all queued packets in all unfinished blocks before and remove them
      if (m_enable_log_debug) {
        wifibroadcast::log::get_default()->debug("Block {} triggered a flush",
                                                 block.getBlockIdx());
      }
      while (block != *rx_queue.front()) {
        forwardMissingPrimaryFragmentsIfAvailable(*rx_queue.front(),
                                                  m_forward_gapped_fragments);
        rxQueuePopFront();
      }
      // then process the block who is fully recoverable or has no gaps in the
      // primary fragments
      if (block.allPrimaryFragmentsAreAvailable()) {
        forwardMissingPrimaryFragmentsIfAvailable(block);
        assert(block.allPrimaryFragmentsHaveBeenForwarded());
      } else {
        // apply fec for this block
        stats.count_fragments_recovered += block.reconstructAllMissingData();
        stats.count_blocks_recovered++;
        forwardMissingPrimaryFragmentsIfAvailable(block);
        assert(block.allPrimaryFragmentsHaveBeenForwarded());
      }
      // remove block
      rxQueuePopFront();
    }
  }
}

void FECDecoder::reset_rx_queue() {
  /*while (auto el=rx_queue.front() != nullptr){
    rxQueuePopFront();
  }*/
  rx_queue.resize(0);
  last_known_block = ((uint64_t)-1);
}