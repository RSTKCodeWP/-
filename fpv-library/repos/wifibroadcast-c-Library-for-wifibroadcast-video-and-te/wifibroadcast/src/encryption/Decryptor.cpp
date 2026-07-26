#include "Decryptor.h"

#include <sodium/crypto_onetimeauth.h>

#include <cassert>
#include <cstring>

#include "../wifibroadcast_spdlog.h"
#include "Encryption.h"

wb::Decryptor::Decryptor(wb::Key key1)
    : rx_secretkey(key1.secret_key), tx_publickey(key1.public_key) {
  memset(session_key.data(), 0, sizeof(session_key));
}

int wb::Decryptor::onNewPacketSessionKeyData(
    const std::array<uint8_t, 24U>& sessionKeyNonce,
    const std::array<uint8_t, 32U + 16U>& sessionKeyData) {
  std::array<uint8_t, sizeof(session_key)> new_session_key{};
  if (crypto_box_open_easy(new_session_key.data(), sessionKeyData.data(),
                           sessionKeyData.size(), sessionKeyNonce.data(),
                           tx_publickey.data(), rx_secretkey.data()) != 0) {
    // this basically should just never happen, and is an error
    wifibroadcast::log::get_default()->warn("unable to decrypt session key");
    return SESSION_NOT_VALID;
  }
  if (memcmp(session_key.data(), new_session_key.data(), sizeof(session_key)) !=
      0) {
    wifibroadcast::log::get_default()->info("Decryptor-New session detected");
    session_key = new_session_key;
    m_has_valid_session = true;
    return SESSION_VALID_NEW;
  }
  // this is NOT an error, the same session key is sent multiple times !
  return SESSION_VALID_NOT_NEW;
}

bool wb::Decryptor::authenticate(const uint64_t& nonce,
                                 const uint8_t* encrypted, int encrypted_size,
                                 uint8_t* dest) {
  const auto payload_size = encrypted_size - crypto_onetimeauth_BYTES;
  assert(payload_size > 0);
  const uint8_t* sign = encrypted + payload_size;
  // const int
  // res=crypto_auth_hmacsha256_verify(sign,msg,payload_size,session_key.data());
  const auto sub_key = wb::create_onetimeauth_subkey(nonce, session_key);
  const int res =
      crypto_onetimeauth_verify(sign, encrypted, payload_size, sub_key.data());
  if (res != -1) {
    memcpy(dest, encrypted, payload_size);
    return true;
  }
  return false;
}

bool wb::Decryptor::decrypt(const uint64_t& nonce, const uint8_t* encrypted,
                            int encrypted_size, uint8_t* dest) {
  unsigned long long mlen;
  int res = crypto_aead_chacha20poly1305_decrypt(
      dest, &mlen, nullptr, encrypted, encrypted_size, nullptr, 0,
      (uint8_t*)(&nonce), session_key.data());
  return res != -1;
}

std::shared_ptr<std::vector<uint8_t>>
wb::Decryptor::authenticate_and_decrypt_buff(const uint64_t& nonce,
                                             const uint8_t* encrypted,
                                             int encrypted_size,
                                             bool isEncrypt) {
  auto ret = std::make_shared<std::vector<uint8_t>>(
      encrypted_size - crypto_aead_chacha20poly1305_ABYTES);

  bool res;
  if (isEncrypt) {
    res = decrypt(nonce, encrypted, encrypted_size, ret->data());
  } else {
    res = authenticate(nonce, encrypted, encrypted_size, ret->data());
  }

  if (res) {
    return ret;
  }
  return nullptr;
}