// Telegram Bot in HolyC   
// This bot responds to the /start command   
   
U0 HandleStartCommand(I64 chat_id) {   
  I64 message = "Hello! Welcome to the HolyC Telegram Bot. This bot is written in HolyC!";   
  Print("Sending message to chat %%%d: %%%s\\n", chat_id, message);   
}   
   
U0 ProcessMessage(I64 chat_id, I64 text) {   
    HandleStartCommand(chat_id);   
  } else {   
    Print("Received message: %%%s\\n", text);   
  }   
}   
   
U0 TelegramBotMain() {   
  Print("Starting Telegram Bot...\\n");   
  Print("Bot is running. Send /start to get a response.\\n");   
   
  // Simulate receiving a /start command   
  ProcessMessage(123456789, "/start");   
}   
   
// Entry point   
U0 main() {   
  TelegramBotMain();   
}  
