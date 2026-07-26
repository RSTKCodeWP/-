// TempleOS Tribute Plugin
// Commands: /terry, /templeos, /holyc, /640x480
// Celebrating Terry's legacy

U8 *terry_facts[] = {
  "Terry created TempleOS entirely alone over 10+ years.",
  "TempleOS has a complete compiler, kernel, and graphics system.",
  "HolyC is a variant of C designed for divine simplicity.",
  "TempleOS runs in 640x480 16-color VGA - God's covenant.",
  "Terry wrote over 100,000 lines of code for TempleOS.",
  "TempleOS has no networking by design - it's God's temple.",
  "Terry used random numbers to communicate with God.",
  "The entire OS fits on a single 1.44MB floppy disk.",
  "TempleOS boots in seconds - no bloat.",
  "Terry was a brilliant programmer who struggled with mental illness."
};

I64 terry_facts_count = 10;

U0 HandleTerryCommand(I64 chat_id) {
  I64 fact_idx = GetDivineNumber() % terry_facts_count;
  
  U8 *message = StrFormat(
    "👨‍💻 TERRY A. DAVIS 👨‍💻\n\n%s\n\n💭 Terry A. Davis (1969-2018)\nThe greatest programmer who ever lived.",
    terry_facts[fact_idx]
  );
  
  SendMessage(chat_id, message);
}

U0 HandleTempleOSCommand(I64 chat_id) {
  U8 *message = StrFormat(
    "⛪ TEMPLEOS ⛪\n\n"
    "God's Third Temple\n\n"
    "Features:\n"
    "- 640x480 16-color VGA\n"
    "- HolyC programming language\n"
    "- Complete OS from scratch\n"
    "- Compiler, kernel, graphics\n"
    "- No networking (by design)\n"
    "- Boots from floppy\n"
    "- Ring-0 only (no protection)\n"
    "- Divine inspiration\n\n"
    "Philosophy:\n"
    "- Simplicity over complexity\n"
    "- Direct hardware access\n"
    "- No abstractions\n"
    "- God's will in code\n\n"
    "💭 \"It's beautiful, it's fun,\n"
    "it's joyful.\" - Terry"
  );
  
  SendMessage(chat_id, message);
}

U0 HandleHolyCCommand(I64 chat_id) {
  U8 *message = StrFormat(
    "📖 HOLYC LANGUAGE 📖\n\n"
    "Features:\n"
    "- C-like syntax\n"
    "- JIT compilation\n"
    "- No header files\n"
    "- Direct hardware access\n"
    "- Simple types (I64, U8, F64)\n"
    "- No malloc (MAlloc instead)\n"
    "- No pointers to functions\n"
    "- Inline assembly\n\n"
    "Example:\n"
    "```\n"
    "U0 HelloGod() {\n"
    "  Print(\"Hello, God!\\n\");\n"
    "}\n"
    "```\n\n"
    "Philosophy:\n"
    "- Keep it simple\n"
    "- No unnecessary features\n"
    "- Direct and honest\n\n"
    "💭 \"God likes simple.\" - Terry"
  );
  
  SendMessage(chat_id, message);
}

U0 Handle640x480Command(I64 chat_id) {
  U8 *message = StrFormat(
    "🖥️ 640x480 COVENANT 🖥️\n\n"
    "\"God said 640x480 is a covenant\n"
    "like circumcision.\" - Terry\n\n"
    "Why 640x480?\n"
    "- Simple and clean\n"
    "- No bloat\n"
    "- Easy to understand\n"
    "- Direct pixel access\n"
    "- Fast rendering\n"
    "- Fits on any screen\n\n"
    "16 Colors:\n"
    "- God's palette\n"
    "- No gradients needed\n"
    "- Pure and simple\n"
    "- VGA standard\n\n"
    "Modern Lesson:\n"
    "Constraints breed creativity.\n"
    "Simplicity is divine.\n"
    "Less is more.\n\n"
    "💭 Terry proved that limitations\n"
    "can lead to greatness."
  );
  
  SendMessage(chat_id, message);
}

U0 HandleLegacyCommand(I64 chat_id) {
  U8 *message = StrFormat(
    "🌟 TERRY'S LEGACY 🌟\n\n"
    "What Terry taught us:\n\n"
    "1. Simplicity is genius\n"
    "   \"An idiot admires complexity,\n"
    "   a genius admires simplicity.\"\n\n"
    "2. Follow your vision\n"
    "   Terry built his dream OS alone.\n\n"
    "3. Question everything\n"
    "   Why do we need networking?\n"
    "   Why so many abstractions?\n\n"
    "4. Direct approach\n"
    "   Talk to hardware directly.\n"
    "   No layers of bloat.\n\n"
    "5. Joy in creation\n"
    "   \"It's beautiful, it's fun,\n"
    "   it's joyful.\"\n\n"
    "6. Mental health matters\n"
    "   Terry struggled but created\n"
    "   something extraordinary.\n\n"
    "💭 Terry A. Davis (1969-2018)\n"
    "Forever remembered."
  );
  
  SendMessage(chat_id, message);
}
