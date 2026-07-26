// Divine Cryptography Library
// Simple hashing and encoding - Terry's way
// Keep it simple, no bloat

// Simple hash function (DJB2)
I64 HashString(U8 *str) {
  I64 hash = 5381;
  I64 i = 0;
  
  while (str[i] != 0) {
    hash = ((hash << 5) + hash) + str[i];
    i++;
  }
  
  return hash;
}

// XOR cipher (simple encryption)
U8 *XORCipher(U8 *text, U8 *key) {
  I64 text_len = StrLen(text);
  I64 key_len = StrLen(key);
  
  if (key_len == 0) return text;
  
  U8 *result = MAlloc(text_len + 1);
  
  for (I64 i = 0; i < text_len; i++) {
    result[i] = text[i] ^ key[i % key_len];
  }
  result[text_len] = 0;
  
  return result;
}

// Caesar cipher
U8 *CaesarCipher(U8 *text, I64 shift) {
  I64 len = StrLen(text);
  U8 *result = MAlloc(len + 1);
  
  shift = shift % 26;
  if (shift < 0) shift += 26;
  
  for (I64 i = 0; i < len; i++) {
    U8 c = text[i];
    
    if (c >= 'A' && c <= 'Z') {
      result[i] = ((c - 'A' + shift) % 26) + 'A';
    } else if (c >= 'a' && c <= 'z') {
      result[i] = ((c - 'a' + shift) % 26) + 'a';
    } else {
      result[i] = c;
    }
  }
  result[len] = 0;
  
  return result;
}

// ROT13 (special case of Caesar)
U8 *ROT13(U8 *text) {
  return CaesarCipher(text, 13);
}

// Simple checksum
I64 Checksum(U8 *data) {
  I64 sum = 0;
  I64 i = 0;
  
  while (data[i] != 0) {
    sum += data[i];
    i++;
  }
  
  return sum % 256;
}

// Base64 encode (simplified)
U8 *Base64Encode(U8 *data) {
  // Simplified version - bridge will handle full implementation
  // This is a placeholder showing the concept
  
  U8 *base64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  I64 len = StrLen(data);
  I64 output_len = ((len + 2) / 3) * 4;
  
  U8 *result = MAlloc(output_len + 1);
  I64 j = 0;
  
  for (I64 i = 0; i < len; i += 3) {
    I64 b1 = data[i];
    I64 b2 = (i + 1 < len) ? data[i + 1] : 0;
    I64 b3 = (i + 2 < len) ? data[i + 2] : 0;
    
    result[j++] = base64_chars[b1 >> 2];
    result[j++] = base64_chars[((b1 & 0x03) << 4) | (b2 >> 4)];
    result[j++] = (i + 1 < len) ? base64_chars[((b2 & 0x0F) << 2) | (b3 >> 6)] : '=';
    result[j++] = (i + 2 < len) ? base64_chars[b3 & 0x3F] : '=';
  }
  
  result[j] = 0;
  return result;
}

// Generate random key
U8 *GenerateKey(I64 length) {
  U8 *key = MAlloc(length + 1);
  
  for (I64 i = 0; i < length; i++) {
    I64 r = GetDivineNumber() % 62;
    
    if (r < 10) {
      key[i] = '0' + r;
    } else if (r < 36) {
      key[i] = 'A' + (r - 10);
    } else {
      key[i] = 'a' + (r - 36);
    }
  }
  
  key[length] = 0;
  return key;
}

// Simple password strength check
I64 PasswordStrength(U8 *password) {
  I64 len = StrLen(password);
  if (len < 4) return 0; // Very weak
  
  Bool has_upper = FALSE;
  Bool has_lower = FALSE;
  Bool has_digit = FALSE;
  Bool has_special = FALSE;
  
  for (I64 i = 0; i < len; i++) {
    U8 c = password[i];
    if (c >= 'A' && c <= 'Z') has_upper = TRUE;
    else if (c >= 'a' && c <= 'z') has_lower = TRUE;
    else if (c >= '0' && c <= '9') has_digit = TRUE;
    else has_special = TRUE;
  }
  
  I64 strength = 0;
  if (len >= 8) strength++;
  if (len >= 12) strength++;
  if (has_upper) strength++;
  if (has_lower) strength++;
  if (has_digit) strength++;
  if (has_special) strength++;
  
  return strength; // 0-6 scale
}

// Hex encode
U8 *HexEncode(U8 *data) {
  I64 len = StrLen(data);
  U8 *result = MAlloc(len * 2 + 1);
  U8 *hex_chars = "0123456789ABCDEF";
  
  for (I64 i = 0; i < len; i++) {
    result[i * 2] = hex_chars[(data[i] >> 4) & 0x0F];
    result[i * 2 + 1] = hex_chars[data[i] & 0x0F];
  }
  
  result[len * 2] = 0;
  return result;
}
