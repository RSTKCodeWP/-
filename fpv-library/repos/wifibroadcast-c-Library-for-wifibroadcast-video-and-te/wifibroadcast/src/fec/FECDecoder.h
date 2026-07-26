#ifndef FEC_DECODER_HPP
#define FEC_DECODER_HPP

#include <cassert>
#include <cstdint>
#include <deque>
#include <functional>
#include <memory>

#include "FECConstants.hpp"
#include "RxBlock.h"
#include "TimeHelper.hpp"

// Takes a continuous stream of packets (data and fec correction packets) and
// processes them such that the output is exactly (or as close as possible) to
// the Input stream fed to FECEncoder. Most importantly, it also handles
// re-ordering of packets and packet duplicates due to multiple rx cards
class FECDecoder {
 public:
  /**
   * @param rx_queue_max_depth max size of rx queue - since in case of openhd,
   * one frame is either one or two FEC blocks we don't need that big of an rx
   * queue
   * @param maxNFragmentsPerBlock memory per block is pre-allocated, reduce this
   * value if you know the encoder doesn't ever exceed a given n of fragments
   * per block
   * @param enable_log_debug
   */
  explicit FECDecoder(
      const unsigned int rx_queue_max_depth,
      const unsigned int maxNFragmentsPerBlock = MAX_TOTAL_FRAGMENTS_PER_BLOCK,
      bool enable_log_debug = false, bool forward_gapped_fragments = true)
      : RX_QUEUE_MAX_SIZE(rx_queue_max_depth),
        maxNFragmentsPerBlock(maxNFragmentsPerBlock),
        m_enable_log_debug(enable_log_debug),
        m_forward_gapped_fragments(forward_gapped_fragments) {
    assert(rx_queue_max_depth < 20);
    assert(rx_queue_max_depth >= 1);
  }
  FECDecoder(const FECDecoder &other) = delete;
  ~FECDecoder() = default;
  // data forwarded on this callback is always in-order but possibly with gaps
  typedef std::function<void(const uint8_t *payload, std::size_t payloadSize)>
      SEND_DECODED_PACKET;
  // WARNING: Don't forget to register this callback !
  SEND_DECODED_PACKET mSendDecodedPayloadCallback;
  // Experimental
  typedef std::function<void(uint64_t block_idx, int n_fragments_total,
                             int n_fragments_forwarded)>
      ON_BLOCK_DONE_CB;
  ON_BLOCK_DONE_CB m_block_done_cb = nullptr;
  // A value too high doesn't really give much benefit and increases memory
  // usage
  const unsigned int RX_QUEUE_MAX_SIZE;
  const unsigned int maxNFragmentsPerBlock;
  const bool m_enable_log_debug;
  const bool m_forward_gapped_fragments;
  AvgCalculator m_fec_decode_time{};

 public:
  static bool validate_packet_size(int data_len);
  // process a valid packet
  bool process_valid_packet(const uint8_t *data, int data_len);

 private:
  // since we also need to search this data structure, a std::queue is not
  // enough. since we have an upper limit on the size of this dequeue, it is
  // basically a searchable ring buffer
  std::deque<std::unique_ptr<RxBlock>> rx_queue;
  uint64_t last_known_block = ((uint64_t)-1);  // id of last known block
  /**
   * For this Block,
   * starting at the primary fragment we stopped on last time,
   * forward as many primary fragments as they are available until there is a
   * gap
   * @param discardMissingPackets : if true, gaps are ignored and fragments are
   * forwarded even though this means the missing ones are irreversible lost Be
   * carefully with this param, use it only before you need to get rid of a
   * block
   */
  void forwardMissingPrimaryFragmentsIfAvailable(
      RxBlock &block, const bool discardMissingPackets = false);
  // also increase lost block count if block is not fully recovered
  void rxQueuePopFront();
  // create a new RxBlock for the specified block_idx and push it into the queue
  // NOTE: Checks first if this operation would increase the size of the queue
  // over its max capacity In this case, the only solution is to remove the
  // oldest block before adding the new one
  void rxRingCreateNewSafe(const uint64_t blockIdx);

  // If block is already known and not in the queue anymore return nullptr
  // else if block is inside the ring return pointer to it
  // and if it is not inside the ring add as many blocks as needed, then return
  // pointer to it
  RxBlock *rxRingFindCreateBlockByIdx(const uint64_t blockIdx);
  void process_with_rx_queue(const FECPayloadHdr &header, const uint8_t *data,
                             int data_size);

 public:
  // matches FECDecoder
  struct FECRxStats {
    // total block count
    uint64_t count_blocks_total = 0;
    // a block counts as "lost" if it was removed before being fully received or
    // recovered
    uint64_t count_blocks_lost = 0;
    // a block counts as "recovered" if it was recovered using FEC packets
    uint64_t count_blocks_recovered = 0;
    // n of primary fragments that were reconstructed during the recovery
    // process of a block
    uint64_t count_fragments_recovered = 0;
    // n of forwarded bytes
    uint64_t count_bytes_forwarded = 0;
    MinMaxAvg<std::chrono::nanoseconds> curr_fec_decode_time{};
  };
  FECRxStats stats{};
  void reset_rx_queue();
};

#endif  // FEC_DECODER_HPP
