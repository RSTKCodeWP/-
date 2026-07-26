#ifndef RX_BLOCK_HPP
#define RX_BLOCK_HPP

#include <array>
#include <chrono>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "FECConstants.hpp"

// This encapsulates everything you need when working on a single FEC block on
// the receiver for example, addFragment() or pullAvailablePrimaryFragments() it
// also provides convenient methods to query if the block is fully forwarded or
// if it is ready for the FEC reconstruction step.
class RxBlock {
 public:
  // @param maxNFragmentsPerBlock max number of primary and secondary fragments
  // for this block. you could just use MAX_TOTAL_FRAGMENTS_PER_BLOCK for that,
  // but if your tx then uses (4:8) for example, you'd allocate much more memory
  // every time for a new RX block than needed.
  explicit RxBlock(unsigned int maxNFragmentsPerBlock, uint64_t blockIdx1);
  // No copy constructor for safety
  RxBlock(const RxBlock &) = delete;
  // two blocks are the same if they refer to the same block idx:
  constexpr bool operator==(const RxBlock &other) const {
    return blockIdx == other.blockIdx;
  }
  // same for not equal operator
  constexpr bool operator!=(const RxBlock &other) const {
    return !(*this == other);
  }
  ~RxBlock() = default;

 public:
  // returns true if this fragment has been already received
  bool hasFragment(int fragment_idx);
  // returns true if we are "done with this block" aka all data has been already
  // forwarded
  bool allPrimaryFragmentsHaveBeenForwarded() const;
  // returns true if enough FEC secondary fragments are available to replace all
  // missing primary fragments
  bool allPrimaryFragmentsCanBeRecovered() const;
  // returns true as soon as all primary fragments are available
  bool allPrimaryFragmentsAreAvailable() const;
  // copy the fragment data and mark it as available
  // you should check if it is already available with hasFragment() to avoid
  // copying the same fragment multiple times when using multiple RX cards
  void addFragment(const uint8_t *data, const std::size_t dataLen);
  // util to copy the packet size and payload (and not more)
  void fragment_copy_payload(const int fragment_idx, const uint8_t *data,
                             const std::size_t dataLen);
  /**
   * @returns the indices for all primary fragments that have not yet been
   * forwarded and are available (already received or reconstructed). Once an
   * index is returned here, it won't be returned again (Therefore, as long as
   * you immediately forward all primary fragments returned here,everything
   * happens in order)
   * @param discardMissingPackets : if true, gaps are ignored and fragments are
   * forwarded even though this means the missing ones are irreversible lost Be
   * carefully with this param, use it only before you need to get rid of a
   * block */
  std::vector<uint16_t> pullAvailablePrimaryFragments(
      const bool discardMissingPackets = false);
  const uint8_t *get_primary_fragment_data_p(const int fragment_index);
  const int get_primary_fragment_data_size(const int fragment_index);

  // returns the n of primary and secondary fragments for this block
  int getNAvailableFragments() const {
    return m_n_available_primary_fragments + m_n_available_secondary_fragments;
  }
  /**
   * Reconstruct all missing primary fragments (data packets) by using the
   * received secondary (FEC) packets NOTE: reconstructing only part of the
   * missing data is not supported ! (That's a non-fixable technical detail of
   * FEC) NOTE: Do not call this method unless it is needed
   * @return the n of reconstructed packets
   */
  int reconstructAllMissingData();
  [[nodiscard]] uint64_t getBlockIdx() const { return blockIdx; }
  [[nodiscard]] std::optional<std::chrono::steady_clock::time_point>
  getFirstFragmentTimePoint() const {
    return firstFragmentTimePoint;
  }
  // Returns the number of missing primary packets (e.g. the n of actual data
  // packets that are missing) This only works if we know the "fec_k" parameter
  std::optional<int> get_missing_primary_packets() const;
  std::string get_missing_primary_packets_readable() const;
  int get_n_primary_fragments() const;
  int get_n_forwarded_primary_fragments() const;

 private:
  // the block idx marks which block this element refers to
  const uint64_t blockIdx = 0;
  // n of primary fragments that are already pulled out
  int nAlreadyForwardedPrimaryFragments = 0;
  // for each fragment (via fragment_idx) store if it has been received yet
  std::vector<bool> fragment_map;
  // holds all the data for all received fragments (if fragment_map says
  // UNAVALIABLE at this position, content is undefined)
  std::vector<std::array<uint8_t, MAX_PAYLOAD_BEFORE_FEC>> blockBuffer;
  // time point when the first fragment for this block was received (via
  // addFragment() )
  std::optional<std::chrono::steady_clock::time_point> firstFragmentTimePoint =
      std::nullopt;
  // as soon as we know any of the fragments for this block, we know how many
  // primary fragments this block contains (and therefore, how many primary or
  // secondary fragments we need to fully reconstruct)
  int m_n_primary_fragments_in_block = -1;
  // for the fec step, we need the size of the fec secondary fragments, which
  // should be equal for all secondary fragments
  int m_size_of_secondary_fragments = -1;
  int m_n_available_primary_fragments = 0;
  int m_n_available_secondary_fragments = 0;
};

#endif  // RX_BLOCK_HPP