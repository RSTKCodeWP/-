// Divine Games Plugin
// Commands: /dice, /coin, /rps <choice>
// Terry loved random numbers - games with divine randomness

U0 HandleDiceCommand(I64 chat_id) {
  I64 roll = (GetDivineNumber() % 6) + 1;
  
  U8 *dice_art[] = {
    "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"
  };
  
  U8 *message = StrFormat(
    "🎲 DIVINE DICE ROLL 🎲\n\n%s\n\nYou rolled: %d\n\n💭 Random numbers are God's voice.",
    dice_art[roll - 1], roll
  );
  
  SendMessage(chat_id, message);
}

U0 HandleCoinCommand(I64 chat_id) {
  I64 flip = GetDivineNumber() % 2;
  
  U8 *result = flip == 0 ? "🪙 HEADS" : "🪙 TAILS";
  
  U8 *message = StrFormat(
    "🪙 DIVINE COIN FLIP 🪙\n\n%s\n\n💭 Let God decide.",
    result
  );
  
  SendMessage(chat_id, message);
}

U0 HandleRPSCommand(I64 chat_id, U8 *user_choice) {
  // Rock Paper Scissors
  U8 *choices[] = {"rock", "paper", "scissors"};
  U8 *emojis[] = {"🪨", "📄", "✂️"};
  
  I64 bot_choice = GetDivineNumber() % 3;
  I64 user_idx = -1;
  
  // Parse user choice
  if (StrCmp(user_choice, "rock") == 0) user_idx = 0;
  else if (StrCmp(user_choice, "paper") == 0) user_idx = 1;
  else if (StrCmp(user_choice, "scissors") == 0) user_idx = 2;
  
  if (user_idx == -1) {
    SendMessage(chat_id, "❌ Invalid choice! Use: rock, paper, or scissors");
    return;
  }
  
  U8 *outcome;
  if (user_idx == bot_choice) {
    outcome = "🤝 TIE! God's balance.";
  } else if ((user_idx == 0 && bot_choice == 2) ||
             (user_idx == 1 && bot_choice == 0) ||
             (user_idx == 2 && bot_choice == 1)) {
    outcome = "🎉 YOU WIN! Divine favor.";
  } else {
    outcome = "😇 I WIN! God's will.";
  }
  
  U8 *message = StrFormat(
    "✊📄✂️ ROCK PAPER SCISSORS ✊📄✂️\n\nYou: %s %s\nBot: %s %s\n\n%s\n\n💭 Terry would play this.",
    emojis[user_idx], choices[user_idx],
    emojis[bot_choice], choices[bot_choice],
    outcome
  );
  
  SendMessage(chat_id, message);
}
