// Divine Mathematics Library
// Pure HolyC mathematical functions
// Terry loved math - God's language

// Absolute value
I64 Abs(I64 n) {
  return n < 0 ? -n : n;
}

// Power function
I64 Pow(I64 base, I64 exp) {
  if (exp == 0) return 1;
  I64 result = 1;
  for (I64 i = 0; i < exp; i++) {
    result *= base;
  }
  return result;
}

// Square root (integer)
I64 Sqrt(I64 n) {
  if (n < 0) return -1;
  if (n == 0) return 0;
  
  I64 x = n;
  I64 y = (x + 1) / 2;
  
  while (y < x) {
    x = y;
    y = (x + n / x) / 2;
  }
  
  return x;
}

// Greatest Common Divisor
I64 GCD(I64 a, I64 b) {
  a = Abs(a);
  b = Abs(b);
  
  while (b != 0) {
    I64 temp = b;
    b = a % b;
    a = temp;
  }
  
  return a;
}

// Least Common Multiple
I64 LCM(I64 a, I64 b) {
  return Abs(a * b) / GCD(a, b);
}

// Check if prime
Bool IsPrime(I64 n) {
  if (n <= 1) return FALSE;
  if (n <= 3) return TRUE;
  if (n % 2 == 0 || n % 3 == 0) return FALSE;
  
  I64 i = 5;
  while (i * i <= n) {
    if (n % i == 0 || n % (i + 2) == 0)
      return FALSE;
    i += 6;
  }
  return TRUE;
}

// Next prime after n
I64 NextPrime(I64 n) {
  if (n < 2) return 2;
  
  I64 candidate = n + 1;
  while (!IsPrime(candidate)) {
    candidate++;
  }
  
  return candidate;
}

// Factorial
I64 Factorial(I64 n) {
  if (n < 0) return -1;
  if (n <= 1) return 1;
  
  I64 result = 1;
  for (I64 i = 2; i <= n; i++) {
    result *= i;
  }
  return result;
}

// Fibonacci
I64 Fibonacci(I64 n) {
  if (n < 0) return -1;
  if (n <= 1) return n;
  
  I64 a = 0, b = 1;
  for (I64 i = 2; i <= n; i++) {
    I64 temp = a + b;
    a = b;
    b = temp;
  }
  
  return b;
}

// Sum of digits
I64 DigitSum(I64 n) {
  n = Abs(n);
  I64 sum = 0;
  
  while (n > 0) {
    sum += n % 10;
    n /= 10;
  }
  
  return sum;
}

// Reverse number
I64 ReverseNumber(I64 n) {
  I64 sign = n < 0 ? -1 : 1;
  n = Abs(n);
  
  I64 result = 0;
  while (n > 0) {
    result = result * 10 + (n % 10);
    n /= 10;
  }
  
  return result * sign;
}

// Check if palindrome
Bool IsPalindrome(I64 n) {
  return n == ReverseNumber(n);
}

// Collatz sequence length
I64 CollatzLength(I64 n) {
  if (n <= 0) return -1;
  
  I64 length = 0;
  while (n != 1) {
    if (n % 2 == 0) {
      n = n / 2;
    } else {
      n = 3 * n + 1;
    }
    length++;
  }
  
  return length;
}

// Perfect number check
Bool IsPerfect(I64 n) {
  if (n <= 1) return FALSE;
  
  I64 sum = 1;
  for (I64 i = 2; i * i <= n; i++) {
    if (n % i == 0) {
      sum += i;
      if (i * i != n) {
        sum += n / i;
      }
    }
  }
  
  return sum == n;
}

// Sum of divisors
I64 DivisorSum(I64 n) {
  if (n <= 0) return 0;
  
  I64 sum = 0;
  for (I64 i = 1; i <= n; i++) {
    if (n % i == 0) {
      sum += i;
    }
  }
  
  return sum;
}

// Divine random in range
I64 RandomRange(I64 min, I64 max) {
  if (min >= max) return min;
  return min + (GetDivineNumber() % (max - min + 1));
}

// Clamp value
I64 Clamp(I64 value, I64 min, I64 max) {
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

// Linear interpolation
I64 Lerp(I64 a, I64 b, I64 t) {
  // t should be 0-100 (percentage)
  return a + (b - a) * t / 100;
}
