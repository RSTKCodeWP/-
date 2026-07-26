// Divine Growth Game Plugin
// Commands: /grow, /growtop
// Terry's random game with divine measurements
// God's will determines growth through random oracle

// Game state stored in database via bridge
// Format: user_id -> size,last_grow_timestamp

U0 HandleGrowCommand(I64 chat_id, I64 user_id, U8 *username) {
  // Get current size and last grow time from database
  U8 *game_data = LoadGameData(user_id);
  
  I64 current_size = 0;
  I64 last_grow = 0;
  
  if (StrLen(game_data) > 0) {
    // Parse "size,timestamp"
    I64 comma_pos = StrFind(game_data, ",");
    if (comma_pos > 0) {
      U8 *size_str = StrSubstr(game_data, 0, comma_pos);
      U8 *time_str = StrSubstr(game_data, comma_pos + 1, StrLen(game_data));
      current_size = StrToI64(size_str);
      last_grow = StrToI64(time_str);
    }
  }
  
  // Check cooldown (24 hours = 86400 seconds)
  I64 current_time = GetCurrentTime();
  I64 time_diff = current_time - last_grow;
  I64 cooldown = 86400; // 24 hours
  
  if (time_diff < cooldown && last_grow > 0) {
    I64 remaining = cooldown - time_diff;
    I64 hours = remaining / 3600;
    I64 minutes = (remaining % 3600) / 60;
    
    U8 *message = StrFormat(
      "⏰ DIVINE COOLDOWN ⏰\n\n"
      "Current size: %d cm\n\n"
      "Next attempt in %d h. %d min.\n\n"
      "💭 Patience is a divine virtue.",
      current_size, hours, minutes
    );
    
    SendMessage(chat_id, message);
    return;
  }
  
  // Divine growth calculation using Terry's random oracle
  I64 growth = RandomRange(1, 30);
  
  // 5% chance for divine blessing (double growth)
  if (GetDivineNumber() % 100 < 5) {
    growth *= 2;
  }
  
  // 2% chance for divine curse (negative growth)
  if (GetDivineNumber() % 100 < 2) {
    growth = -RandomRange(1, 15);
  }
  
  current_size += growth;
  if (current_size < 0) current_size = 0;
  
  // Save new data
  U8 *new_data = StrFormat("%d,%d", current_size, current_time);
  SaveGameData(user_id, username, new_data);
  
  // Get rank
  I64 rank = GetUserRank(user_id);
  
  // Build message
  U8 *growth_text;
  if (growth > 0) {
    if (growth > 20) {
      growth_text = StrFormat("🎉 DIVINE BLESSING! Grew by %d cm!!", growth);
    } else {
      growth_text = StrFormat("✨ Grew by %d cm!", growth);
    }
  } else {
    growth_text = StrFormat("😱 DIVINE CURSE! Shrunk by %d cm!", -growth);
  }
  
  U8 *message = StrFormat(
    "🍆 DIVINE GROWTH GAME 🍆\n\n"
    "%s\n\n"
    "Current size: %d cm\n"
    "You rank #%d in the leaderboard.\n\n"
    "Next attempt in 24 h.\n\n"
    "💭 Randomness is God's voice.",
    growth_text, current_size, rank
  );
  
  SendMessage(chat_id, message);
}

U0 HandleGrowTopCommand(I64 chat_id, I64 page) {
  // Get top players from database
  U8 *top_data = GetTopPlayers(page);
  
  if (StrLen(top_data) == 0) {
    SendMessage(chat_id, "❌ No data. Use /grow to start!");
    return;
  }
  
  U8 *message = StrFormat(
    "🏆 DIVINE GROWTH LEADERBOARD 🏆\n\n%s\n\n💭 Size doesn't matter, God's will does!",
    top_data
  );
  
  // Send with inline keyboard for pagination
  SendMessageWithKeyboard(chat_id, message, page);
}

// Helper to check if user can grow
Bool CanUserGrow(I64 user_id) {
  U8 *game_data = LoadGameData(user_id);
  
  if (StrLen(game_data) == 0) return TRUE;
  
  I64 comma_pos = StrFind(game_data, ",");
  if (comma_pos <= 0) return TRUE;
  
  U8 *time_str = StrSubstr(game_data, comma_pos + 1, StrLen(game_data));
  I64 last_grow = StrToI64(time_str);
  
  I64 current_time = GetCurrentTime();
  I64 time_diff = current_time - last_grow;
  
  return time_diff >= 86400;
}
