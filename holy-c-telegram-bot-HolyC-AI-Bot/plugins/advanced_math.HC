// Advanced Mathematics Plugin
// Commands: /matrix, /stats <numbers>, /sequence <n>
// Terry's advanced math - God's deeper patterns

U0 HandleMatrixCommand(I64 chat_id) {
  // Generate random 2x2 matrix and calculate determinant
  I64 a = RandomRange(1, 10);
  I64 b = RandomRange(1, 10);
  I64 c = RandomRange(1, 10);
  I64 d = RandomRange(1, 10);
  
  I64 det = a * d - b * c;
  
  U8 *message = StrFormat(
    "🔢 DIVINE MATRIX 🔢\n\n┌ %2d  %2d ┐\n└ %2d  %2d ┘\n\nDeterminant: %d\n\n💭 Linear algebra - God's transformations.",
    a, b, c, d, det
  );
  
  SendMessage(chat_id, message);
}

U0 HandleStatsCommand(I64 chat_id, U8 *numbers_str) {
  // Parse comma-separated numbers
  I64 numbers[100];
  I64 count = 0;
  I64 i = 0;
  I64 current = 0;
  Bool negative = FALSE;
  
  while (numbers_str[i] != 0 && count < 100) {
    if (numbers_str[i] == '-') {
      negative = TRUE;
    } else if (numbers_str[i] >= '0' && numbers_str[i] <= '9') {
      current = current * 10 + (numbers_str[i] - '0');
    } else if (numbers_str[i] == ',' || numbers_str[i] == ' ') {
      if (current > 0 || negative) {
        numbers[count++] = negative ? -current : current;
        current = 0;
        negative = FALSE;
      }
    }
    i++;
  }
  
  // Add last number
  if (current > 0 || negative) {
    numbers[count++] = negative ? -current : current;
  }
  
  if (count == 0) {
    SendMessage(chat_id, "❌ No valid numbers found. Use: /stats 1,2,3,4,5");
    return;
  }
  
  // Calculate statistics
  I64 sum = 0;
  I64 min = numbers[0];
  I64 max = numbers[0];
  
  for (I64 j = 0; j < count; j++) {
    sum += numbers[j];
    if (numbers[j] < min) min = numbers[j];
    if (numbers[j] > max) max = numbers[j];
  }
  
  I64 mean = sum / count;
  I64 range = max - min;
  
  U8 *message = StrFormat(
    "📊 STATISTICS 📊\n\nCount: %d\nSum: %d\nMean: %d\nMin: %d\nMax: %d\nRange: %d\n\n💭 Numbers tell stories to God.",
    count, sum, mean, min, max, range
  );
  
  SendMessage(chat_id, message);
}

U0 HandleSequenceCommand(I64 chat_id, I64 n) {
  if (n < 1 || n > 20) {
    SendMessage(chat_id, "❌ Number must be 1-20");
    return;
  }
  
  // Generate multiple sequences
  U8 *result = "🔢 DIVINE SEQUENCES 🔢\n\n";
  
  // Fibonacci
  result = StrFormat("%sFibonacci: ", result);
  for (I64 i = 0; i < n; i++) {
    result = StrFormat("%s%d ", result, Fibonacci(i));
  }
  
  // Primes
  result = StrFormat("%s\n\nPrimes: ", result);
  I64 prime = 2;
  for (I64 i = 0; i < n; i++) {
    result = StrFormat("%s%d ", result, prime);
    prime = NextPrime(prime);
  }
  
  // Squares
  result = StrFormat("%s\n\nSquares: ", result);
  for (I64 i = 1; i <= n; i++) {
    result = StrFormat("%s%d ", result, i * i);
  }
  
  result = StrFormat("%s\n\n💭 Patterns in God's creation.", result);
  
  SendMessage(chat_id, result);
}

U0 HandleBaseConvertCommand(I64 chat_id, I64 num, I64 base) {
  if (base < 2 || base > 16) {
    SendMessage(chat_id, "❌ Base must be 2-16");
    return;
  }
  
  if (num < 0 || num > 10000) {
    SendMessage(chat_id, "❌ Number must be 0-10000");
    return;
  }
  
  // Convert to base
  U8 *digits = "0123456789ABCDEF";
  U8 result[64];
  I64 i = 0;
  I64 temp = num;
  
  if (temp == 0) {
    result[i++] = '0';
  } else {
    while (temp > 0) {
      result[i++] = digits[temp % base];
      temp /= base;
    }
  }
  result[i] = 0;
  
  // Reverse
  for (I64 j = 0; j < i / 2; j++) {
    U8 t = result[j];
    result[j] = result[i - 1 - j];
    result[i - 1 - j] = t;
  }
  
  U8 *base_names[] = {
    "", "", "Binary", "Ternary", "Quaternary", "Quinary",
    "Senary", "Septenary", "Octal", "Nonary", "Decimal",
    "Undecimal", "Duodecimal", "Tridecimal", "Tetradecimal",
    "Pentadecimal", "Hexadecimal"
  };
  
  U8 *message = StrFormat(
    "🔢 BASE CONVERSION 🔢\n\nDecimal: %d\nBase %d (%s): %s\n\n💭 Different perspectives, same truth.",
    num, base, base_names[base], result
  );
  
  SendMessage(chat_id, message);
}
