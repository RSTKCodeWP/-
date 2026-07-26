#ifndef ENCRYPTION_FS_UTILS_HPP
#define ENCRYPTION_FS_UTILS_HPP

#include <optional>
#include <string>

#include "KeyPair.h"

namespace wb {

/**
 * Saves the KeyPairTxRx as a raw file
 */
bool write_keypair_to_file(const KeyPairTxRx& keypair_txrx,
                           const std::string& filename);

/**
 * Reads a raw KeyPairTxRx from a raw file previusly generated.
 */
std::optional<KeyPairTxRx> read_keypair_from_file(const std::string& filename);

}  // namespace wb

#endif  // ENCRYPTION_FS_UTILS_HPP