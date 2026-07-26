# HolyC Telegram Bot  
  
This is a simple Telegram bot implementation written in HolyC for TempleOS.  
  
## Features 
  
- Responds to the /start command with a welcome message  
- Processes other messages with a generic response  
  
## Code  
  
The main bot code is as follows: 
  
// Telegram Bot in HolyC  
// This bot responds to the /start command  
  
U0 HandleStartCommand(I64 chat_id) {  
  I64 message = "Hello! Welcome to the HolyC Telegram Bot. This bot is written in HolyC!";  
  Print("Sending message to chat %%d: %%s\\n", chat_id, message);  
} 
  
U0 ProcessMessage(I64 chat_id, I64 text) {  
