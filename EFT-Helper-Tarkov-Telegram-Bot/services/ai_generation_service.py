"""AI-powered build generation service using Qwen3-Coder-480B-Cloud via Ollama."""
import logging
import json
import re
from typing import Dict, List, Optional, Tuple
from api_clients import TarkovAPIClient
from database import Database
from .context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class AIGenerationService:
    """Service for AI-powered weapon build generation using Ollama."""
    
    # Tier definitions for build quality
    TIER_DISTRIBUTION = {
        "S": 0.10,  # 10% - Top tier, expensive
        "A": 0.20,  # 20% - Excellent quality
        "B": 0.40,  # 40% - Good, balanced
        "C": 0.20,  # 20% - Budget-friendly
        "D": 0.10   # 10% - Experimental/weak
    }
    
    def __init__(
        self, 
        api_client: TarkovAPIClient,
        db: Database,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3-coder:480b-cloud"
    ):
        self.api = api_client
        self.db = db
        self.context_builder = ContextBuilder(api_client, db)
        self.ollama_url = ollama_url
        self.model = ollama_model
    
    async def generate_build_with_ai(
        self,
        intent: str,
        context: Dict,
        user_id: int,
        language: str = "ru"
    ) -> Optional[Dict]:
        """
        Unified AI build generation based on intent.
        
        Args:
            intent: Type of generation ("random_build", "meta_build", "quest_build", "custom_request")
            context: Context dictionary with weapon_id, budget, loyalty, tier, quest_name, etc.
            user_id: User ID for preferences
            language: Response language
            
        Returns:
            Dict with build data including tier
        """
        try:
            # Build context string based on intent
            context_str = await self._build_context_for_intent(intent, context, user_id, language)
            
            # Create prompt based on intent
            prompt = self._create_prompt_for_intent(intent, context, context_str, language)
            
            # Call Ollama
            response = await self._call_ollama(prompt)
            
            if not response:
                return None
            
            # Parse response and extract tier
            build_data = self._parse_build_response(response, language)
            build_data["intent"] = intent
            build_data["tier"] = self._extract_tier_from_response(response, context.get("target_tier"))
            
            return build_data
            
        except Exception as e:
            logger.error(f"Error in AI build generation: {e}", exc_info=True)
            return None
    
    async def generate_build(
        self, 
        user_request: str, 
        user_id: int, 
        language: str = "ru"
    ) -> Optional[Dict]:
        """
        Legacy method - converts user request to intent and calls generate_build_with_ai.
        Kept for backward compatibility.
            
        Returns:
            Dict with build information or None if generation failed
        """
        try:
            # Parse user intent
            intent = await self._parse_intent(user_request, language)
            
            # Build context
            context = await self._build_generation_context(intent, user_id, language)
            
            # Generate build via LLM
            prompt = self._create_build_prompt(user_request, context, language)
            
            response = await self._call_ollama(prompt)
            if not response:
                logger.warning("No response from Ollama")
                return None
            
            # Parse response into structured build
            build_data = self._parse_build_response(response, language)
            
            return build_data
            
        except Exception as e:
            logger.error(f"Error generating build: {e}", exc_info=True)
            return None
    
    async def generate_quest_build(
        self,
        quest_name: str,
        user_id: int,
        language: str = "ru"
    ) -> Optional[Dict]:
        """
        Generate build specifically for a quest using exact tarkov.dev requirements.
        
        Args:
            quest_name: Name of the quest
            user_id: Telegram user ID
            language: User's language (ru/en)
            
        Returns:
            Dict with build information or None if generation failed
        """
        try:
            # Get quest details from API with exact requirements
            quests = await self.api.get_weapon_build_tasks(lang=language)
            quest_data = None
            for q in quests:
                if quest_name.lower() in q.get("name", "").lower():
                    quest_data = q
                    break
            
            if not quest_data:
                logger.warning(f"Quest '{quest_name}' not found in API")
                return None
            
            # Extract buildWeapon objective with required items
            objectives = quest_data.get("objectives", [])
            build_obj = None
            for obj in objectives:
                if obj.get("type") == "buildWeapon":
                    build_obj = obj
                    break
            
            if not build_obj:
                logger.warning(f"No buildWeapon objective in quest '{quest_name}'")
                return None
            
            # Build context with quest requirements
            quest_context = await self.context_builder.build_quest_context(quest_name, language)
            user_context = await self.context_builder.build_user_context(user_id)
            
            # Include exact required items in context
            required_items = build_obj.get("containsOne", []) or build_obj.get("containsAll", [])
            requirements_text = "\n**REQUIRED QUEST ITEMS (MUST BE INCLUDED):**\n"
            for item in required_items:
                item_name = item.get("name", "Unknown")
                requirements_text += f"  - {item_name} (ID: {item.get('id')})\n"
            
            full_context = quest_context + "\n" + requirements_text
            
            prompt = self._create_quest_build_prompt(quest_name, full_context, user_context, language)
            
            response = await self._call_ollama(prompt)
            if not response:
                return None
            
            build_data = self._parse_build_response(response, language)
            build_data["quest_name"] = quest_name
            build_data["required_items"] = [item.get("name") for item in required_items]
            
            return build_data
            
        except Exception as e:
            logger.error(f"Error generating quest build: {e}", exc_info=True)
            return None
    
    async def _parse_intent(self, user_request: str, language: str) -> Dict:
        """Parse user intent from request."""
        intent = {
            "type": "custom",  # custom, quest, meta, random
            "weapon_name": None,
            "budget": None,
            "preferences": []
        }
        
        request_lower = user_request.lower()
        
        # Detect quest requests
        quest_keywords = ["квест", "quest", "оружейник", "gunsmith", "механик", "mechanic"]
        if any(kw in request_lower for kw in quest_keywords):
            intent["type"] = "quest"
        
        # Detect meta requests
        meta_keywords = ["мета", "meta", "лучш", "best", "топ", "top"]
        if any(kw in request_lower for kw in meta_keywords):
            intent["type"] = "meta"
        
        # Extract budget
        budget_pattern = r'(\d+)\s*[кkк]?(?:\s*руб|₽)?'
        budget_matches = re.findall(budget_pattern, request_lower)
        if budget_matches:
            budget_str = budget_matches[0]
            budget_value = int(budget_str)
            # Handle 'k' suffix
            if 'k' in request_lower or 'к' in request_lower:
                budget_value *= 1000
            intent["budget"] = budget_value
        
        # Extract weapon name (simple heuristic)
        weapon_keywords = [
            "ак", "ak", "м4", "m4", "мр", "mp", "свд", "svd", "вал", "val", 
            "вск", "vsk", "впо", "vpo", "сайга", "saiga", "вепрь", "vepr"
        ]
        for keyword in weapon_keywords:
            if keyword in request_lower:
                # Try to extract weapon name around keyword
                words = user_request.split()
                for word in words:
                    if keyword in word.lower():
                        intent["weapon_name"] = word
                        break
        
        # Extract preferences
        if "эргономика" in request_lower or "ergonomic" in request_lower or "ergo" in request_lower:
            intent["preferences"].append("ergonomics")
        if "отдача" in request_lower or "recoil" in request_lower:
            intent["preferences"].append("recoil")
        if "прицел" in request_lower or "sight" in request_lower or "scope" in request_lower:
            intent["preferences"].append("sight")
        
        return intent
    
    async def _build_generation_context(
        self, 
        intent: Dict, 
        user_id: int, 
        language: str
    ) -> str:
        """Build context for LLM based on intent."""
        context_parts = []
        
        # User context
        user_ctx = await self.context_builder.build_user_context(user_id)
        context_parts.append(user_ctx)
        
        # Weapon context
        if intent.get("weapon_name"):
            # Search for specific weapon
            weapons = await self.api.search_items(intent["weapon_name"], item_types=["gun"])
            if weapons:
                weapon = weapons[0]
                weapon_ctx = await self.context_builder.build_weapon_context(weapon["id"], language)
                context_parts.append(weapon_ctx)
                
                # Module context
                module_ctx = await self.context_builder.build_modules_context(weapon["id"], language)
                context_parts.append(module_ctx)
        else:
            # General weapon context
            weapon_ctx = await self.context_builder.build_weapon_context(None, language)
            context_parts.append(weapon_ctx)
        
        # Quest context if needed
        if intent["type"] == "quest":
            quest_ctx = await self.context_builder.build_quest_context(None, language)
            context_parts.append(quest_ctx)
        
        return "\n\n---\n\n".join(context_parts)
    
    def _create_build_prompt(self, user_request: str, context: str, language: str) -> str:
        """Create prompt for LLM build generation."""
        if language == "ru":
            system_prompt = """Ты — Никита Буянов, главный разработчик Escape from Tarkov и эксперт по игре. 
Твоя задача — помогать игрокам создавать оптимальные сборки оружия на основе актуальных данных из tarkov.dev.

ВАЖНЫЕ ПРАВИЛА:
1. НИКОГДА не показывай ID предметов (tarkov_id) пользователю - только названия
2. Всегда используй ТОЛЬКО данные из предоставленного контекста (названия оружия, модулей, цены)
3. КРИТИЧНО: Генерируй сборки с учётом СТРОГОЙ совместимости слотов:
   - Каждый модуль ДОЛЖЕН быть ТОЛЬКО из списка для конкретного слота в контексте
   - ПРОВЕРЯЙ что модуль указан в разделе этого слота
   - НЕ придумывай модули которых нет в контексте
   - НЕ используй гранатомёты, подствольники там, где их нет в списке
4. Учитывай бюджет пользователя (если указан)
5. Структурируй ответ иерархически: базовое оружие → каждый слот → модули → характеристики
6. Добавляй короткое обоснование выбора модулей
7. Указывай итоговую стоимость и доступность (торговцы/барахолка)

ФОРМАТ ОТВЕТА (НЕ ПОКАЗЫВАЙ ID ПРЕДМЕТОВ):
🤖 Никита Буянов:
Вот ваша сборка для [ОРУЖИЕ]:

1️⃣ **Базовое оружие:** [НАЗВАНИЕ]
   - Цена: [ЦЕНА] ₽
   - Базовая эргономика: [ЗНАЧЕНИЕ]
   - Базовая вертикальная отдача: [ЗНАЧЕНИЕ]
   - Базовая горизонтальная отдача: [ЗНАЧЕНИЕ]
   📍 [ТОРГОВЕЦ] L[УРОВЕНЬ]

2️⃣ **[СЛОТ 1]:**
   - [МОДУЛЬ] — [ЦЕНА] ₽ (Ergo: +X, Recoil: -Y%)
   📍 [ТОРГОВЕЦ] L[УРОВЕНЬ] или Flea Market

3️⃣ **[СЛОТ 2]:**
   - [МОДУЛЬ] — [ЦЕНА] ₽
   📍 [ТОРГОВЕЦ] L[УРОВЕНЬ] или Flea Market

...

📊 **Итоговые характеристики:**
   - Эргономика: [БАЗОВАЯ + СУММА МОДИФИКАТОРОВ]
   - Вертикальная отдача: [БАЗОВАЯ × (1 + СУММА_RECOIL_МОДИФИКАТОРОВ/100)]
   - Горизонтальная отдача: [БАЗОВАЯ × (1 + СУММА_RECOIL_МОДИФИКАТОРОВ/100)]

💰 **Итого:** [СУММА] ₽

💡 **Обоснование:** [1-2 предложения почему выбраны эти модули]

ВАЖНО ПО РАСЧЕТУ:
- Эргономика: просто суммируется (базовая + все модификаторы Ergo)
- Отдача: базовая отдача умножается на (1 + сумма всех Recoil модификаторов / 100)
- Recoil модификаторы обычно отрицательные (-5%, -10%), что уменьшает отдачу
"""
        else:
            system_prompt = """You are Nikita Buyanov, lead developer of Escape from Tarkov and game expert.
Your task is to help players create optimal weapon builds based on actual data from tarkov.dev.

IMPORTANT RULES:
1. NEVER show item IDs (tarkov_id) to user - only names
2. ONLY use data from provided context (weapon names, module names, prices)
3. CRITICAL: Generate builds with STRICT slot compatibility:
   - Each module MUST be ONLY from the list for that specific slot in context
   - VERIFY that module is listed in that slot's section
   - DO NOT invent modules not present in context
   - DO NOT use grenade launchers or underbarrel devices where they're not listed
4. Consider user's budget (if specified)
5. Structure response hierarchically: base weapon → each slot → modules → stats
6. Add brief reasoning for module choices
7. Include total cost and availability (traders/flea)

RESPONSE FORMAT (DO NOT SHOW ITEM IDs):
🤖 Nikita Buyanov:
Here's your build for [WEAPON]:

1️⃣ **Base weapon:** [NAME]
   - Price: [PRICE] ₽
   - Base ergonomics: [VALUE]
   - Base vertical recoil: [VALUE]
   - Base horizontal recoil: [VALUE]
   📍 [TRADER] L[LEVEL]

2️⃣ **[SLOT 1]:**
   - [MODULE] — [PRICE] ₽ (Ergo: +X, Recoil: -Y%)
   📍 [TRADER] L[LEVEL] or Flea Market

3️⃣ **[SLOT 2]:**
   - [MODULE] — [PRICE] ₽
   📍 [TRADER] L[LEVEL] or Flea Market

...

📊 **Final Stats:**
   - Ergonomics: [BASE + SUM OF ERGO MODIFIERS]
   - Vertical recoil: [BASE × (1 + SUM_OF_RECOIL_MODIFIERS/100)]
   - Horizontal recoil: [BASE × (1 + SUM_OF_RECOIL_MODIFIERS/100)]

💰 **Total:** [SUM] ₽

💡 **Reasoning:** [1-2 sentences why these modules were chosen]

IMPORTANT FOR CALCULATIONS:
- Ergonomics: simply add (base + all Ergo modifiers)
- Recoil: base recoil multiplied by (1 + sum of all Recoil modifiers / 100)
- Recoil modifiers are usually negative (-5%, -10%), which reduces recoil
"""
        
        prompt = f"""{system_prompt}

ДАННЫЕ ИЗ TARKOV.DEV:
{context}

ЗАПРОС ПОЛЬЗОВАТЕЛЯ:
{user_request}

Сгенерируй сборку на основе этих данных:"""
        
        return prompt
    
    def _create_quest_build_prompt(
        self, 
        quest_name: str, 
        quest_context: str, 
        user_context: str,
        language: str
    ) -> str:
        """Create prompt specifically for quest builds."""
        if language == "ru":
            prompt = f"""Ты — Никита Буянов, эксперт по квестам Escape from Tarkov.
Создай сборку для квеста "{quest_name}".

КРИТИЧНО ВАЖНО:
1. Сборка ДОЛЖНА включать ВСЕ модули из раздела "REQUIRED MODULES"
2. НЕ показывай ID предметов пользователю
3. Если указаны STAT REQUIREMENTS - сборка ДОЛЖНА их выполнить
4. Используй ТОЛЬКО модули из контекста
5. Объясни как требования квеста выполнены

ИНФОРМАЦИЯ О КВЕСТЕ:
{quest_context}

{user_context}

Создай сборку на русском языке, которая ТОЧНО выполнит все требования квеста:"""
        else:
            prompt = f"""You are Nikita Buyanov, expert on Escape from Tarkov quests.
Create a build for quest "{quest_name}".

CRITICALLY IMPORTANT:
1. Build MUST include ALL modules from "REQUIRED MODULES" section
2. DO NOT show item IDs to user
3. If STAT REQUIREMENTS are specified - build MUST meet them
4. Use ONLY modules from context
5. Explain how quest requirements are fulfilled

QUEST INFORMATION:
{quest_context}

{user_context}

Create a build in English that EXACTLY fulfills all quest requirements:"""
        
        return prompt
    
    def _select_random_tier(self) -> str:
        """Select random tier based on distribution."""
        import random
        rand = random.random()
        cumulative = 0
        for tier, probability in self.TIER_DISTRIBUTION.items():
            cumulative += probability
            if rand <= cumulative:
                return tier
        return "B"  # Default fallback
    
    def _extract_tier_from_response(self, response: str, target_tier: Optional[str] = None) -> str:
        """Extract tier from AI response or use target tier."""
        if target_tier:
            return target_tier
        
        # Try to find tier in response
        tier_pattern = r'(?:Tier|Тир)[:\s]+([SABCD])[\-]?Tier'
        match = re.search(tier_pattern, response, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        
        # Default to B tier
        return "B"
    
    async def _build_context_for_intent(
        self,
        intent: str,
        context: Dict,
        user_id: int,
        language: str
    ) -> str:
        """Build context string based on intent type."""
        from .context_builder import ContextBuilder
        context_builder = ContextBuilder(self.api, self.db)
        
        parts = []
        
        if intent == "meta_build":
            # Meta build - focus on optimal performance
            weapon_id = context.get("weapon_id")
            if weapon_id:
                weapon_context = await context_builder.build_weapon_context(weapon_id, language)
                module_context = await context_builder.build_modules_context(weapon_id, language)
                parts.extend([weapon_context, module_context])
        
        elif intent == "quest_build":
            # Quest build - exact requirements
            quest_name = context.get("quest_name")
            if quest_name:
                quest_context = await context_builder.build_quest_context(quest_name, language)
                parts.append(quest_context)
            weapon_id = context.get("weapon_id")
            if weapon_id:
                module_context = await context_builder.build_modules_context(weapon_id, language)
                parts.append(module_context)
        
        elif intent == "random_build":
            # Random build - with tier variety
            weapon_id = context.get("weapon_id")
            if weapon_id:
                weapon_context = await context_builder.build_weapon_context(weapon_id, language)
                module_context = await context_builder.build_modules_context(weapon_id, language)
                parts.extend([weapon_context, module_context])
        
        else:  # custom_request
            weapon_id = context.get("weapon_id")
            if weapon_id:
                weapon_context = await context_builder.build_weapon_context(weapon_id, language)
                module_context = await context_builder.build_modules_context(weapon_id, language)
                parts.extend([weapon_context, module_context])
        
        # Add user context
        user_context = await context_builder.build_user_context(user_id)
        parts.append(user_context)
        
        return "\n\n---\n\n".join(parts)
    
    def _create_prompt_for_intent(
        self,
        intent: str,
        context: Dict,
        context_str: str,
        language: str
    ) -> str:
        """Create prompt based on intent type."""
        target_tier = context.get("target_tier", "B")
        budget = context.get("budget")
        weapon_name = context.get("weapon_name", "weapon")
        
        if intent == "meta_build":
            if language == "ru":
                return f"""Ты — Никита Буянов, эксперт Escape from Tarkov.
Создай оптимальную мета-сборку для {weapon_name}.

ВАЖНО:
1. ПИШИ ВСЁ НА РУССКОМ! Названия модулей, характеристики - всё на русском
2. Для КАЖДОГО модуля УКАЖИ:
   - Название (на русском)
   - Торговец и уровень: Прапор LL2, Механик LL4, Барахолка
   - Цену и модификаторы (Ergo: +X, Recoil: -Y%)
3. Используй лучшие модули (тир A/S)
4. Фокус на минимальной отдаче и высокой эргономике
5. Укажи тир в начале
6. ПРАВИЛЬНО рассчитывай итоговые характеристики
7. Объясни почему это мета

ФОРМАТ:
🔫 **{weapon_name}** - Тир [A/S]

📝 **Описание:**
[Почему это мета-сборка]

🔧 **Модули:**
1. [Название] - [Торговец LLХ] - [Цена]₽ (Ergo: +X, Recoil: -Y%)
2. ...

📊 **Итоговые характеристики:**
   - Эргономика: [базовая + сумма Ergo]
   - Вертикальная отдача: [базовая × (1 + сумма Recoil%/100)]
   - Горизонтальная отдача: [базовая × (1 + сумма Recoil%/100)]

💰 **Стоимость:** [Сумма]₽

КОНТЕКСТ:
{context_str}

Создай сборку:"""
            
            else:
                return f"""You are Nikita Buyanov, Escape from Tarkov expert.
Create optimal meta build for {weapon_name}.

IMPORTANT:
1. WRITE IN ENGLISH! Module names, characteristics - all in English
2. For EACH module SPECIFY:
   - Module name
   - Trader and level: Prapor LL2, Mechanic LL4, Flea Market
   - Price and modifiers (Ergo: +X, Recoil: -Y%)
3. Use best modules (tier A/S)
4. Focus on minimal recoil and high ergonomics
5. Specify tier at start
6. CORRECTLY calculate final stats
7. Explain why this is meta

FORMAT:
🔫 **{weapon_name}** - Tier [A/S]

📝 **Description:**
[Why this is meta]

🔧 **Modules:**
1. [Name] - [Trader LLX] - [Price]₽ (Ergo: +X, Recoil: -Y%)
2. ...

📊 **Final Stats:**
   - Ergonomics: [base + sum of Ergo]
   - Vertical recoil: [base × (1 + sum of Recoil%/100)]
   - Horizontal recoil: [base × (1 + sum of Recoil%/100)]

💰 **Total Cost:** [Sum]₽

CONTEXT:
{context_str}

Create build:"""
        
        elif intent == "quest_build":
            quest_name = context.get("quest_name", "квеста")
            return f"""Ты — Никита Буянов, эксперт по квестам Escape from Tarkov.
Создай сборку для {quest_name}.

КРИТИЧНО ВАЖНО:
1. Сборка ДОЛЖНА включать ВСЕ требуемые модули из REQUIRED MODULES
2. НЕ показывай ID предметов
3. Выполни все STAT REQUIREMENTS
4. Укажи тир сборки
5. Объясни как требования выполнены

КОНТЕКСТ:
{context_str}

Создай квестовую сборку на русском:"""
        
        if intent == "random_build":
            target_tier = context.get("target_tier", "B")
            if language == "ru":
                return f"""Ты — Никита Буянов, эксперт Escape from Tarkov.
Создай случайную сборку для {weapon_name}.

ВАЖНО:
1. ПИШИ ВСЁ НА РУССКОМ! Названия модулей, характеристики - всё на русском
2. Для КАЖДОГО модуля УКАЖИ:
   - Название (на русском)
   - Торговец/Барахолка
   - Цену и модификаторы (Ergo: +X, Recoil: -Y%)
3. Сборка должна быть тира {target_tier}
4. Укажи тир в начале
5. ПРАВИЛЬНО рассчитывай характеристики
6. Будь креативным

ФОРМАТ:
🔫 **{weapon_name}** - Тир {target_tier}

📝 **Описание:**
[Краткое описание]

🔧 **Модули:**
1. [Название] - [Торговец/Барахолка] - [Цена]₽ (Ergo: +X, Recoil: -Y%)
2. ...

📊 **Итоговые характеристики:**
   - Эргономика: [базовая + сумма Ergo]
   - Вертикальная отдача: [базовая × (1 + сумма Recoil%/100)]
   - Горизонтальная отдача: [базовая × (1 + сумма Recoil%/100)]

💰 **Стоимость:** [Сумма]₽

КОНТЕКСТ:
{context_str}

Создай сборку:"""
            else:
                return f"""You are Nikita Buyanov, Escape from Tarkov expert.
Create random build for {weapon_name}.

IMPORTANT:
1. WRITE IN ENGLISH! Module names, characteristics - all in English
2. For EACH module SPECIFY:
   - Module name
   - Trader/Flea Market
   - Price and modifiers (Ergo: +X, Recoil: -Y%)
3. Build should be tier {target_tier}
4. Specify tier at start
5. CORRECTLY calculate final stats
6. Be creative

FORMAT:
🔫 **{weapon_name}** - Tier {target_tier}

📝 **Description:**
[Brief description]

🔧 **Modules:**
1. [Name] - [Trader/Flea] - [Price]₽ (Ergo: +X, Recoil: -Y%)
2. ...

📊 **Final Stats:**
   - Ergonomics: [base + sum of Ergo]
   - Vertical recoil: [base × (1 + sum of Recoil%/100)]
   - Horizontal recoil: [base × (1 + sum of Recoil%/100)]

💰 **Total Cost:** [Sum]₽

CONTEXT:
{context_str}

Create build:"""
        
        # Custom request (loyalty build, budget build, etc.)
        trader_levels = context.get("trader_levels")
        budget = context.get("budget")
        use_flea = context.get("use_flea_market", True)
        
        if trader_levels:
            # Loyalty-based build
            trader_names_ru = {
                "prapor": "Прапор",
                "therapist": "Терапевт",
                "fence": "Скупщик",
                "skier": "Лыжник",
                "mechanic": "Механик",
                "ragman": "Барахольщик",
                "jaeger": "Егерь"
            }
            
            trader_names_en = {
                "prapor": "Prapor",
                "therapist": "Therapist",
                "fence": "Fence",
                "skier": "Skier",
                "mechanic": "Mechanic",
                "ragman": "Ragman",
                "jaeger": "Jaeger"
            }
            
            trader_names = trader_names_ru if language == "ru" else trader_names_en
            
            loyalty_info = "\n".join([
                f"{trader_names[trader]}: LL{level}" + (" (недоступен)" if level == 0 else "")
                for trader, level in trader_levels.items()
            ])
            
            budget_info = f"\nБюджет: {budget:,} ₽" if budget else "\nБюджет: без ограничений"
            flea_info = "\nБарахолка: " + ("доступна" if use_flea else "НЕ доступна")
            
            if language == "ru":
                return f"""Ты — Никита Буянов, эксперт Escape from Tarkov.
Создай сборку для {weapon_name} с учетом уровней лояльности торговцев.

УРОВНИ ЛОЯЛЬНОСТИ:
{loyalty_info}{budget_info}{flea_info}

ВАЖНО:
1. ПИШИ ВСЁ НА РУССКОМ ЯЗЫКЕ! Названия модулей, слоты, характеристики - всё на русском
2. Для КАЖДОГО модуля УКАЖИ:
   - Название модуля (на русском!)
   - Торговец и уровень: Прапор LL2, Механик LL4, Барахолка и т.д.
   - Цену в рублях и модификаторы (Ergo: +X, Recoil: -Y%)
3. Используй ТОЛЬКО модули доступные на указанных уровнях лояльности
4. Если у торговца LL0 (Егерь) - НЕ используй его модули
5. {'Можешь использовать барахолку' if use_flea else 'НЕ используй барахолку, только торговцы'}
6. Соблюдай бюджет
7. Укажи тир сборки в начале
8. ПРАВИЛЬНО рассчитывай итоговые характеристики
9. Объясни почему выбраны эти модули

ФОРМАТ ОТВЕТА:
🔫 **{weapon_name}** - Тир [S/A/B/C/D]

📝 **Описание:**
[Краткое описание сборки]

🔧 **Модули:**
1. [Название на русском] - [Торговец LLХ] - [Цена]₽ (Ergo: +X, Recoil: -Y%)
2. ...

📊 **Итоговые характеристики:**
   - Эргономика: [базовая + сумма Ergo]
   - Вертикальная отдача: [базовая × (1 + сумма Recoil%/100)]
   - Горизонтальная отдача: [базовая × (1 + сумма Recoil%/100)]

💰 **Стоимость:** [Сумма]₽

КОНТЕКСТ:
{context_str}

Создай сборку:"""
            else:
                return f"""You are Nikita Buyanov, Escape from Tarkov expert.
Create build for {weapon_name} considering trader loyalty levels.

LOYALTY LEVELS:
{loyalty_info}{budget_info_en}{flea_info_en}

IMPORTANT:
1. WRITE EVERYTHING IN ENGLISH! Module names, slots, characteristics - all in English
2. For EACH module SPECIFY:
   - Module name (in English)
   - Trader and level: Prapor LL2, Mechanic LL4, Flea Market, etc.
   - Price in rubles and modifiers (Ergo: +X, Recoil: -Y%)
3. Use ONLY modules available at specified loyalty levels
4. If trader has LL0 (Jaeger) - DO NOT use his modules
5. {'You can use flea market' if use_flea else 'DO NOT use flea market, only traders'}
6. Stay within budget
7. Specify build tier at the start
8. CORRECTLY calculate final stats
9. Explain why these modules were chosen

FORMAT:
🔫 **{weapon_name}** - Tier [S/A/B/C/D]

📝 **Description:**
[Brief build description]

🔧 **Modules:**
1. [Module name] - [Trader LLX] - [Price]₽ (Ergo: +X, Recoil: -Y%)
2. ...

📊 **Final Stats:**
   - Ergonomics: [base + sum of Ergo]
   - Vertical recoil: [base × (1 + sum of Recoil%/100)]
   - Horizontal recoil: [base × (1 + sum of Recoil%/100)]

💰 **Total Cost:** [Sum]₽

CONTEXT:
{context_str}

Create build:"""
        
        elif budget:
            # Budget-only build
            budget_text = f"{budget:,} ₽"
            if language == "ru":
                return f"""Ты — Никита Буянов, эксперт Escape from Tarkov.
Создай сборку для {weapon_name} с бюджетом {budget_text}.

ВАЖНО:
1. ПИШИ ВСЁ НА РУССКОМ! Названия модулей, характеристики - всё на русском
2. Для КАЖДОГО модуля УКАЖИ:
   - Название (на русском)
   - Торговец/Барахолка
   - Цену и модификаторы (Ergo: +X, Recoil: -Y%)
3. Уложись в бюджет {budget_text}
4. Оптимизируй цена/качество
5. Укажи тир в начале
6. ПРАВИЛЬНО рассчитывай характеристики
7. Объясни выбор

ФОРМАТ:
🔫 **{weapon_name}** - Тир [S/A/B/C/D]

📝 **Описание:**
[Краткое описание]

🔧 **Модули:**
1. [Название] - [Торговец/Барахолка] - [Цена]₽ (Ergo: +X, Recoil: -Y%)
2. ...

📊 **Итоговые характеристики:**
   - Эргономика: [базовая + сумма Ergo]
   - Вертикальная отдача: [базовая × (1 + сумма Recoil%/100)]
   - Горизонтальная отдача: [базовая × (1 + сумма Recoil%/100)]

💰 **Стоимость:** [Сумма]₽

КОНТЕКСТ:
{context_str}

Создай сборку:"""
            else:
                return f"""You are Nikita Buyanov, Escape from Tarkov expert.
Create build for {weapon_name} with budget {budget_text}.

IMPORTANT:
1. WRITE IN ENGLISH! Module names, characteristics - all in English
2. For EACH module SPECIFY:
   - Module name
   - Trader/Flea Market
   - Price
3. Stay within budget {budget_text}
4. Optimize price/quality ratio
5. Specify build tier
6. Explain module choices

CONTEXT:
{context_str}

Create build in English:"""
        
        # Fallback to generic custom request
        return self._create_build_prompt(context.get("user_request", ""), context_str, language)
    
    async def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call Ollama API to generate response."""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "max_tokens": 2048
                    }
                }
                
                async with session.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Ollama API error {response.status}: {error_text}")
                        return None
                    
                    # Parse response (Ollama cloud models return text/plain with valid JSON)
                    try:
                        result = await response.json(content_type=None)
                        return result.get("response", "")
                    except Exception as e:
                        error_text = await response.text()
                        logger.error(f"Failed to parse Ollama response: {e}. Response: {error_text[:500]}")
                        return None
        
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}", exc_info=True)
            return None
    
    def _parse_build_response(self, response: str, language: str) -> Dict:
        """Parse LLM response into structured build data."""
        build_data = {
            "text": response,
            "weapon": None,
            "modules": [],
            "stats": {},
            "total_cost": None,
            "reasoning": None
        }
        
        try:
            # Extract weapon name
            weapon_pattern = r"(?:Base weapon|Базовое оружие):\s*\*\*([^\*]+)\*\*"
            weapon_match = re.search(weapon_pattern, response, re.IGNORECASE)
            if weapon_match:
                build_data["weapon"] = weapon_match.group(1).strip()
            
            # Extract total cost
            cost_pattern = r"(?:Total|Итого):\s*([0-9,]+)\s*₽"
            cost_match = re.search(cost_pattern, response)
            if cost_match:
                cost_str = cost_match.group(1).replace(",", "")
                build_data["total_cost"] = int(cost_str)
            
            # Extract stats
            ergo_pattern = r"(?:Ergonomics|Эргономика):\s*([0-9]+)"
            ergo_match = re.search(ergo_pattern, response)
            if ergo_match:
                build_data["stats"]["ergonomics"] = int(ergo_match.group(1))
            
            recoil_v_pattern = r"(?:Vertical recoil|Вертикальная отдача):\s*([0-9]+)"
            recoil_v_match = re.search(recoil_v_pattern, response)
            if recoil_v_match:
                build_data["stats"]["recoil_vertical"] = int(recoil_v_match.group(1))
            
            # Extract reasoning
            reasoning_pattern = r"(?:Reasoning|Обоснование):\s*(.+?)(?:\n\n|$)"
            reasoning_match = re.search(reasoning_pattern, response, re.DOTALL)
            if reasoning_match:
                build_data["reasoning"] = reasoning_match.group(1).strip()
        
        except Exception as e:
            logger.error(f"Error parsing build response: {e}")
        
        return build_data
    
    async def check_ollama_available(self) -> bool:
        """Check if Ollama service is available."""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.ollama_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            return False
