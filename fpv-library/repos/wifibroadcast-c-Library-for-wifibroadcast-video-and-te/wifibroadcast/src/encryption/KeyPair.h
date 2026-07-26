#ifndef KEY_HPP
#define KEY_HPP
#include <sodium/crypto_box.h>

#include <array>
#include <cstdint>

namespace wb {
// A wb key consists of a public and secret key
struct Key {
  std::array<uint8_t, crypto_box_PUBLICKEYBYTES> public_key;
  std::array<uint8_t, crypto_box_SECRETKEYBYTES> secret_key;
  int operator==(const Key& other) const {
    return std::equal(std::begin(public_key), std::end(public_key),
                      std::begin(other.public_key)) &&
           std::equal(std::begin(secret_key), std::end(secret_key),
                      std::begin(other.secret_key));
  }
} __attribute__((packed));
;
static_assert(sizeof(Key) ==
              crypto_box_PUBLICKEYBYTES + crypto_box_SECRETKEYBYTES);

// A wb keypair are 2 keys, one for transmitting, one for receiving
// (Since both ground and air unit talk bidirectional)
// We use a different key for the down-link / uplink, respective
static constexpr const int KEYPAIR_RAW_SIZE = 32 * 4;
struct KeyPairTxRx {
  Key key_1;
  Key key_2;
  Key get_tx_key(bool is_air) { return is_air ? key_1 : key_2; }
  Key get_rx_key(bool is_air) { return is_air ? key_2 : key_1; }
  int operator==(const KeyPairTxRx& other) const {
    return key_1 == other.key_1 && key_2 == other.key_2;
  }
  static std::array<uint8_t, KEYPAIR_RAW_SIZE> as_raw(
      const KeyPairTxRx& keypair);
  static KeyPairTxRx from_raw(const std::array<uint8_t, KEYPAIR_RAW_SIZE>& raw);
} __attribute__((packed));
static_assert(sizeof(KeyPairTxRx) == 2 * sizeof(Key));
static_assert(sizeof(KeyPairTxRx) == KEYPAIR_RAW_SIZE);

}  // namespace wb

#endif  // KEY_HPP
