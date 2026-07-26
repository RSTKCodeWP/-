#include "Encryptor.h"

#include <sodium/randombytes.h>

#include <cassert>
#include <cstring>
#include <stdexcept>

#include "Encryption.h"

void wb::Encryptor::makeNewSessionKey(
    std::array<uint8_t, 24U>& sessionKeyNonce,
    std::array<uint8_t, 32U + 16U>& sessionKeyData) {
  randombytes_buf(session_key.data(), sizeof(session_key));
  randombytes_buf(sessionKeyNonce.data(), sizeof(sessionKeyNonce));
  if (crypto_box_easy(sessionKeyData.data(), session_key.data(),
                      sizeof(session_key), sessionKeyNonce.data(),
                      rx_publickey.data(), tx_secretkey.data()) != 0) {
    throw std::runtime_error("Unable to make session key!");
  }
}

int wb::Encryptor::authenticate_and_encrypt(const uint64_t& nonce,
                                            const uint8_t* src, int src_len,
                                            uint8_t* dest) {
  if (!m_encrypt_data) {  // Only sign message
    memcpy(dest, src, src_len);
    uint8_t* sign = dest + src_len;
    const auto sub_key = wb::create_onetimeauth_subkey(nonce, session_key);
    crypto_onetimeauth(sign, src, src_len, sub_key.data());
    return src_len + crypto_onetimeauth_BYTES;
  }
  // sign and encrypt all together
  long long unsigned int ciphertext_len;
  crypto_aead_chacha20poly1305_encrypt(dest, &ciphertext_len, src, src_len,
                                       (uint8_t*)nullptr, 0, nullptr,
                                       (uint8_t*)&nonce, session_key.data());
  return (int)ciphertext_len;
}

std::shared_ptr<std::vector<uint8_t>>
wb::Encryptor::authenticate_and_encrypt_buff(const uint64_t& nonce,
                                             const uint8_t* src,
                                             std::size_t src_len) {
  auto ret = std::make_shared<std::vector<uint8_t>>(
      src_len + ENCRYPTION_ADDITIONAL_VALIDATION_DATA);
  const auto size = authenticate_and_encrypt(nonce, src, src_len, ret->data());
  assert(size == ret->size());
  return ret;
}