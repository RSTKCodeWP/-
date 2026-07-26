// System Information Plugin
// Commands: /sysinfo, /uptime, /version
// Terry's system awareness

U0 HandleSysInfoCommand(I64 chat_id) {
  U8 *message = StrFormat(
    "💻 SYSTEM INFO 💻\n\n"
    "Bot: HolyC Telegram Bot\n"
    "Language: Pure HolyC\n"
    "Bridge: C++/Python\n"
    "AI: Ollama\n"
    "Database: SQLite\n"
    "Memory: RAG + Embeddings\n"
    "Plugins: 13 modules\n"
    "Libraries: 6 modules\n"
    "Commands: 50+\n\n"
    "💭 Built with Terry's principles:\n"
    "- Simplicity\n"
    "- Divine inspiration\n"
    "- 640x480 mindset\n"
    "- No bloat"
  );
  
  SendMessage(chat_id, message);
}

U0 HandleVersionCommand(I64 chat_id) {
  U8 *message = StrFormat(
    "📦 VERSION INFO 📦\n\n"
    "HolyC Bot v2.0\n"
    "Release: Divine Edition\n\n"
    "Components:\n"
    "- HolyC Core: 2155 lines\n"
    "- Plugins: 11 modules\n"
    "- Libraries: 6 modules\n"
    "- Bridge: C++/Python\n\n"
    "Features:\n"
    "✅ AI Chat (Ollama)\n"
    "✅ RAG Memory\n"
    "✅ 50+ Commands\n"
    "✅ Games & Fun\n"
    "✅ Math & Crypto\n"
    "✅ Text Processing\n\n"
    "💭 In memory of Terry A. Davis\n"
    "\"An idiot admires complexity,\n"
    "a genius admires simplicity.\""
  );
  
  SendMessage(chat_id, message);
}

U0 HandlePluginsCommand(I64 chat_id) {
  U8 *message = StrFormat(
    "🔌 INSTALLED PLUGINS 🔌\n\n"
    "1. oracle.HC - Divine oracle\n"
    "2. weather.HC - Weather predictions\n"
    "3. astronomy.HC - Cosmos & planets\n"
    "4. wisdom.HC - Quotes & proverbs\n"
    "5. games.HC - Dice, coin, RPS\n"
    "6. calculator.HC - Math operations\n"
    "7. time.HC - Time utilities\n"
    "8. crypto.HC - Cryptography\n"
    "9. text.HC - Text processing\n"
    "10. number.HC - Number theory\n"
    "11. fun.HC - Jokes & riddles\n"
    "12. advanced_math.HC - Statistics\n"
    "13. system.HC - System info\n\n"
    "💭 Modular design, Terry's way."
  );
  
  SendMessage(chat_id, message);
}

U0 HandleLibrariesCommand(I64 chat_id) {
  U8 *message = StrFormat(
    "📚 CORE LIBRARIES 📚\n\n"
    "1. string_utils.HC\n"
    "   - String manipulation\n"
    "   - 15+ functions\n\n"
    "2. math_divine.HC\n"
    "   - Mathematical operations\n"
    "   - Prime, Fibonacci, GCD\n\n"
    "3. crypto_holy.HC\n"
    "   - Cryptography primitives\n"
    "   - Hash, cipher, encoding\n\n"
    "4. json_parser.HC\n"
    "   - JSON parsing\n"
    "   - Get, array, escape\n\n"
    "5. http_client.HC\n"
    "   - HTTP interface\n"
    "   - Request/response\n\n"
    "6. bridge_interface.HC\n"
    "   - Bridge definitions\n"
    "   - Function signatures\n\n"
    "💭 Reusable, simple, divine."
  );
  
  SendMessage(chat_id, message);
}
