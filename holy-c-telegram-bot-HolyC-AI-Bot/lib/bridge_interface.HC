// Bridge Interface Definitions
// Functions that bridge must implement
// Terry's clean interface design

// Core bridge functions (implemented by C++/Python)
extern U8 *SendMessage(I64 chat_id, U8 *text);
extern U8 *OllamaChat(U8 *user_message);
extern I64 RandomNumber();
extern I64 GetCurrentTime();
extern U8 *GetBotStats();

// Memory functions (SQLite via bridge)
extern U8 *SaveMemory(I64 chat_id, U8 *data);
extern U8 *LoadMemory(I64 chat_id);
extern U8 *ClearMemory(I64 chat_id);

// Game functions (SQLite via bridge)
extern U8 *LoadGameData(I64 user_id);
extern U0 SaveGameData(I64 user_id, U8 *username, U8 *data);
extern I64 GetUserRank(I64 user_id);
extern U8 *GetTopPlayers(I64 page);
extern U0 SendMessageWithKeyboard(I64 chat_id, U8 *text, I64 page);

// String utilities (can be HolyC or bridge)
extern I64 StrLen(U8 *str);
extern I64 StrCmp(U8 *str1, U8 *str2);
extern I64 StrICmp(U8 *str1, U8 *str2);
extern I64 StrNCmp(U8 *str1, U8 *str2, I64 n);
extern U8 *StrFormat(U8 *format, ...);
extern U8 *StrUpper(U8 *str);
extern U8 *StrLower(U8 *str);
extern U8 *StrReverse(U8 *str);
extern I64 StrFind(U8 *haystack, U8 *needle);
extern U8 *StrSubstr(U8 *str, I64 start, I64 end);
extern I64 StrToI64(U8 *str);

// Math utilities (HolyC implementation)
extern Bool IsPrime(I64 n);
extern I64 Factorial(I64 n);
extern I64 Fibonacci(I64 n);
extern I64 NextPrime(I64 n);
extern I64 GCD(I64 a, I64 b);
extern I64 LCM(I64 a, I64 b);
extern Bool IsPerfect(I64 n);
extern I64 DivisorSum(I64 n);
extern I64 CollatzLength(I64 n);
extern I64 DigitSum(I64 n);
extern I64 ReverseNumber(I64 n);
extern Bool IsPalindrome(I64 n);

// Crypto utilities (HolyC implementation)
extern I64 HashString(U8 *str);
extern I64 Checksum(U8 *data);
extern U8 *HexEncode(U8 *data);
extern U8 *ROT13(U8 *text);
extern U8 *CaesarCipher(U8 *text, I64 shift);
extern U8 *Base64Encode(U8 *data);
extern U8 *GenerateKey(I64 length);
extern I64 PasswordStrength(U8 *password);

// Memory allocation
extern U8 *MAlloc(I64 size);
extern U0 Free(U8 *ptr);

// Divine randomness wrapper
I64 GetDivineNumber() {
  return RandomNumber();
}

// Print wrapper
U0 Print(U8 *format, ...) {
  // Bridge handles console output
}
