// Divine Astronomy Plugin
// Command: /cosmos, /planet <name>
// Terry looked at the stars - God's creation

U8 *planet_data[][3] = {
  {"Mercury", "☿️", "Closest to the Sun. God's messenger."},
  {"Venus", "♀️", "Brightest planet. Morning star."},
  {"Earth", "🌍", "Our home. God's temple."},
  {"Mars", "♂️", "Red planet. God's warrior."},
  {"Jupiter", "♃", "Largest planet. King of planets."},
  {"Saturn", "♄", "Ringed beauty. God's jewel."},
  {"Uranus", "♅", "Ice giant. Tilted by divine will."},
  {"Neptune", "♆", "Blue giant. God's ocean."}
};

I64 planet_count = 8;

U0 HandleCosmosCommand(I64 chat_id) {
  I64 fact_type = GetDivineNumber() % 5;
  
  U8 *facts[] = {
    "🌌 The universe is 13.8 billion years old.\nGod's eternal creation.",
    "⭐ There are more stars than grains of sand on Earth.\nGod's infinite design.",
    "🌙 The Moon is moving away from Earth 3.8cm per year.\nGod's slow dance.",
    "☀️ The Sun is 109 times wider than Earth.\nGod's power source.",
    "🪐 Saturn's rings are made of ice and rock.\nGod's cosmic art."
  };
  
  U8 *message = StrFormat(
    "🌌 DIVINE COSMOS 🌌\n\n%s\n\n💭 Terry gazed at God's creation.",
    facts[fact_type]
  );
  
  SendMessage(chat_id, message);
}

U0 HandlePlanetCommand(I64 chat_id, U8 *planet_name) {
  I64 found = -1;
  
  // Find planet
  for (I64 i = 0; i < planet_count; i++) {
    if (StrICmp(planet_name, planet_data[i][0]) == 0) {
      found = i;
      break;
    }
  }
  
  if (found == -1) {
    SendMessage(chat_id, "❌ Planet not found. Try: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune");
    return;
  }
  
  U8 *message = StrFormat(
    "🪐 PLANET INFO 🪐\n\n%s %s\n\n%s\n\n💭 God's solar system.",
    planet_data[found][1], planet_data[found][0], planet_data[found][2]
  );
  
  SendMessage(chat_id, message);
}
