"""Localization texts for the EFT Helper bot."""

TEXTS = {
    "ru": {
        # Main menu
        "main_menu": "🏠 Главное меню",
        "search_weapon": "🔍 Поиск оружия",
        "all_quest_builds": "📜 Все квестовые сборки",
        "random_build": "🎲 Случайная сборка",
        "meta_builds": "⚔️ Мета-сборки",
        "loyalty_builds": "🤝 Сборки по лояльности торговцев",
        "loyalty_build_menu": "🤝 Сборка по лояльности",
        "budget_build_menu": "💰 Сборка по бюджету",
        "best_weapons": "⭐ Лучшее оружие",
        "settings": "⚙️ Настройки",
        
        # Welcome message
        "welcome": "👋 Добро пожаловать в EFT Helper!\n\nЭтот бот поможет вам подобрать оптимальные сборки оружия для Escape from Tarkov.\n\nВыберите действие из меню ниже:",
        "select_language": "🌍 Выберите язык / Select your language:",
        "language_selected": "✅ Язык выбран: Русский\n\nДобро пожаловать в EFT Helper! Этот бот поможет вам подобрать оптимальные сборки оружия для Escape from Tarkov.",
        
        # Search
        "enter_weapon_name": "🔍 Введите название оружия для поиска:\n\nНапример: AK-74N, MP-153, M4A1",
        "weapon_not_found": "❌ Оружие не найдено. Попробуйте другой запрос.",
        "select_weapon": "Выберите оружие:",
        "no_weapons_found": "❌ Оружие не найдено в базе данных.",
        
        # Build filters
        "select_build_type": "Выберите тип сборки для {weapon}:",
        "random_build_btn": "🎲 Случайная",
        "meta_build_btn": "⚔️ Мета",
        "quest_build_btn": "📜 Квестовая",
        "constructor_btn": "🛠️ Конфигуратор",
        "budget_build_btn": "💰 По бюджету",
        "loyalty_build_btn": "🤝 По лояльности",
        
        # Build display
        "build_card_title": "🔫 {weapon}\n",
        "build_category": "📂 Категория: {category}",
        "build_quest": "📜 Квест: {quest}",
        "build_modules": "🔧 Модули:",
        "build_total_cost": "💰 Общая стоимость: {cost} ₽",
        "build_loyalty": "🤝 Минимальная лояльность: {level}",
        "build_planner": "🔗 [Открыть в планировщике]({link})",
        "no_builds_found": "❌ Сборки не найдены для этого оружия.",
        
        # Quest builds
        "quest_builds_list": "📜 Квестовые сборки\n\nВыберите квест:",
        "no_quest_builds": "❌ Квестовые сборки не найдены.",
        "quest_description": "📝 {description}",
        "loading_quests": "⏳ Загружаю квесты...",
        "quest_builds_title": "📜 Квестовые сборки",
        "all_quest_builds_title": "📜 Все квестовые сборки",
        "select_quest": "Выберите квест для просмотра информации:",
        "quest_trader": "Торговец",
        "quest_level": "Требуемый уровень",
        "quest_experience": "Опыт",
        "quest_map": "Карта",
        "quest_required_tasks": "Требуемые квесты",
        "quest_objectives": "Цели",
        "quest_optional": "опц.",
        "quest_and_more": "и ещё",
        "quest_more_objectives": "целей",
        "quest_recommended_build": "Рекомендуемая сборка",
        
        # Random build
        "random_build_title": "🎲 Случайная сборка",
        "generating_random": "🎲 Генерирую случайную сборку...",
        "truly_random_build": "🎰 Рандомная сборка",
        "generating_truly_random": "🎰 Генерирую по-настоящему рандомную сборку...",
        "truly_random_build_title": "🎰 Рандомная сборка",
        
        # Meta builds
        "meta_builds_title": "⚔️ Мета-сборки 2025",
        "meta_builds_desc": "Актуальные топовые сборки по категориям:",
        "no_meta_builds": "❌ Мета-сборки не найдены.",
        
        # Loyalty builds
        "select_trader": "🤝 Выберите торговца:",
        "select_loyalty_level": "Выберите уровень лояльности для {trader}:",
        "loyalty_level": "Уровень {level}",
        "no_loyalty_builds": "❌ Нет доступных сборок для {trader} (уровень {level}).",
        "setup_loyalty_levels": "🤝 Настройка уровней лояльности\n\nУкажите ваши текущие уровни лояльности к торговцам. Это позволит боту показывать только доступные вам сборки.",
        "current_loyalty_levels": "Текущие уровни лояльности:",
        "trader_level_set": "✅ Уровень лояльности к {trader} установлен: {level}",
        "loyalty_levels_saved": "✅ Уровни лояльности сохранены!",
        "show_available_builds": "📋 Показать доступные сборки",
        "reset_loyalty_levels": "🔄 Сбросить уровни",
        "select_weapon_category": "Выберите категорию оружия:",
        "any_category": "🔫 Любая категория",
        "enter_max_budget": "💰 Введите максимальный бюджет (в рублях):\n\nНапример: 500000\n\nОтправьте /skip чтобы пропустить",
        "skip_budget": "⏭️ Пропустить бюджет",
        "invalid_budget_format": "❌ Неверный формат. Введите число или /skip",
        "budget_set_to": "✅ Бюджет установлен: {budget} ₽",
        "no_budget_limit": "♾️ Без ограничения бюджета",
        "loyalty_builds_filters": "📋 Фильтры:\n  • Категория: {category}\n  • Бюджет: {budget}",
        "found_builds": "Найдено сборок: {count}",
        "regenerate": "🔄 Перегенерировать",
        "select_flea_market": "Использовать барахолку?",
        "traders_only": "🤝 Только торговцы",
        "with_flea_market": "🏪 С барахолкой",
        
        # Best weapons
        "best_weapons_title": "⭐ Лучшее оружие по категориям",
        "tier_s": "🏆 S-Tier (Лучшие)",
        "tier_a": "🥇 A-Tier (Отличные)",
        "tier_b": "🥈 B-Tier (Хорошие)",
        "tier_c": "🥉 C-Tier (Средние)",
        "tier_d": "📊 D-Tier (Слабые)",
        "no_tier_weapons": "❌ Оружие не найдено для этого уровня.",
        
        # Settings
        "settings_title": "⚙️ Настройки",
        "current_language": "Текущий язык: {language_name}",
        "change_language": "Изменить язык:",
        "language_changed": "✅ Язык изменен на: {language_name}",
        "lang_ru": "🇷🇺 Русский",
        "lang_en": "🇬🇧 English",
        
        # Build Constructor (v3.0)
        "build_constructor": "🛠 Конструктор сборок",
        "dynamic_random_build": "🎲 Динамическая сборка",
        "community_builds": "👥 Сборки сообщества",
        "my_builds": "💾 Мои сборки",
        "constructor_title": "🛠 Конструктор сборок",
        "constructor_desc": "Создайте свою идеальную сборку с учётом бюджета и лояльности",
        "select_weapon_for_build": "Выберите оружие для сборки:",
        "enter_budget": "💰 Введите бюджет в рублях (например: 150000):",
        "budget_set": "✅ Бюджет установлен: {budget} ₽",
        "invalid_budget": "❌ Неверный формат бюджета. Введите число.",
        "use_flea_market": "🛒 Использовать только Flea Market?",
        "generating_build": "⚙️ Генерирую сборку...",
        "build_generated": "✅ Сборка сгенерирована!",
        "save_build": "💾 Сохранить",
        "regenerate_build": "🔄 Перегенерировать",
        "share_build": "📤 Поделиться",
        "build_saved": "✅ Сборка сохранена!",
        "enter_build_name": "Введите название сборки:",
        "build_stats": "📊 Характеристики:",
        "build_ergonomics": "  • Эргономика: {value}",
        "build_recoil_v": "  • Вертикальная отдача: {value}",
        "build_recoil_h": "  • Горизонтальная отдача: {value}",
        "build_tier": "🏆 Тир качества: {tier}",
        "build_spent": "💸 Потрачено: {cost} ₽ из {budget} ₽",
        "build_remaining": "💰 Остаток: {remaining} ₽",
        "build_available_from": "🛒 Доступно: {sources}",
        "build_modules_list": "🔧 Модули:",
        
        # Community Builds
        "community_builds_title": "👥 Сборки сообщества",
        "community_builds_desc": "Просмотр и копирование сборок других игроков",
        "no_community_builds": "❌ Пока нет публичных сборок",
        "build_by_user": "Автор: Пользователь #{user_id}",
        "build_likes": "👍 {count}",
        "like_build": "👍 Нравится",
        "copy_build": "📋 Копировать",
        "build_copied": "✅ Сборка скопирована в ваши сохранения!",
        "build_liked": "✅ Вам понравилась эта сборка!",
        "view_details": "📝 Детали",
        "make_public": "🌐 Опубликовать",
        "make_private": "🔒 Скрыть",
        "build_published": "✅ Сборка опубликована!",
        "build_unpublished": "✅ Сборка скрыта",
        "delete_build": "🗑 Удалить",
        "build_deleted": "✅ Сборка удалена",
        "confirm_delete": "Вы уверены, что хотите удалить эту сборку?",
        "my_builds_title": "💾 Мои сборки",
        "no_saved_builds": "❌ У вас пока нет сохранённых сборок",
        
        # Dynamic Build Generation
        "dynamic_build_title": "🎲 Динамическая сборка",
        "dynamic_build_desc": "Генерация случайной сборки с учётом ваших параметров",
        "setup_generation": "⚙️ Настройка генерации",
        "any_weapon": "Любое оружие",
        "budget_question": "Какой у вас бюджет?",
        "flea_only_question": "Использовать только Flea Market?",
        "yes": "✅ Да",
        "no": "❌ Нет",
        "prioritize_question": "Что приоритезировать?",
        "prioritize_ergo": "📈 Эргономика",
        "prioritize_recoil": "📉 Отдача",
        "balanced": "⚖️ Баланс",
        
        # Traders
        "prapor": "Прапор",
        "therapist": "Терапевт",
        "fence": "Скупщик",
        "skier": "Лыжник",
        "peacekeeper": "Миротворец",
        "mechanic": "Механик",
        "ragman": "Барахольщик",
        "jaeger": "Егерь",
        "ref": "Реф",
        "lightkeeper": "Смотритель",
        # Trader names mapping (for API responses)
        "trader_prapor": "Прапор",
        "trader_therapist": "Терапевт",
        "trader_fence": "Скупщик",
        "trader_skier": "Лыжник",
        "trader_peacekeeper": "Миротворец",
        "trader_mechanic": "Механик",
        "trader_ragman": "Барахольщик",
        "trader_jaeger": "Егерь",
        "trader_ref": "Реф",
        "trader_lightkeeper": "Смотритель",
        
        # Categories
        "assault_rifle": "Штурмовая винтовка",
        "smg": "Пистолет-пулемет",
        "sniper": "Снайперская винтовка",
        "dmr": "Марксманская винтовка",
        "shotgun": "Дробовик",
        "pistol": "Пистолет",
        "lmg": "Ручной пулемет",
        
        # Build categories
        "category_random": "Случайная",
        "category_meta": "Мета",
        "category_quest": "Квестовая",
        "category_loyalty": "По лояльности",
        
        # Weapon categories
        "select_category": "Выберите категорию оружия:",
        "category_pistols": "🔫 Пистолеты",
        "category_smg": "🔫 Пистолеты-пулемёты",
        "category_assault_rifles": "🔫 Штурмовые винтовки",
        "category_dmr": "🔫 Марксманские винтовки",
        "category_sniper_rifles": "🔫 Снайперские винтовки",
        "category_shotguns": "🔫 Дробовики",
        "category_lmg": "🔫 Пулемёты",
        "search_by_name": "🔍 Поиск по названию",
        
        # Weapon stats
        "caliber": "Калибр",
        "fire_rate": "Скорострельность",
        "weapon_price": "Цена оружия",
        "weapon_characteristics": "ХАРАКТЕРИСТИКИ ОРУЖИЯ",
        "final_stats": "ИТОГОВЫЕ ХАРАКТЕРИСТИКИ",
        "ergonomics_stat": "Эргономика",
        "vertical_recoil": "Вертикальная отдача",
        "horizontal_recoil": "Горизонтальная отдача",
        "budget_title": "БЮДЖЕТ",
        "spent": "Потрачено",
        "remaining": "Остаток",
        
        # Media types
        "media_photo": "фото",
        "media_video": "видео",
        "media_document": "документ",
        
        # Common
        "back": "◀️ Назад",
        "main_menu_btn": "🏠 Главное меню",
        "suggestion_meta_builds": "⚔️ Мета-сборки",
        "quest_build_failed": "❌ Не удалось сгенерировать сборку для квеста.",
        "meta_build_request": "Покажи лучшую мета-сборку для {weapon}",
        "meta_build_request_general": "Покажи лучшие мета-сборки",
        
        # Voice messages
        "voice_transcribed": "🎤 Распознано: _{text}_",
        "voice_transcription_failed": "❌ Не удалось распознать голосовое сообщение.",
        "voice_not_supported": "❌ Голосовые сообщения пока не поддерживаются.",
        "voice_processing_error": "❌ Ошибка при обработке голосового сообщения.",
        "voice_processing": "🎤 Обрабатываю голосовое сообщение...",
        
        # AI Assistant (v5.1)
        "ai_not_available": "❌ AI-ассистент временно недоступен. Используйте меню для навигации.",
        "ai_error": "❌ Ошибка AI-ассистента. Попробуйте ещё раз или используйте меню.",
        "ai_generating": "🤖 Никита Буянов: Обрабатываю запрос...",
        
        # News
        "news_loading": "⏳ Загружаю новости Escape from Tarkov...",
        "news_error": "❌ Не удалось загрузить новости. Попробуйте позже.",
        
        # Tier System (v5.3)
        "build_tier_label": "🏆 Тир сборки",
        "tier_s_desc": "S-Tier: Топовые характеристики, дорогие модули",
        "tier_a_desc": "A-Tier: Отличное качество, баланс цены и эффективности",
        "tier_b_desc": "B-Tier: Хорошая сборка, доступная цена",
        "tier_c_desc": "C-Tier: Средняя сборка, бюджетная",
        "tier_d_desc": "D-Tier: Экспериментальная или слабая сборка",
        "generating_meta_build": "⚙️ Генерирую мета-сборку...",
        "meta_build_button": "🤖 Сгенерировать мета-сборку",
        "random_build_with_tier": "🎲 Генерирую случайную сборку (тир: {tier})...",
    },
    "en": {
        # Main menu
        "main_menu": "🏠 Main Menu",
        "search_weapon": "🔍 Search Weapon",
        "all_quest_builds": "📜 All Quest Builds",
        "random_build": "🎲 Random Build",
        "meta_builds": "⚔️ Meta Builds",
        "loyalty_builds": "🤝 Loyalty Builds",
        "loyalty_build_menu": "🤝 Loyalty Build",
        "budget_build_menu": "💰 Budget Build",
        "best_weapons": "⭐ Best Weapons",
        "settings": "⚙️ Settings",
        "dynamic_random_build": "🎲 Dynamic Build",
        
        # Welcome
        "welcome": "👋 Welcome to EFT Helper!\n\nThis bot will help you find optimal weapon builds for Escape from Tarkov.\n\nSelect an action from the menu below:",
        "select_language": "🌍 Выберите язык / Select your language:",
        "language_selected": "✅ Language selected: English\n\nWelcome to EFT Helper! This bot will help you find optimal weapon builds for Escape from Tarkov.",
        
        # Common
        "back": "◀️ Back",
        "main_menu_btn": "🏠 Main Menu",
        "error": "❌ Error occurred",
        "loading": "⏳ Loading...",
        
        # Voice messages
        "voice_transcribed": "🎤 Recognized: _{text}_",
        "voice_transcription_failed": "❌ Failed to recognize voice message.",
        "voice_not_supported": "❌ Voice messages are not supported yet.",
        "voice_processing_error": "❌ Error processing voice message.",
        "voice_processing": "🎤 Processing voice message...",
        
        # AI Assistant (v5.1)
        "ai_not_available": "❌ AI assistant is temporarily unavailable. Use menu for navigation.",
        "ai_error": "❌ AI assistant error. Please try again or use the menu.",
        "ai_generating": "🤖 Nikita Buyanov: Processing request...",
        
        # News
        "news_loading": "⏳ Loading Escape from Tarkov news...",
        "news_error": "❌ Failed to load news. Please try again later.",
        
        # Tier System (v5.3)
        "build_tier_label": "🏆 Build Tier",
        "tier_s_desc": "S-Tier: Top characteristics, expensive modules",
        "tier_a_desc": "A-Tier: Excellent quality, balanced price and effectiveness",
        "tier_b_desc": "B-Tier: Good build, affordable price",
        "tier_c_desc": "C-Tier: Average build, budget-friendly",
        "tier_d_desc": "D-Tier: Experimental or weak build",
        "generating_meta_build": "⚙️ Generating meta build...",
        "meta_build_button": "🤖 Generate Meta Build",
        "random_build_with_tier": "🎲 Generating random build (tier: {tier})...",
    }
}


def get_text(key: str, language: str = "ru", **kwargs) -> str:
    """Get localized text by key."""
    text = TEXTS.get(language, TEXTS["ru"]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text
