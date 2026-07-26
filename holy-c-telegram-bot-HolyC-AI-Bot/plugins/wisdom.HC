// Divine Wisdom Plugin
// Command: /wisdom, /proverb
// Terry's philosophy and programming wisdom

U8 *programming_wisdom[] = {
  "Write code for humans, not machines.",
  "Premature optimization is the root of all evil.",
  "Code is read more than written.",
  "Simplicity is the ultimate sophistication.",
  "Make it work, make it right, make it fast.",
  "Don't repeat yourself (DRY).",
  "Explicit is better than implicit.",
  "Errors should never pass silently.",
  "In the face of ambiguity, refuse the temptation to guess.",
  "There should be one obvious way to do it."
};

I64 programming_wisdom_count = 10;

U8 *life_proverbs[] = {
  "The journey of a thousand miles begins with a single step.",
  "Fall seven times, stand up eight.",
  "What we think, we become.",
  "The only way to do great work is to love what you do.",
  "Be the change you wish to see in the world.",
  "In the middle of difficulty lies opportunity.",
  "Life is 10% what happens to you and 90% how you react.",
  "The best time to plant a tree was 20 years ago. The second best time is now.",
  "Do not go where the path may lead, go instead where there is no path.",
  "The only impossible journey is the one you never begin."
};

I64 life_proverbs_count = 10;

U0 HandleWisdomCommand(I64 chat_id) {
  I64 wisdom_idx = GetDivineNumber() % programming_wisdom_count;
  
  U8 *message = StrFormat(
    "💡 PROGRAMMING WISDOM 💡\n\n\"%s\"\n\n💭 Terry lived by these principles.",
    programming_wisdom[wisdom_idx]
  );
  
  SendMessage(chat_id, message);
}

U0 HandleProverbCommand(I64 chat_id) {
  I64 proverb_idx = GetDivineNumber() % life_proverbs_count;
  
  U8 *message = StrFormat(
    "🌟 LIFE PROVERB 🌟\n\n\"%s\"\n\n💭 Divine guidance for life.",
    life_proverbs[proverb_idx]
  );
  
  SendMessage(chat_id, message);
}
