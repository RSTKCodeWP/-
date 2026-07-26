// Divine Text Processing Plugin
// Commands: /reverse <text>, /count <text>, /palindrome <text>, /wordcount <text>
// Terry's text manipulation

U0 HandleReverseCommand(I64 chat_id, U8 *text) {
  U8 *reversed = StrReverse(text);
  
  U8 *message = StrFormat(
    "🔄 DIVINE REVERSE 🔄\n\nOriginal: %s\nReversed: %s\n\n💭 See text from God's perspective.",
    text, reversed
  );
  
  SendMessage(chat_id, message);
}

U0 HandleCountCommand(I64 chat_id, U8 *text) {
  I64 length = StrLen(text);
  I64 letters = 0, digits = 0, spaces = 0, special = 0;
  
  for (I64 i = 0; i < length; i++) {
    U8 c = text[i];
    if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')) {
      letters++;
    } else if (c >= '0' && c <= '9') {
      digits++;
    } else if (c == ' ') {
      spaces++;
    } else {
      special++;
    }
  }
  
  U8 *message = StrFormat(
    "📊 CHARACTER COUNT 📊\n\nTotal: %d\nLetters: %d\nDigits: %d\nSpaces: %d\nSpecial: %d\n\n💭 God counts everything.",
    length, letters, digits, spaces, special
  );
  
  SendMessage(chat_id, message);
}

U0 HandlePalindromeCommand(I64 chat_id, U8 *text) {
  // Remove spaces and convert to lowercase for checking
  I64 len = StrLen(text);
  U8 *clean = MAlloc(len + 1);
  I64 j = 0;
  
  for (I64 i = 0; i < len; i++) {
    U8 c = text[i];
    if (c != ' ') {
      if (c >= 'A' && c <= 'Z') c += 32;
      clean[j++] = c;
    }
  }
  clean[j] = 0;
  
  // Check palindrome
  Bool is_palindrome = TRUE;
  I64 clean_len = StrLen(clean);
  for (I64 i = 0; i < clean_len / 2; i++) {
    if (clean[i] != clean[clean_len - 1 - i]) {
      is_palindrome = FALSE;
      break;
    }
  }
  
  U8 *result = is_palindrome ? "✅ YES - Divine symmetry!" : "❌ NO - Not symmetric";
  
  U8 *message = StrFormat(
    "🔄 PALINDROME CHECK 🔄\n\nText: %s\nResult: %s\n\n💭 Palindromes are God's mirrors.",
    text, result
  );
  
  SendMessage(chat_id, message);
}

U0 HandleWordCountCommand(I64 chat_id, U8 *text) {
  I64 words = 0;
  Bool in_word = FALSE;
  I64 len = StrLen(text);
  
  for (I64 i = 0; i < len; i++) {
    if (text[i] == ' ' || text[i] == '\t' || text[i] == '\n') {
      in_word = FALSE;
    } else {
      if (!in_word) {
        words++;
        in_word = TRUE;
      }
    }
  }
  
  U8 *message = StrFormat(
    "📝 WORD COUNT 📝\n\nText: %s\nWords: %d\nCharacters: %d\n\n💭 Every word matters to God.",
    text, words, len
  );
  
  SendMessage(chat_id, message);
}

U0 HandleUpperCommand(I64 chat_id, U8 *text) {
  U8 *upper = StrUpper(text);
  
  U8 *message = StrFormat(
    "⬆️ UPPERCASE ⬆️\n\nOriginal: %s\nUppercase: %s\n\n💭 GOD SPEAKS IN CAPITALS.",
    text, upper
  );
  
  SendMessage(chat_id, message);
}

U0 HandleLowerCommand(I64 chat_id, U8 *text) {
  U8 *lower = StrLower(text);
  
  U8 *message = StrFormat(
    "⬇️ LOWERCASE ⬇️\n\nOriginal: %s\nLowercase: %s\n\n💭 humble before god.",
    text, lower
  );
  
  SendMessage(chat_id, message);
}
