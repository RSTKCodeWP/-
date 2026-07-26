//
// Created by consti10 on 13.08.23.
//

#include "Encryption.h"

#include <spdlog/spdlog.h>

#include <cassert>
#include <cstring>
#include <iostream>

#include "../wifibroadcast_spdlog.h"

wb::KeyPairTxRx wb::generate_keypair_random() {
  KeyPairTxRx ret{};
  crypto_box_keypair(ret.key_1.public_key.data(), ret.key_1.secret_key.data());
  crypto_box_keypair(ret.key_2.public_key.data(), ret.key_2.secret_key.data());
  return ret;
}

// Salts generated once using
// https://www.random.org/cgi-bin/randbyte?nbytes=16&format=d We want
// deterministic seed from a pw, and are only interested in making it impossible
// to reverse the process (even though the salt is plain text)
static constexpr std::array<uint8_t, crypto_pwhash_SALTBYTES> OHD_SALT_AIR{
    192, 189, 216, 102, 56, 153, 154, 92, 228, 26, 49, 209, 157, 7, 128, 207};
static constexpr std::array<uint8_t, crypto_pwhash_SALTBYTES> OHD_SALT_GND{
    179, 30, 150, 20, 17, 200, 225, 82, 48, 64, 18, 130, 89, 62, 83, 234};

std::array<uint8_t, crypto_box_SEEDBYTES>
wb::create_seed_from_password_openhd_salt(const std::string& pw,
                                          bool use_salt_air) {
  const auto salt = use_salt_air ? OHD_SALT_AIR : OHD_SALT_GND;
  std::array<uint8_t, crypto_box_SEEDBYTES> key{};
  if (crypto_pwhash(key.data(), key.size(), pw.c_str(), pw.length(),
                    salt.data(), crypto_pwhash_OPSLIMIT_INTERACTIVE,
                    crypto_pwhash_MEMLIMIT_INTERACTIVE,
                    crypto_pwhash_ALG_DEFAULT) != 0) {
    std::cerr << "ERROR: cannot create_seed_from_password_openhd_salt"
              << std::endl;
    assert(false);
    // out of memory
  }
  return key;
}

wb::KeyPairTxRx wb::generate_keypair_from_bind_phrase(
    const std::string& bind_phrase) {
  const auto seed_air =
      create_seed_from_password_openhd_salt(bind_phrase, true);
  const auto seed_gnd =
      create_seed_from_password_openhd_salt(bind_phrase, false);
  KeyPairTxRx ret{};
  crypto_box_seed_keypair(ret.key_1.public_key.data(),
                          ret.key_1.secret_key.data(), seed_air.data());
  crypto_box_seed_keypair(ret.key_2.public_key.data(),
                          ret.key_2.secret_key.data(), seed_gnd.data());
  return ret;
}

std::array<uint8_t, crypto_aead_chacha20poly1305_KEYBYTES>
wb::create_onetimeauth_subkey(const uint64_t& nonce,
                              const std::array<uint8_t, 32U>& session_key) {
  // sub-key for this packet
  std::array<uint8_t, 32> subkey{};
  // We only have an 8 byte nonce, this should be enough entropy
  std::array<uint8_t, 16> nonce_buf{0};
  memcpy(nonce_buf.data(), (uint8_t*)&nonce, 8);
  crypto_core_hchacha20(subkey.data(), nonce_buf.data(), session_key.data(),
                        nullptr);
  return subkey;
}