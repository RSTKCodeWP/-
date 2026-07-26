// Divine String Utilities Library
// Pure HolyC string manipulation
// Keep it simple - Terry's way

// String length
I64 StrLen(U8 *str) {
  I64 len = 0;
  while (str[len] != 0) len++;
  return len;
}

// String compare
I64 StrCmp(U8 *str1, U8 *str2) {
  I64 i = 0;
  while (str1[i] != 0 && str2[i] != 0) {
    if (str1[i] != str2[i]) {
      return str1[i] - str2[i];
    }
    i++;
  }
  return str1[i] - str2[i];
}

// String compare (case insensitive)
I64 StrICmp(U8 *str1, U8 *str2) {
  I64 i = 0;
  while (str1[i] != 0 && str2[i] != 0) {
    U8 c1 = str1[i];
    U8 c2 = str2[i];
    
    // Convert to lowercase
    if (c1 >= 'A' && c1 <= 'Z') c1 += 32;
    if (c2 >= 'A' && c2 <= 'Z') c2 += 32;
    
    if (c1 != c2) return c1 - c2;
    i++;
  }
  return str1[i] - str2[i];
}

// String compare first N chars
I64 StrNCmp(U8 *str1, U8 *str2, I64 n) {
  I64 i = 0;
  while (i < n && str1[i] != 0 && str2[i] != 0) {
    if (str1[i] != str2[i]) {
      return str1[i] - str2[i];
    }
    i++;
  }
  if (i == n) return 0;
  return str1[i] - str2[i];
}

// String copy
U8 *StrCopy(U8 *dest, U8 *src) {
  I64 i = 0;
  while (src[i] != 0) {
    dest[i] = src[i];
    i++;
  }
  dest[i] = 0;
  return dest;
}

// String concatenate
U8 *StrCat(U8 *dest, U8 *src) {
  I64 dest_len = StrLen(dest);
  I64 i = 0;
  while (src[i] != 0) {
    dest[dest_len + i] = src[i];
    i++;
  }
  dest[dest_len + i] = 0;
  return dest;
}

// String to uppercase
U8 *StrUpper(U8 *str) {
  I64 i = 0;
  while (str[i] != 0) {
    if (str[i] >= 'a' && str[i] <= 'z') {
      str[i] -= 32;
    }
    i++;
  }
  return str;
}

// String to lowercase
U8 *StrLower(U8 *str) {
  I64 i = 0;
  while (str[i] != 0) {
    if (str[i] >= 'A' && str[i] <= 'Z') {
      str[i] += 32;
    }
    i++;
  }
  return str;
}

// String reverse
U8 *StrReverse(U8 *str) {
  I64 len = StrLen(str);
  I64 i = 0;
  while (i < len / 2) {
    U8 temp = str[i];
    str[i] = str[len - 1 - i];
    str[len - 1 - i] = temp;
    i++;
  }
  return str;
}

// Find substring
I64 StrFind(U8 *haystack, U8 *needle) {
  I64 h_len = StrLen(haystack);
  I64 n_len = StrLen(needle);
  
  if (n_len == 0) return 0;
  if (n_len > h_len) return -1;
  
  for (I64 i = 0; i <= h_len - n_len; i++) {
    Bool match = TRUE;
    for (I64 j = 0; j < n_len; j++) {
      if (haystack[i + j] != needle[j]) {
        match = FALSE;
        break;
      }
    }
    if (match) return i;
  }
  
  return -1;
}

// Substring
U8 *StrSubstr(U8 *str, I64 start, I64 end) {
  I64 len = end - start;
  U8 *result = MAlloc(len + 1);
  
  for (I64 i = 0; i < len; i++) {
    result[i] = str[start + i];
  }
  result[len] = 0;
  
  return result;
}

// String format (simple version)
U8 *StrFormat(U8 *format, ...) {
  // Bridge will handle this
  // This is a placeholder for HolyC
  return format;
}

// Trim whitespace
U8 *StrTrim(U8 *str) {
  // Find first non-whitespace
  I64 start = 0;
  while (str[start] == ' ' || str[start] == '\t' || 
         str[start] == '\n' || str[start] == '\r') {
    start++;
  }
  
  // Find last non-whitespace
  I64 end = StrLen(str) - 1;
  while (end >= start && (str[end] == ' ' || str[end] == '\t' || 
         str[end] == '\n' || str[end] == '\r')) {
    end--;
  }
  
  return StrSubstr(str, start, end + 1);
}

// String to integer
I64 StrToI64(U8 *str) {
  I64 result = 0;
  I64 sign = 1;
  I64 i = 0;
  
  // Handle negative
  if (str[0] == '-') {
    sign = -1;
    i = 1;
  }
  
  while (str[i] >= '0' && str[i] <= '9') {
    result = result * 10 + (str[i] - '0');
    i++;
  }
  
  return result * sign;
}

// Integer to string
U8 *I64ToStr(I64 num) {
  U8 *result = MAlloc(32);
  I64 i = 0;
  Bool negative = FALSE;
  
  if (num < 0) {
    negative = TRUE;
    num = -num;
  }
  
  // Convert digits in reverse
  do {
    result[i++] = (num % 10) + '0';
    num /= 10;
  } while (num > 0);
  
  if (negative) result[i++] = '-';
  result[i] = 0;
  
  // Reverse the string
  return StrReverse(result);
}
