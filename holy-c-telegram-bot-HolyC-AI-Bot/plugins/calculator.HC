// Divine Calculator Plugin
// Command: /calc <expression>
// Terry's simple math with divine precision

U0 HandleCalcCommand(I64 chat_id, U8 *expression) {
  // Parse simple expressions: "5+3", "10*2", "100/5", "20-7"
  I64 num1 = 0, num2 = 0;
  U8 operator = 0;
  I64 result = 0;
  
  // Simple parser
  I64 i = 0;
  while (expression[i] >= '0' && expression[i] <= '9') {
    num1 = num1 * 10 + (expression[i] - '0');
    i++;
  }
  
  operator = expression[i];
  i++;
  
  while (expression[i] >= '0' && expression[i] <= '9') {
    num2 = num2 * 10 + (expression[i] - '0');
    i++;
  }
  
  // Calculate
  if (operator == '+') {
    result = num1 + num2;
  } else if (operator == '-') {
    result = num1 - num2;
  } else if (operator == '*') {
    result = num1 * num2;
  } else if (operator == '/') {
    if (num2 != 0) {
      result = num1 / num2;
    } else {
      SendMessage(chat_id, "❌ Division by zero! God doesn't divide by zero.");
      return;
    }
  } else {
    SendMessage(chat_id, "❌ Invalid operator. Use: +, -, *, /");
    return;
  }
  
  U8 *message = StrFormat(
    "🔢 DIVINE CALCULATION 🔢\n\n%d %c %d = %d\n\n💭 Simple math, as Terry intended.",
    num1, operator, num2, result
  );
  
  SendMessage(chat_id, message);
}
