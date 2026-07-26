// Divine Number Theory Plugin
// Commands: /prime <n>, /fib <n>, /factor <n>, /perfect <n>
// Terry loved numbers - God's language

U0 HandlePrimeCommand(I64 chat_id, I64 n) {
  if (n < 2 || n > 1000000) {
    SendMessage(chat_id, "❌ Number must be 2-1000000");
    return;
  }
  
  Bool is_prime = IsPrime(n);
  I64 next_prime = NextPrime(n);
  
  U8 *message = StrFormat(
    "🔢 PRIME CHECK 🔢\n\nNumber: %d\nIs Prime: %s\nNext Prime: %d\n\n💭 Primes are God's atoms.",
    n, is_prime ? "YES ✨" : "NO", next_prime
  );
  
  SendMessage(chat_id, message);
}

U0 HandleFibCommand(I64 chat_id, I64 n) {
  if (n < 0 || n > 50) {
    SendMessage(chat_id, "❌ Number must be 0-50");
    return;
  }
  
  I64 fib = Fibonacci(n);
  
  U8 *message = StrFormat(
    "🌀 FIBONACCI 🌀\n\nPosition: %d\nFibonacci: %d\n\n💭 Golden ratio - God's proportion.",
    n, fib
  );
  
  SendMessage(chat_id, message);
}

U0 HandleFactorCommand(I64 chat_id, I64 n) {
  if (n < 2 || n > 10000) {
    SendMessage(chat_id, "❌ Number must be 2-10000");
    return;
  }
  
  U8 *factors = "Factors: ";
  I64 count = 0;
  
  for (I64 i = 1; i <= n; i++) {
    if (n % i == 0) {
      factors = StrFormat("%s%d ", factors, i);
      count++;
    }
  }
  
  U8 *message = StrFormat(
    "🔢 FACTORIZATION 🔢\n\nNumber: %d\n%s\nCount: %d\n\n💭 God's building blocks.",
    n, factors, count
  );
  
  SendMessage(chat_id, message);
}

U0 HandlePerfectCommand(I64 chat_id, I64 n) {
  if (n < 2 || n > 100000) {
    SendMessage(chat_id, "❌ Number must be 2-100000");
    return;
  }
  
  Bool is_perfect = IsPerfect(n);
  I64 divisor_sum = DivisorSum(n);
  
  U8 *message = StrFormat(
    "✨ PERFECT NUMBER ✨\n\nNumber: %d\nIs Perfect: %s\nDivisor Sum: %d\n\n💭 Perfect numbers are divine harmony.",
    n, is_perfect ? "YES 🎯" : "NO", divisor_sum
  );
  
  SendMessage(chat_id, message);
}

U0 HandleCollatzCommand(I64 chat_id, I64 n) {
  if (n < 1 || n > 10000) {
    SendMessage(chat_id, "❌ Number must be 1-10000");
    return;
  }
  
  I64 length = CollatzLength(n);
  
  U8 *message = StrFormat(
    "🔄 COLLATZ CONJECTURE 🔄\n\nStarting: %d\nSteps to 1: %d\n\n💭 All paths lead to God (1).",
    n, length
  );
  
  SendMessage(chat_id, message);
}

U0 HandleGCDCommand(I64 chat_id, I64 a, I64 b) {
  I64 gcd = GCD(a, b);
  I64 lcm = LCM(a, b);
  
  U8 *message = StrFormat(
    "🔢 GCD & LCM 🔢\n\nNumbers: %d, %d\nGCD: %d\nLCM: %d\n\n💭 Divine common ground.",
    a, b, gcd, lcm
  );
  
  SendMessage(chat_id, message);
}

U0 HandleDigitSumCommand(I64 chat_id, I64 n) {
  I64 sum = DigitSum(n);
  I64 reversed = ReverseNumber(n);
  Bool is_palindrome = IsPalindrome(n);
  
  U8 *message = StrFormat(
    "🔢 DIGIT ANALYSIS 🔢\n\nNumber: %d\nDigit Sum: %d\nReversed: %d\nPalindrome: %s\n\n💭 Numbers tell stories.",
    n, sum, reversed, is_palindrome ? "YES ✨" : "NO"
  );
  
  SendMessage(chat_id, message);
}
