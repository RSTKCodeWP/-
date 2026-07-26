// Divine Fun Plugin
// Commands: /joke, /riddle, /fact, /compliment
// Terry had humor - God's gift

U8 *programming_jokes[] = {
  "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
  "A SQL query walks into a bar, walks up to two tables and asks: 'Can I JOIN you?' 🍺",
  "Why do Java developers wear glasses? Because they can't C#! 👓",
  "How many programmers does it take to change a light bulb? None, that's a hardware problem! 💡",
  "Why did the programmer quit his job? Because he didn't get arrays! 📊",
  "What's a programmer's favorite hangout place? Foo Bar! 🍻",
  "Why do programmers always mix up Halloween and Christmas? Because Oct 31 == Dec 25! 🎃🎄",
  "A programmer's wife tells him: 'Go to the store and buy a loaf of bread. If they have eggs, buy a dozen.' He returns with 12 loaves of bread. 🍞",
  "Why did the developer go broke? Because he used up all his cache! 💰",
  "What do you call a programmer from Finland? Nerdic! 🇫🇮"
};

I64 programming_jokes_count = 10;

U8 *riddles[] = {
  "I speak without a mouth and hear without ears. I have no body, but come alive with wind. What am I? (Echo) 🔊",
  "The more you take, the more you leave behind. What am I? (Footsteps) 👣",
  "What has keys but no locks, space but no room, and you can enter but can't go inside? (Keyboard) ⌨️",
  "I'm tall when I'm young, and short when I'm old. What am I? (Candle) 🕯️",
  "What has hands but cannot clap? (Clock) ⏰",
  "What gets wetter the more it dries? (Towel) 🧻",
  "What can travel around the world while staying in a corner? (Stamp) 📮",
  "What has a head and tail but no body? (Coin) 🪙",
  "What runs but never walks, has a mouth but never talks? (River) 🌊",
  "What can you catch but not throw? (Cold) 🤧"
};

I64 riddles_count = 10;

U8 *tech_facts[] = {
  "The first computer bug was an actual bug - a moth found in a Harvard Mark II computer in 1947! 🦋",
  "The first 1GB hard drive weighed over 500 pounds and cost $40,000 in 1980! 💾",
  "The first computer mouse was made of wood! 🖱️",
  "CAPTCHA stands for 'Completely Automated Public Turing test to tell Computers and Humans Apart' 🤖",
  "The first domain ever registered was Symbolics.com on March 15, 1985! 🌐",
  "Email existed before the World Wide Web! 📧",
  "The first webcam was created to monitor a coffee pot at Cambridge University! ☕",
  "The average person blinks 15-20 times per minute, but only 7 times per minute when using a computer! 👁️",
  "The first computer programmer was Ada Lovelace in the 1840s! 👩‍💻",
  "There are more possible iterations of a game of chess than atoms in the observable universe! ♟️"
};

I64 tech_facts_count = 10;

U8 *compliments[] = {
  "Your code is as elegant as Terry's TempleOS! ✨",
  "You debug like a divine oracle! 🔮",
  "Your algorithms are blessed by God! 🙏",
  "You write code that even Terry would admire! 💻",
  "Your logic is as pure as HolyC! ⛪",
  "You're a programming genius in the making! 🧠",
  "Your dedication to simplicity is divine! 🌟",
  "You understand that less is more - Terry's way! 📐",
  "Your code speaks the language of God! 📖",
  "You're on the path to programming enlightenment! 🛤️"
};

I64 compliments_count = 10;

U0 HandleJokeCommand(I64 chat_id) {
  I64 joke_idx = GetDivineNumber() % programming_jokes_count;
  
  U8 *message = StrFormat(
    "😄 DIVINE JOKE 😄\n\n%s\n\n💭 Terry had a sense of humor too!",
    programming_jokes[joke_idx]
  );
  
  SendMessage(chat_id, message);
}

U0 HandleRiddleCommand(I64 chat_id) {
  I64 riddle_idx = GetDivineNumber() % riddles_count;
  
  U8 *message = StrFormat(
    "🤔 DIVINE RIDDLE 🤔\n\n%s\n\n💭 Exercise your divine mind!",
    riddles[riddle_idx]
  );
  
  SendMessage(chat_id, message);
}

U0 HandleFactCommand(I64 chat_id) {
  I64 fact_idx = GetDivineNumber() % tech_facts_count;
  
  U8 *message = StrFormat(
    "💡 TECH FACT 💡\n\n%s\n\n💭 Knowledge is divine!",
    tech_facts[fact_idx]
  );
  
  SendMessage(chat_id, message);
}

U0 HandleComplimentCommand(I64 chat_id) {
  I64 comp_idx = GetDivineNumber() % compliments_count;
  
  U8 *message = StrFormat(
    "💝 DIVINE COMPLIMENT 💝\n\n%s\n\n💭 You deserve it!",
    compliments[comp_idx]
  );
  
  SendMessage(chat_id, message);
}

U0 Handle8BallCommand(I64 chat_id, U8 *question) {
  U8 *answers[] = {
    "🎱 It is certain.",
    "🎱 Without a doubt.",
    "🎱 Yes, definitely.",
    "🎱 You may rely on it.",
    "🎱 As I see it, yes.",
    "🎱 Most likely.",
    "🎱 Outlook good.",
    "🎱 Signs point to yes.",
    "🎱 Reply hazy, try again.",
    "🎱 Ask again later.",
    "🎱 Better not tell you now.",
    "🎱 Cannot predict now.",
    "🎱 Concentrate and ask again.",
    "🎱 Don't count on it.",
    "🎱 My reply is no.",
    "🎱 My sources say no.",
    "🎱 Outlook not so good.",
    "🎱 Very doubtful."
  };
  
  I64 answer_idx = GetDivineNumber() % 18;
  
  U8 *message = StrFormat(
    "🎱 MAGIC 8-BALL 🎱\n\nQuestion: %s\n\nAnswer: %s\n\n💭 Divine wisdom from the oracle!",
    question, answers[answer_idx]
  );
  
  SendMessage(chat_id, message);
}
