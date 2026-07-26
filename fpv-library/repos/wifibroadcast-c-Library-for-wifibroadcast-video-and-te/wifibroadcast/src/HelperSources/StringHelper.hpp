//
// Created by Constantin on 09.10.2017.
//

#ifndef OSDTESTER_STRINGHELPER_H
#define OSDTESTER_STRINGHELPER_H

#include <array>
#include <sstream>
#include <string>
#include <vector>

class StringHelper {
 public:
  template <typename T>
  static std::string vectorAsString(const std::vector<T>& v) {
    std::stringstream ss;
    ss << "[";
    for (int i = 0; i < v.size(); i++) {
      ss << std::to_string(v[i]);
      if (i != v.size() - 1) {
        ss << ",";
      }
    }
    ss << "]";
    return ss.str();
  }

  static std::string string_vec_as_string(const std::vector<std::string>& v) {
    std::stringstream ss;
    ss << "[";
    for (int i = 0; i < v.size(); i++) {
      ss << v[i];
      if (i != v.size() - 1) {
        ss << ",";
      }
    }
    ss << "]";
    return ss.str();
  }
  static std::string bytes_as_string_decimal(const uint8_t* data,
                                             int data_len) {
    std::stringstream ss;
    ss << "[";
    for (int i = 0; i < data_len; i++) {
      ss << (int)data[i];
      if (i != data_len - 1) {
        ss << ",";
      }
    }
    ss << "]";
    return ss.str();
  }
  static std::string byte_as_hex(uint8_t byte) {
    char str[100] = {};
    sprintf(str, "%x", byte);
    return "0x" + std::string(str);
  }
  static std::string bytes_as_string_hex(const uint8_t* data, int data_len) {
    std::stringstream ss;
    ss << "[";
    for (int i = 0; i < data_len; i++) {
      ss << byte_as_hex(data[i]);
      if (i != data_len - 1) {
        ss << ",";
      }
    }
    ss << "]";
    return ss.str();
  }

  template <typename T, std::size_t S>
  static std::string arrayAsString(const std::array<T, S>& a) {
    std::stringstream ss;
    ss << "[";
    for (int i = 0; i < a.size(); i++) {
      ss << std::to_string(a[i]);
      if (i != a.size() - 1) {
        ss << ",";
      }
    }
    ss << "]";
    return ss.str();
  }

  static std::string memorySizeReadable(const size_t sizeBytes) {
    // more than one MB
    if (sizeBytes > 1024 * 1024) {
      float sizeMB = (float)sizeBytes / 1024.0 / 1024.0;
      return std::to_string(sizeMB) + "mB";
    }
    // more than one KB
    if (sizeBytes > 1024) {
      float sizeKB = (float)sizeBytes / 1024.0;
      return std::to_string(sizeKB) + "kB";
    }
    return std::to_string(sizeBytes) + "B";
  }

  static std::string float_to_string_with_precision(float value,
                                                    int precision = -1) {
    if (precision == -1) {
      return std::to_string(value);
    }
    std::stringstream ss;
    ss.precision(precision);
    ss << std::fixed << value;
    return ss.str();
  }

  static std::string bitrate_readable(int64_t bits_per_second) {
    if (bits_per_second <= 0) {
      return std::to_string(bits_per_second) + " Bit/s";
    }
    if (bits_per_second > 1024 * 1024) {
      float mBitsPerSecond = (float)bits_per_second / 1000.0 / 1000.0;
      return float_to_string_with_precision(mBitsPerSecond, 2) + "mBit/s";
    }
    if (bits_per_second > 1024) {
      float kBitsPerSecond = (float)bits_per_second / 1000.0;
      return float_to_string_with_precision(kBitsPerSecond, 2) + "kBit/s";
    }
    return float_to_string_with_precision(bits_per_second, 2) + "Bit/s";
  }
};

#endif  // OSDTESTER_STRINGHELPER_H
