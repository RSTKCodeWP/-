#ifndef ENCRIPTOR_HPP
#define ENCRIPTOR_HPP

#include <sodium/crypto_aead_chacha20poly1305.h>
#include <sodium/crypto_box.h>

#include <array>
#include <cstdint>
#include <memory>
#include <vector>

#include "KeyPair.h"

namespace wb {
class Encryptor {
 public:
  /**
   *
   * @param key1 encryption key, otherwise enable a default deterministic
   * encryption key by using std::nullopt
   * @param DISABLE_ENCRYPTION_FOR_PERFORMANCE only validate, do not encrypt
   * (less CPU usage)
   */
  explicit Encryptor(wb::Key key1)
      : tx_secretkey(key1.secret_key), rx_publickey(key1.public_key) {}
  /**
   * Creates a new session key, simply put, the data we can send publicly
   * @param sessionKeyNonce filled with public nonce
   * @param sessionKeyData filled with public data
   */
  void makeNewSessionKey(
      std::array<uint8_t, crypto_box_NONCEBYTES> &sessionKeyNonce,
      std::array<uint8_t, crypto_aead_chacha20poly1305_KEYBYTES +
                              crypto_box_MACBYTES> &sessionKeyData);
  /**
   * Encrypt the given message of size @param src_len
   * (Or if encryption is disabled, only calculate the message sign)
   * and write the (encrypted) data appended by the validation data into dest
   * @param nonce: needs to be different for every packet
   * @param src @param src_len message to encrypt
   * @param dest needs to point to a memory region at least @param src_len + 16
   * bytes big Returns written data size (msg payload plus sign data)
   */
  int authenticate_and_encrypt(const uint64_t &nonce, const uint8_t *src,
                               int src_len, uint8_t *dest);

  /**
   *  For easy use - returns a buffer including (encrypted) payload plus
   * validation data
   */
  std::shared_ptr<std::vector<uint8_t>> authenticate_and_encrypt_buff(
      const uint64_t &nonce, const uint8_t *src, std::size_t src_len);
  /**
   * Disables encryption (to save cpu performance) but keeps packet validation
   * functionality
   * @param encryption_enabled
   */
  void set_encryption_enabled(bool encryption_enabled) {
    m_encrypt_data = encryption_enabled;
  }

 private:
  // tx->rx keypair
  const std::array<uint8_t, crypto_box_SECRETKEYBYTES> tx_secretkey{};
  const std::array<uint8_t, crypto_box_PUBLICKEYBYTES> rx_publickey{};
  std::array<uint8_t, crypto_aead_chacha20poly1305_KEYBYTES> session_key{};
  // use this one if you are worried about CPU usage when using encryption
  bool m_encrypt_data = true;
};

}  // namespace wb

#endif  // ENCRIPTOR_HPP