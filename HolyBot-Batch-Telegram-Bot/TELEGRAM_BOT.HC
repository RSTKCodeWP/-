// Simple Telegram Bot in HolyC 
U0 HandleStartCommand(I64 chat_id) { 
  I64 message; 
  message = "Hello! Welcome to the HolyC Telegram Bot. This bot is written in HolyC!"; 
  // In a real implementation, you would call the Telegram API to send this message 
  Print("Sending message to chat %d: %s\\n", chat_id, message); 
} 
ECHO is on.
U0 ProcessMessage(I64 chat_id, I64 text) { 
