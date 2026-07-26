#ifndef ENCRYPTION_HPP
#define ENCRYPTION_HPP

#include <sodium.h>

#include <array>
#include <memory>
#include <string>
#include <vector>

#include "KeyPair.h"

// Namespace that can be used to add encryption+packet validation
// (Or packet validation only to save CPU resources)
// to a lossy unidirectional link
// Packet validation is quite important, to make sure only openhd packets (and
// not standard wifi packets) are used in OpenHD The Encryption / Decryption
// name(s) are legacy - The more difficult part is dealing with the session key
// stuff, and this class makes it a bit easier to use

// one time authentication and encryption nicely are really similar
static_assert(crypto_onetimeauth_BYTES == crypto_aead_chacha20poly1305_ABYTES);
// Encryption (or packet validation) adds this many bytes to the end of the
// message
static constexpr auto ENCRYPTION_ADDITIONAL_VALIDATION_DATA =
    crypto_aead_chacha20poly1305_ABYTES;

namespace wb {

/**
 * Generates a new keypair. Non-deterministic, 100% secure.
 */
KeyPairTxRx generate_keypair_random();

/**
 * See https://libsodium.gitbook.io/doc/password_hashing
 * Deterministic seed from password, but hides password itself (non-reversible)
 * Uses a pre-defined salt to be deterministic
 */
std::array<uint8_t, crypto_box_SEEDBYTES> create_seed_from_password_openhd_salt(
    const std::string& pw, bool use_salt_air);

// We always use the same bind phrase by default
static constexpr auto DEFAULT_BIND_PHRASE = "openhd";
/**
 * Generates 2 new (deterministic) tx rx keys, using the seed created from the
 * pw.
 * @param bind_phrase the password / bind phrase
 */
KeyPairTxRx generate_keypair_from_bind_phrase(
    const std::string& bind_phrase = DEFAULT_BIND_PHRASE);

/**
 * https://libsodium.gitbook.io/doc/key_derivation
 * UINT16SeqNrHelper since we both support encryption and one time validation to
 * save cpu performance
 */
std::array<uint8_t, 32> create_onetimeauth_subkey(
    const uint64_t& nonce,
    const std::array<uint8_t, crypto_aead_chacha20poly1305_KEYBYTES>&
        session_key);

}  // namespace wb

#endif  // ENCRYPTION_HPP