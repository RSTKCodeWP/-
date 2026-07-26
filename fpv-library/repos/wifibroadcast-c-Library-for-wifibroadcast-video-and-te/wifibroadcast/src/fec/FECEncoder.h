#ifndef FEC_ENCODER_HPP
#define FEC_ENCODER_HPP

#include <functional>
#include <memory>

#include "FECConstants.hpp"
#include "TimeHelper.hpp"

class FECEncoder {
 public:
  typedef std::function<void(const uint8_t* packet, int packet_len)>
      OUTPUT_DATA_CALLBACK;
  explicit FECEncoder();
  FECEncoder(const FECEncoder& other) = delete;

 public:
  /**
   * Encodes a new block and forwards the packets for this block
   * forwards data packets first, then generated fec packets
   * (if needed) and forwards them after.
   * @param data_packets the packets for this block
   * @param n_secondary_fragments how many secondary fragments (FEC packets)
   * should be created
   */
  void encode_block(
      const std::vector<std::shared_ptr<std::vector<uint8_t>>>& data_packets,
      int n_secondary_fragments);
  /**
   * Distributes data evenly into @param n_primary_fragments and calculates
   * @param n_secondary_fragments afterwards. Reduces latency to a minimum by
   * forwarding packets via the cb as soon as possible (primary fragments are
   * forwarded before the fec step is performed).
   */
  void fragment_and_encode(const uint8_t* data, int data_len,
                           int n_primary_fragments, int n_secondary_fragments);
  OUTPUT_DATA_CALLBACK m_out_cb = nullptr;
  AvgCalculator m_fec_block_encode_time;
  MinMaxAvg<std::chrono::nanoseconds> m_curr_fec_block_encode_time{};
  BaseAvgCalculator<uint16_t> m_block_sizes{};
  MinMaxAvg<uint16_t> m_curr_fec_block_sizes{};

 private:
  // Creates the (next) primary fragment
  // forward it via the data cb (such that it can be sent out as soon as
  // possible) and store the fragment for later use (fec_encode)
  void create_forward_save_fragment(const uint8_t* data, int data_len);
  // performs fec_encode (on the previously saved data) then forward all the fec
  // packets one after another.
  void create_fec_packets(int n_secondary_fragments);
  void init_block(int n_primary_fragments);
  // Pre-allocated to have space for storing primary fragments (they are needed
  // once the fec step needs to be performed) and creating the wanted amount of
  // secondary packets
  std::array<std::array<uint8_t, MAX_PAYLOAD_BEFORE_FEC>,
             MAX_TOTAL_FRAGMENTS_PER_BLOCK>
      m_block_buffer{};
  // Increased each time a block has been finished
  uint32_t m_curr_block_idx = 0;
  static_assert(sizeof(m_curr_block_idx) == sizeof(FECPayloadHdr::block_idx));
  FECPayloadHdr m_fec_payload_hdr;
  int m_max_packet_size = -1;
  int m_fragment_index = 0;
  std::vector<const uint8_t*> m_primary_fragments_data_p;
};

#endif  // FEC_ENCODER_HPP