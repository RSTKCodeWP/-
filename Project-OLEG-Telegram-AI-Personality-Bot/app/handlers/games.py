"""Игровые механики и команды."""

import logging
import random
from datetime import datetime, timedelta
import io
from aiogram import Router, Bot
from aiogram.types import Message, BufferedInputFile, CallbackQuery
from aiogram import F
from aiogram.filters import Command
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, GameStat, Wallet, Marriage
from app.services.achievements import check_and_award_achievements
from app.services.quests import check_and_update_quests
from app.services.profile import get_full_user_profile
from app.services.game_engine import game_engine, RouletteResult, CoinFlipResult
from app.services.leagues import league_service, League
from app.services.profile_generator import profile_generator, ProfileData
from app.services.tournaments import tournament_service, TournamentDiscipline
from app.services.state_manager import state_manager
from app.services.sparkline import sparkline_generator
from app.services.event_service import event_service, EventModifier
from app.services import wallet_service
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()


# ============================================================================
# Async wrappers for game_engine using wallet_service
# ============================================================================

async def play_roulette_async(user_id: int, bet_amount: int = 0) -> RouletteResult:
    """
    Play Russian Roulette with unified wallet balance.
    
    Args:
        user_id: Telegram user ID
        bet_amount: Amount to bet (0 for standard mode)
        
    Returns:
        RouletteResult with outcome
    """
    # Get current balance
    balance = await wallet_service.get_balance(user_id)
    
    # Validate bet
    if bet_amount < 0:
        return RouletteResult(
            success=False,
            message="Ставка должна быть положительной, гений.",
            shot=False,
            points_change=0,
            new_balance=balance,
            bet_amount=bet_amount,
            error_code="INVALID_BET"
        )
    
    if bet_amount > 0 and balance < bet_amount:
        return RouletteResult(
            success=False,
            message=f"Недостаточно монет. У тебя {balance}, нужно {bet_amount}",
            shot=False,
            points_change=0,
            new_balance=balance,
            bet_amount=bet_amount,
            error_code="INSUFFICIENT_BALANCE"
        )
    
    # Spin the chamber - 1/6 chance of shot
    chamber = random.randint(0, 5)
    shot = (chamber == 0)
    
    # Roulette settings
    SHOT_PENALTY = 50
    SURVIVAL_REWARD = 10
    
    # Messages
    SHOT_MESSAGES = [
        "💥 БАХ! Пуля нашла твою голову. -{points} очков. Не повезло, бро.",
        "💀 Щёлк... БАМ! Ты труп. -{points} очков. Классика жанра.",
        "🔫 Барабан крутится... ВЫСТРЕЛ! -{points} очков. Олег скорбит.",
    ]
    SURVIVAL_MESSAGES = [
        "😮‍💨 Щёлк... пусто! Ты выжил, везунчик. +{points} очков.",
        "🍀 Барабан крутится... тишина. Живой! +{points} очков.",
        "😎 Холодный пот, но ты цел. +{points} очков. Красавчик.",
    ]
    
    if bet_amount > 0:
        # Betting mode
        if shot:
            points_change = -bet_amount
            message = random.choice(SHOT_MESSAGES).format(points=bet_amount)
            await wallet_service.deduct_balance(user_id, bet_amount, "roulette loss")
        else:
            # Event Modifier: DOUBLE_COINS
            reward = bet_amount
            if await event_service.has_modifier(EventModifier.DOUBLE_COINS):
                reward *= 2
                message = f"🔥 ИВЕНТ x2! {random.choice(SURVIVAL_MESSAGES).format(points=reward)}"
            else:
                message = random.choice(SURVIVAL_MESSAGES).format(points=reward)
            
            points_change = reward
            await wallet_service.add_balance(user_id, reward, "roulette win")
    else:
        # Standard mode with fixed points
        if shot:
            points_change = -SHOT_PENALTY
            message = random.choice(SHOT_MESSAGES).format(points=SHOT_PENALTY)
            # Don't go below 0
            deduct_amount = min(SHOT_PENALTY, balance)
            if deduct_amount > 0:
                await wallet_service.deduct_balance(user_id, deduct_amount, "roulette shot")
        else:
            # Event Modifier: DOUBLE_COINS
            reward = SURVIVAL_REWARD
            if await event_service.has_modifier(EventModifier.DOUBLE_COINS):
                reward *= 2
                message = f"🔥 ИВЕНТ x2! {random.choice(SURVIVAL_MESSAGES).format(points=reward)}"
            else:
                message = random.choice(SURVIVAL_MESSAGES).format(points=reward)
                
            points_change = reward
            await wallet_service.add_balance(user_id, reward, "roulette survival")
    
    new_balance = await wallet_service.get_balance(user_id)
    
    return RouletteResult(
        success=True,
        message=message,
        shot=shot,
        points_change=points_change,
        new_balance=new_balance,
        bet_amount=bet_amount
    )


async def flip_coin_async(user_id: int, bet_amount: int, choice: str) -> CoinFlipResult:
    """
    Play Coin Flip with unified wallet balance.
    
    Args:
        user_id: Telegram user ID
        bet_amount: Amount to bet
        choice: "heads" or "tails"
        
    Returns:
        CoinFlipResult with outcome
    """
    # Get current balance
    balance = await wallet_service.get_balance(user_id)
    
    # Validate choice
    choice = choice.lower().strip()
    if choice not in ("heads", "tails"):
        return CoinFlipResult(
            success=False,
            message="Выбери heads или tails, гений.",
            choice=choice,
            result="",
            won=False,
            bet_amount=bet_amount,
            balance_change=0,
            new_balance=balance,
            error_code="INVALID_CHOICE"
        )
    
    # Validate bet
    if bet_amount <= 0:
        return CoinFlipResult(
            success=False,
            message="Ставка должна быть положительной, гений.",
            choice=choice,
            result="",
            won=False,
            bet_amount=bet_amount,
            balance_change=0,
            new_balance=balance,
            error_code="INVALID_BET"
        )
    
    if balance < bet_amount:
        return CoinFlipResult(
            success=False,
            message=f"Недостаточно монет. У тебя {balance}, нужно {bet_amount}",
            choice=choice,
            result="",
            won=False,
            bet_amount=bet_amount,
            balance_change=0,
            new_balance=balance,
            error_code="INSUFFICIENT_BALANCE"
        )
    
    # Flip the coin - 50/50
    coin_result = "heads" if random.random() < 0.5 else "tails"
    won = (choice == coin_result)
    
    # Messages
    WIN_MESSAGES = [
        "🪙 {result}! Угадал, красавчик. +{amount} очков.",
        "💰 Монетка говорит {result}. Ты в плюсе на {amount}!",
        "🎯 Бинго! {result}. Забирай свои {amount} очков.",
    ]
    LOSE_MESSAGES = [
        "🪙 {result}! Мимо. -{amount} очков.",
        "💸 Монетка говорит {result}. Ты проиграл {amount}.",
        "😬 Не угадал. {result}. -{amount} очков.",
    ]
    
    if won:
        # Event Modifier: DOUBLE_COINS
        reward = bet_amount
        if await event_service.has_modifier(EventModifier.DOUBLE_COINS):
            reward *= 2
            message = f"🔥 ИВЕНТ x2! {random.choice(WIN_MESSAGES).format(result=coin_result.capitalize(), amount=reward)}"
        else:
            message = random.choice(WIN_MESSAGES).format(result=coin_result.capitalize(), amount=reward)
            
        balance_change = reward
        await wallet_service.add_balance(user_id, reward, "coinflip win")
    else:
        balance_change = -bet_amount
        message = random.choice(LOSE_MESSAGES).format(result=coin_result.capitalize(), amount=bet_amount)
        await wallet_service.deduct_balance(user_id, bet_amount, "coinflip loss")
    
    new_balance = await wallet_service.get_balance(user_id)
    
    return CoinFlipResult(
        success=True,
        message=message,
        choice=choice,
        result=coin_result,
        won=won,
        bet_amount=bet_amount,
        balance_change=balance_change,
        new_balance=new_balance
    )


# Справка по играм
GAMES_HELP = """
🎮 <b>Мини-игры Олега — Полный гайд</b>

<b>📏 /grow — Выращивание</b>
Увеличь свой "размер" на 1-20 см.
• Кулдаун: 12-24 часа (рандом)
• Чем больше размер — тем выше ранг
• Пример: <code>/grow</code>

<b>🔫 /roulette — Русская рулетка</b>
Крути барабан, испытай удачу!
• 1/6 шанс "выстрела" — теряешь 50 очков
• 5/6 шанс выжить — получаешь 10 очков
• Пример: <code>/roulette</code>

<b>🪙 /coinflip — Монетка</b>
Ставь на орла или решку!
• 50/50 вероятность
• Выигрыш: удвоение ставки
• Примеры:
  <code>/coinflip 50 орёл</code> — ставка 50 на орла
  <code>/coinflip 100 решка</code> — ставка 100 на решку
  <code>/coinflip 50 heads</code> — английский вариант

<b>⚔️ /challenge — PvP с согласием</b>
Вызови другого игрока на дуэль!
• Соперник должен принять вызов
• Ставки списываются только при согласии
• Таймаут: 5 минут
• Пример: <code>/challenge @username 100</code>

<b>⚔️ /pvp — Быстрая дуэль</b>
Сразись с другим игроком!
• Победитель забирает 10-30% размера проигравшего
• Победа: +5 репутации, поражение: -2
• Примеры:
  <code>/pvp @username</code> — по нику
  Или ответь на сообщение соперника и напиши <code>/pvp</code>

<b>🎰 /casino — Слоты</b>
Крути барабаны, выигрывай монеты!
• Ставка: 1-1000 монет (по умолчанию 10)
• 3 одинаковых = x5 (джекпот!)
• 2 одинаковых = x2
• Примеры:
  <code>/casino</code> — ставка 10
  <code>/casino 100</code> — ставка 100

<b>🏆 /top — Топ игроков</b>
Показывает топ-10 по размеру.

<b>⭐ /top_rep — Топ по репутации</b>
Топ-10 по репутации (растёт от побед).

<b>👤 /profile — Твой профиль</b>
Вся статистика: размер, ранг, монеты, победы.

<b>💡 Советы новичкам:</b>
1. Начни с /grow — получи первые сантиметры
2. /roulette — быстрый способ заработать (или потерять)
3. /coinflip — классика азарта
4. /challenge — честный PvP со ставками
5. Выполняй квесты (/quests) для бонусов

<i>Вопросы? Напиши "помоги с играми" — я объясню!</i>
"""

# Константы для баланса игр
GROW_MIN = 5
GROW_MAX = 30
GROW_COOLDOWN_MIN_HOURS = 12
GROW_COOLDOWN_MAX_HOURS = 24

CASINO_MIN_BET = 1
CASINO_MAX_BET = 1000
CASINO_DEFAULT_BET = 10

PVP_STEAL_MIN_PCT = 10
PVP_STEAL_MAX_PCT = 30

# Словарь рангов для игры /grow (ПИПИСОМЕТР 🍆)
RANKS = [
    # === МИКРО МИР (0-10 см) ===
    (1, "Квантовая неопределенность"),
    (2, "Нано-технология"),
    (3, "Молекулярный уровень"),
    (4, "Биологическая погрешность"),
    (5, "Почти заметный"),
    (6, "Микро-боец"),
    (7, "Компактный размер"),
    (8, "Карманный вариант"),
    (9, "Начинающий гигант"),
    (10, "Скромный старт"),

    # === СТАРТОВАЯ ЛИГА (11-20 см) ===
    (11, "Разминочный"),
    (12, "Школьная линейка"),
    (13, "Чертова дюжина"),
    (14, "Батарейка AA"),
    (15, "Стандартный карандаш"),
    (16, "Юношеский максимализм"),
    (17, "Почти совершеннолетний"),
    (18, "Паспортный размер"),
    (19, "Без пяти минут гигант"),
    (20, "Двадцаточка!"),

    # === ЛЮБИТЕЛЬСКАЯ ЛИГА (21-30 см) ===
    (21, "Блэкджек (21)"),
    (22, "Два гуся"),
    (23, "Майкл Джордан"),
    (24, "Сутки в см"),
    (25, "Четвертак"),
    (26, "Полумарафон"),
    (27, "Клуб 27"),
    (28, "Февральский"),
    (29, "Високосный"),
    (30, "Тридцатка! Уверенный"),

    # === ПРОФЕССИОНАЛЫ (31-40 см) ===
    (31, "31-й регион"),
    (32, "32 бита"),
    (33, "Возраст Христа"),
    (34, "Rule 34"),
    (35, "Зрелый возраст"),
    (36, "36 и 6"),
    (37, "37.2 по утрам"),
    (38, "38 попугаев"),
    (39, "В шаге от сорока"),
    (40, "СОРОКОВНИК"),

    # === МАСТЕРА (41-50 см) ===
    (41, "41-й размер"),
    (42, "Ответ на главный вопрос"),
    (43, "Калибр 43"),
    (44, "Стул"),
    (45, "Ягодка опять"),
    (46, "Хромосомный набор"),
    (47, "АК-47"),
    (48, "Двое суток"),
    (49, "Почти юбилей"),
    (50, "ПОЛТИННИК! Солидно"),

    # === ГРАНД-МАСТЕРА (51-60 см) ===
    (51, "Зона 51"),
    (52, "Колода карт"),
    (53, "Холостяк"),
    (54, "Студийный формат"),
    (55, "Две пятерки"),
    (56, "Симфония"),
    (57, "Спутник"),
    (58, "Пробный"),
    (59, "Предпенсионный"),
    (60, "ШЕСТИДЕСЯТНИК"),

    # === ЛЕГЕНДЫ (61-70 см) ===
    (61, "Код региона"),
    (62, "Мудрость"),
    (63, "АМГ"),
    (64, "Nintendo 64"),
    (65, "Юбилейный"),
    (66, "Трасса 66"),
    (67, "Лето любви"),
    (68, "Почти найс"),
    (69, "🔥 НАЙС 🔥"),
    (70, "СЕМИДЕСЯТНИК"),

    # === ТИТАНЫ (71-80 см) ===
    (71, "Тульский"),
    (72, "Высота"),
    (73, "Лучший год"),
    (74, "Калашников"),
    (75, "Три четверти"),
    (76, "Fallout"),
    (77, "Две семерки"),
    (78, "Винил"),
    (79, "Золото"),
    (80, "ВОСЬМИДЕСЯТНИК"),

    # === БОГИ (81-90 см) ===
    (81, "Девять на девять"),
    (82, "Год собаки"),
    (83, "Уровень"),
    (84, "1984"),
    (85, "Назад в будущее"),
    (86, "Тигр"),
    (87, "Кролик"),
    (88, "Две бесконечности"),
    (89, "Дракон"),
    (90, "ДЕВЯНОСТНИК"),

    # === СВЕРХРАЗУМЫ (91-100 см) ===
    (91, "СССР"),
    (92, "Барселона"),
    (93, "Ростов"),
    (94, "Джастин"),
    (95, "Windows 95"),
    (96, "Обратный найс"),
    (97, "Брат 2"),
    (98, "Google"),
    (99, "Почти сотка"),
    (100, "💯 МЕТРОВЫЙ ГИГАНТ 💯"),

    # === КОСМОС (101-150 см) ===
    (101, "Далматинец"),
    (105, "Сверх нормы"),
    (110, "110% Мощи"),
    (115, "Метр с кепкой"),
    (120, "Длинномер"),
    (125, "Четверть второго метра"),
    (130, "Негабарит"),
    (135, "Шлагбаум"),
    (140, "Телескоп"),
    (145, "Анаконда"),
    (150, "🍆 ПОЛТОРА МЕТРА 🍆"),

    # === ГАЛАКТИКА (151-200 см) ===
    (155, "Снайперская винтовка"),
    (160, "Средний рост человека"),
    (165, "Выше среднего"),
    (170, "Модельный рост"),
    (175, "Баскетболист"),
    (180, "Высокий стиль"),
    (185, "Охранник"),
    (190, "Викинг"),
    (195, "Гигачад"),
    (200, "🏆 ДВА МЕТРА МОЩИ 🏆"),

    # === ВСЕЛЕННАЯ (201-300 см) ===
    (210, "Дверной проем"),
    (220, "Самый высокий человек"),
    (230, "Потолок хрущевки"),
    (240, "Грузовик"),
    (250, "Фура"),
    (260, "Автобус"),
    (270, "Вагон метро"),
    (280, "Кит"),
    (290, "Девятиэтажка"),
    (300, "🔥 ТРИ МЕТРА ХАРИЗМЫ 🔥"),

    # === БЕСКОНЕЧНОСТЬ (301+ см) ===
    (350, "Лох-Несское чудовище"),
    (400, "🚀 ЧЕТЫРЕ МЕТРА 🚀"),
    (420, "🌿 BLAZE IT 🌿"),
    (450, "Лимузин"),
    (500, "💎 ПОЛТЫСЯЧИ 💎"),
    (600, "Кран башенный"),
    (666, "😈 ДЕМОНИЧЕСКИЙ 😈"),
    (700, "Боинг 747"),
    (777, "🎰 ДЖЕКПОТ 🎰"),
    (800, "Бурдж-Халифа"),
    (900, "Эверест"),
    (999, "За шаг до величия"),
    (1000, "🔥🔥🔥 КИЛОМЕТР АВТОРИТЕТА 🔥🔥🔥"),
    (float('inf'), "∞ БЕСКОНЕЧНОСТЬ ∞")
]


# Russian to English coinflip choice mapping (Requirements 8.1)
COINFLIP_CHOICE_MAP = {
    # Russian variants
    "орёл": "heads",
    "орел": "heads",  # Without ё
    "решка": "tails",
    # English variants (pass through)
    "heads": "heads",
    "tails": "tails",
    "head": "heads",
    "tail": "tails",
}


def map_coinflip_choice(choice: str) -> str:
    """
    Map Russian or English coinflip choice to internal heads/tails.
    
    Requirements 8.1: Accept Russian input ("орёл"/"решка")
    
    Args:
        choice: User's choice in Russian or English
        
    Returns:
        Normalized choice: "heads" or "tails", or original if not recognized
    """
    if choice is None:
        return ""
    return COINFLIP_CHOICE_MAP.get(choice.lower().strip(), choice)


def get_rank_by_size(size_cm: int) -> str:
    """
    Возвращает ранг по размеру "пиписи".

    Args:
        size_cm: Размер в сантиметрах

    Returns:
        Название ранга
    """
    for threshold, rank_name in RANKS:
        if size_cm <= threshold:
            return rank_name
    return RANKS[-1][1]  # Возвращаем последний ранг, если размер больше всех порогов


async def ensure_user(tg_user) -> User:
    """
    Убедиться, что пользователь существует в БД.

    Если пользователь не существует, создает записи:
    - User (базовая информация)
    - GameStat (статистика игр, "размер")
    - Wallet (виртуальная валюта, начальный баланс 100)

    Args:
        tg_user: Объект пользователя Telegram

    Returns:
        User объект
    """
    async_session = get_session()
    async with async_session() as session:
        # Поиск существующего пользователя
        res = await session.execute(
            select(User).where(User.tg_user_id == tg_user.id)
        )
        user = res.scalars().first()
        if not user:
            user = User(
                tg_user_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )
            session.add(user)
            await session.flush()

        # Убедиться в наличии GameStat
        res2 = await session.execute(
            select(GameStat).where(
                GameStat.tg_user_id == tg_user.id
            )
        )
        gs = res2.scalars().first()
        if not gs:
            gs = GameStat(
                user_id=user.id,
                tg_user_id=tg_user.id,
                username=tg_user.username,
                size_cm=0
            )
            session.add(gs)
        else:
            # Обновить никнейм если изменился
            gs.username = tg_user.username

        # Убедиться в наличии Wallet
        res3 = await session.execute(
            select(Wallet).where(Wallet.user_id == user.id)
        )
        w = res3.scalars().first()
        if not w:
            w = Wallet(user_id=user.id, balance=100)
            session.add(w)

        await session.commit()
        return user


@router.message(Command("games_help"))
async def cmd_games_help(msg: Message):
    """Команда /games_help — справка по всем мини-играм.
    
    Note: /games command is now handled by game_hub.py for the Game Hub UI.
    """
    await msg.reply(GAMES_HELP, parse_mode="HTML")
    logger.info(f"Games help requested by @{msg.from_user.username or msg.from_user.id}")


def update_grow_history(gs: GameStat, gain: int) -> None:
    """
    Update grow_history with the latest growth data.
    
    Keeps last 7 days of growth data for sparkline generation.
    Requirements: 7.4
    
    Args:
        gs: GameStat object to update
        gain: The amount of growth in this session
    """
    from datetime import date
    import copy
    
    today = date.today().isoformat()
    
    # Initialize history if None - create deep copy to ensure mutability
    # SQLAlchemy JSON columns need explicit reassignment to detect changes
    if gs.grow_history is None:
        history = []
    else:
        # Deep copy to ensure we're working with mutable data
        history = copy.deepcopy(list(gs.grow_history))
    
    # Check if we already have an entry for today
    today_index = None
    for i, entry in enumerate(history):
        if entry.get("date") == today:
            today_index = i
            break
    
    if today_index is not None:
        # Update existing entry for today (create new dict to ensure change detection)
        history[today_index] = {
            "date": today,
            "size": gs.size_cm,
            "change": history[today_index].get("change", 0) + gain
        }
    else:
        # Add new entry for today
        history.append({
            "date": today,
            "size": gs.size_cm,
            "change": gain
        })
    
    # Keep only last 7 days
    history = sorted(history, key=lambda x: x.get("date", ""), reverse=True)[:7]
    history = sorted(history, key=lambda x: x.get("date", ""))  # Sort chronologically
    
    # Explicit reassignment to trigger SQLAlchemy change detection
    gs.grow_history = history


@router.message(Command("cancel", "отмена"))
async def cmd_cancel(msg: Message):
    """Отменить текущую игру."""
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    session = await state_manager.get_session(user_id, chat_id)
    if not session:
        return await msg.reply("🎮 У тебя нет активных игр.")
    
    game_type = session.game_type
    await state_manager.end_game(user_id, chat_id)
    
    await msg.reply(f"✅ Игра {game_type} отменена. Можешь начать новую!")
    logger.info(f"User {user_id} cancelled game {game_type} in chat {chat_id}")


@router.message(F.text.startswith("/grow"))
async def cmd_grow(msg: Message):
    """
    Команда /grow — увеличить "пиписю".

    Случайное увеличение размера (1-20 см) с кулдауном.
    """
    from app.services.inventory import inventory_service, ItemType as InvItemType
    
    async_session = get_session()
    user = await ensure_user(msg.from_user) # Get the User object here
    
    # Check if PP_CAGE is active (Requirements 10.4)
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    if await inventory_service.has_active_item(user_id, chat_id, InvItemType.PP_CAGE):
        return await msg.reply(
            "🔒 Клетка не даёт расти! Сними её через /inventory или подожди пока истечёт."
        )
    
    async with async_session() as session:
        res = await session.execute(
            select(GameStat).where(
                GameStat.tg_user_id == msg.from_user.id
            )
        )
        gs = res.scalars().first()
        now = utc_now()
        
        # Получаем статистику для сообщения (нужно и для кулдауна, и для успеха)
        res2 = await session.execute(
            select(GameStat).order_by(GameStat.size_cm.desc())
        )
        all_stats = res2.scalars().all()
        rank = next(
            (i + 1 for i, s in enumerate(all_stats)
             if s.tg_user_id == msg.from_user.id),
            1
        )
        size_rank = get_rank_by_size(gs.size_cm)

        # Ensure both datetimes are comparable (handle naive vs aware)
        next_grow = gs.next_grow_at
        if next_grow and next_grow.tzinfo is None:
            from datetime import timezone
            next_grow = next_grow.replace(tzinfo=timezone.utc)
            
        if next_grow and next_grow > now:
            delta = next_grow - now
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes = remainder // 60
            
            TIMEOUT_MESSAGES = [
                f"⏳ Подожди ещё {hours}ч {minutes}м, не спеши, чемпион.",
                f"🕒 Рано! Твой инструмент отдыхает. Ещё {hours}ч {minutes}м.",
                f"💤 Дай ему отдохнуть! Приходи через {hours}ч {minutes}м.",
                f"🛑 Стоп-машина! Перегрев. Остываем {hours}ч {minutes}м.",
                f"⏱️ Всему своё время. Таймер: {hours}ч {minutes}м."
            ]
            
            # Добавляем инфо о текущем статусе
            msg_text = (
                f"{random.choice(TIMEOUT_MESSAGES)}\n"
                f"📏 Текущий: {gs.size_cm} см\n"
                f"🏆 Место: #{rank}/{len(all_stats)}\n"
                f"📋 /games"
            )
            return await msg.reply(msg_text)
            
        # Progressive growth system with multiple thresholds
        current_size = max(1, gs.size_cm)
        
        # Balance: 10% chance of failure (0 cm), 3% chance of shrinkage
        roll = random.random()
        if roll < 0.03:  # 3% shrinkage
            if current_size < 100:
                gain = -random.randint(2, 8)
            elif current_size < 500:
                shrink_percent = random.uniform(0.01, 0.03)
                gain = -max(2, min(50, int(current_size * shrink_percent)))
            else:
                shrink_percent = random.uniform(0.02, 0.05)
                gain = -max(5, min(100, int(current_size * shrink_percent)))
            failure_msg = "💀 <b>УСАДКА!</b> Твой писюн уменьшился!"
        elif roll < 0.13:  # 10% failure
            gain = 0
            failure_msg = "😐 <b>НЕУДАЧА!</b> Ничего не выросло..."
        else:
            # Normal growth (87% chance)
            if current_size < 100:
                # Early game: fixed growth (5-30 cm)
                gain = random.randint(GROW_MIN, GROW_MAX)
            elif current_size < 500:
                # Mid game: 3%-8% growth
                grow_percent = random.uniform(0.03, 0.08)
                gain = max(5, min(150, int(current_size * grow_percent)))
            elif current_size < 2000:
                # Late game: 5%-12% growth
                grow_percent = random.uniform(0.05, 0.12)
                gain = max(10, min(300, int(current_size * grow_percent)))
            else:
                # End game: 8%-15% growth
                grow_percent = random.uniform(0.08, 0.15)
                gain = max(20, min(500, int(current_size * grow_percent)))
            failure_msg = None
        
        # Check for Omega cream boost (Requirements: grow_boost effect)
        if gain > 0:  # Only apply boost if positive growth
            # Event Modifier: GROW_BOOST
            if await event_service.has_modifier(EventModifier.GROW_BOOST):
                gain = int(gain * 1.5)
                logger.info(f"User {user_id} used event GROW_BOOST: gain increased to {gain}")
            
            try:
                from app.handlers.inventory import get_booster_effect, consume_booster_effect
                grow_boost = await consume_booster_effect(user_id, chat_id, "grow_boost")
                if grow_boost:
                    multiplier = grow_boost if isinstance(grow_boost, (int, float)) else 2.0
                    old_gain = gain
                    gain = int(gain * multiplier)
                    logger.info(f"User {user_id} used grow boost: {old_gain} -> {gain} (x{multiplier})")
            except Exception as e:
                logger.debug(f"No grow boost check: {e}")
        
        cooldown_hours = random.randint(
            GROW_COOLDOWN_MIN_HOURS, GROW_COOLDOWN_MAX_HOURS
        )
        
        # Check for grow accelerator (reduces cooldown by 6 hours)
        try:
            from app.handlers.inventory import consume_booster_effect
            grow_accel = await consume_booster_effect(user_id, chat_id, "grow_accelerator")
            if grow_accel:
                cooldown_reduction = grow_accel.get("cooldown_reduction_hours", 6)
                cooldown_hours = max(1, cooldown_hours - cooldown_reduction)
                logger.info(f"User {user_id} used grow accelerator: cooldown reduced by {cooldown_reduction}h")
        except Exception as e:
            logger.debug(f"No grow accelerator check: {e}")
        
        gs.size_cm += gain
        gs.grow_count += 1
        gs.next_grow_at = now + timedelta(hours=cooldown_hours)
        
        # Update grow history for sparkline (Requirements 7.4)
        update_grow_history(gs, gain)
        
        await session.commit()

        new_achievements = await check_and_award_achievements(session, msg.bot, user, gs, "grow")
        for achievement in new_achievements:
            await msg.answer(f"🎉 Новое достижение: {achievement}!")
        
        updated_quests = await check_and_update_quests(session, user, "grow")
        for quest in updated_quests:
            await msg.answer(f"✅ Выполнили квест: {quest.name}! Награда: {quest.reward_amount} {quest.reward_type}!")

        # Update tournament score for grow (Requirement 10.1)
        try:
            await tournament_service.update_score(
                user_id=msg.from_user.id,
                discipline=TournamentDiscipline.GROW,
                delta=gain,
                username=msg.from_user.username
            )
        except Exception as e:
            logger.warning(f"Failed to update tournament score: {e}")

        # Обновляем рейтинг и размер для отображения
        size_rank = get_rank_by_size(gs.size_cm)
        # Ранг может измениться из-за других игроков, но для сообщения примерно сойдет старый + дельта
        # Или можно пересчитать, но это лишний запрос.
        
        # Generate sparkline if we have enough history (Requirements 7.1)
        sparkline_bytes = None
        if gs.grow_history and len(gs.grow_history) >= 2:
            try:
                sparkline_bytes = sparkline_generator.generate(gs.grow_history)
            except Exception as e:
                logger.warning(f"Failed to generate sparkline: {e}")
        
        # Format: +5 см 📈 Текущий: 109 см Ранг: 110% хуя Место: #8/57 Кулдаун: 20ч 📋 /games
        
        if failure_msg:
             reply_text = f"{failure_msg} ({gain} см)\n"
        else:
            reply_text = f"+{gain} см 📈 "
            
        reply_text += (
            f"Текущий: {gs.size_cm} см\n"
            f"Ранг: {size_rank}\n"
            f"Место: #{rank}/{len(all_stats)} "
            f"Кулдаун: {cooldown_hours}ч\n"
            f"📋 /games"
        )
        
        # Send with sparkline image if available (Requirements 7.1)
        if sparkline_bytes:
            photo = BufferedInputFile(sparkline_bytes, filename="sparkline.png")
            await msg.reply_photo(photo=photo, caption=reply_text)
        else:
            await msg.reply(reply_text)
        
        logger.info(
            f"Grow: @{msg.from_user.username} "
            f"+{gain} cm (total: {gs.size_cm}, rank: {size_rank})"
        )


# Special titles for top rankings (Requirements 7.2, 7.3)
TITLE_LARGEST = "🧠 Гигант мысли"
TITLE_SMALLEST = "🔬 Нано-технолог"


def get_special_title(rank: int, total: int, is_largest: bool = False, is_smallest: bool = False) -> str:
    """
    Get special title for top rankings.
    
    Requirements: 7.2, 7.3
    
    Args:
        rank: Player's rank (1-based)
        total: Total number of players
        is_largest: True if this is the largest size
        is_smallest: True if this is the smallest size
        
    Returns:
        Special title string or empty string
    """
    if is_largest:
        return f" {TITLE_LARGEST}"
    if is_smallest:
        return f" {TITLE_SMALLEST}"
    return ""


def get_diverse_title(rank: int, player: GameStat, smallest_id: int, top10: list) -> str:
    """
    Generate diverse special titles based on rank, stats, and characteristics.
    
    Args:
        rank: Player's rank (1-based)
        player: GameStat object
        smallest_id: ID of the smallest player
        top10: List of top 10 players
        
    Returns:
        Special title string
    """
    # Primary titles for top positions
    if rank == 1:
        return f" {TITLE_LARGEST}"
    
    if player.tg_user_id == smallest_id and player.size_cm > 0:
        return f" {TITLE_SMALLEST}"
    
    # Diverse titles based on characteristics
    if rank == 2:
        # Check if close to leader
        leader_size = top10[0].size_cm
        if player.size_cm >= leader_size * 0.95:
            return " 👑 Претендент на трон"
        return " 🥈 Серебряный гигант"
    
    if rank == 3:
        return " 🥉 Бронзовый титан"
    
    # PvP-based titles
    if player.pvp_wins > 50:
        return " ⚔️ Боевой ветеран"
    elif player.pvp_wins > 20:
        return " 🗡️ Дуэлянт"
    
    # Growth-based titles
    if player.grow_count > 100:
        return " 🌟 Мастер роста"
    elif player.grow_count > 50:
        return " 🌱 Упорный садовник"
    
    # Casino-based titles
    if player.casino_jackpots > 10:
        return " 🎰 Везунчик казино"
    elif player.casino_jackpots > 5:
        return " 🍀 Счастливчик"
    
    # League-based titles
    if player.league == "elite":
        return " 💎 Элитный боец"
    elif player.league == "quantum":
        return " ⚡ Квантовый воин"
    
    # ELO-based titles
    if player.elo_rating > 1500:
        return " 🏅 Высокий рейтинг"
    elif player.elo_rating > 1200:
        return " 📊 Опытный игрок"
    
    # Reputation-based titles
    if player.reputation > 100:
        return " ⭐ Уважаемый"
    elif player.reputation < -50:
        return " 💀 Изгой"
    
    # Growth history analysis
    if player.grow_history and len(player.grow_history) >= 5:
        recent_changes = [entry.get("change", 0) for entry in player.grow_history[-5:]]
        total_change = sum(recent_changes)
        if total_change > 20:
            return " 🚀 Стремительный рост"
        elif total_change < -20:
            return " 📉 В упадке"
    
    # Default titles by rank
    rank_titles = {
        4: " 🎯 Меткий стрелок",
        5: " 🔥 Огненный дух",
        6: " ⚡ Электрический разряд",
        7: " 🌊 Морская волна",
        8: " 🌪️ Вихрь хаоса",
        9: " 🎭 Театральный",
        10: " 🎪 Цирковой артист"
    }
    
    return rank_titles.get(rank, "")


@router.message(F.text.startswith("/top"))
async def cmd_top(msg: Message, bot: Bot):
    """
    Команда /top — показать топ-10 игроков с общим графиком роста и расширенной статистикой.
    
    Features:
    - Multi-line growth chart with all top 10 players (different colors)
    - Diverse special titles based on rank and characteristics
    - Overall statistics: average size, total growth, trend analysis
    - Visual indicators and medals
    
    Requirements: 7.1, 7.2, 7.3, 7.4
    """
    from app.services.top_chart import top_chart_generator
    
    async_session = get_session()
    async with async_session() as session:
        # Get top 10 by size (descending)
        res = await session.execute(select(GameStat).order_by(GameStat.size_cm.desc()).limit(10))
        top10 = res.scalars().all()
        if not top10:
            return await msg.reply("Пусто. Никто не растил свою гордость.")
        
        # Get the smallest player for special title
        res_smallest = await session.execute(
            select(GameStat).where(GameStat.size_cm > 0).order_by(GameStat.size_cm.asc()).limit(1)
        )
        smallest = res_smallest.scalars().first()
        smallest_id = smallest.tg_user_id if smallest else None
        
        # Calculate overall statistics
        total_size = sum(s.size_cm for s in top10)
        avg_size = total_size // len(top10)
        total_grows = sum(s.grow_count for s in top10)
        max_size = top10[0].size_cm
        min_size_in_top = top10[-1].size_cm
        
        # Analyze growth trends
        positive_trends = 0
        negative_trends = 0
        stable_trends = 0
        for s in top10:
            if s.grow_history and len(s.grow_history) >= 2:
                recent_change = sum(entry.get("change", 0) for entry in s.grow_history[-3:])
                if recent_change > 0:
                    positive_trends += 1
                elif recent_change < 0:
                    negative_trends += 1
                else:
                    stable_trends += 1
        
        # Build top 10 list with diverse titles
        lines = ["🏆 ТОП-10 ГИГАНТОВ МЫСЛИ\n"]
        
        for i, s in enumerate(top10, start=1):
            name = s.username or str(s.tg_user_id)
            size_rank = get_rank_by_size(s.size_cm)
            
            # Generate diverse special titles
            special_title = get_diverse_title(i, s, smallest_id, top10)
            
            # Generate trend indicator from history
            trend = ""
            if s.grow_history and len(s.grow_history) >= 2:
                recent_changes = [entry.get("change", 0) for entry in s.grow_history[-3:]]
                avg_change = sum(recent_changes) / len(recent_changes)
                if avg_change > 2:
                    trend = " 📈"
                elif avg_change < -2:
                    trend = " 📉"
                elif avg_change > 0:
                    trend = " ↗️"
                elif avg_change < 0:
                    trend = " ↘️"
                else:
                    trend = " ➡️"
            
            # Format line with medal emojis for top 3
            medal = ""
            if i == 1:
                medal = "🥇 "
            elif i == 2:
                medal = "🥈 "
            elif i == 3:
                medal = "🥉 "
            else:
                medal = f"{i}. "
            
            lines.append(
                f"{medal}{name}: {s.size_cm} см{trend}\n"
                f"   └ {size_rank}{special_title}"
            )
        
        # Add overall statistics section
        stats_section = (
            f"\n\n📊 ОБЩАЯ СТАТИСТИКА\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Игроков в топе: {len(top10)}\n"
            f"📏 Средний размер: {avg_size} см\n"
            f"📐 Диапазон: {min_size_in_top}-{max_size} см\n"
            f"🌱 Всего ростов: {total_grows}\n"
            f"📈 Растут: {positive_trends} | ➡️ Стабильно: {stable_trends} | 📉 Падают: {negative_trends}\n"
        )
        
        # Add smallest player info if not in top 10
        smallest_line = ""
        if smallest and smallest.tg_user_id not in [s.tg_user_id for s in top10]:
            smallest_name = smallest.username or str(smallest.tg_user_id)
            smallest_line = f"\n🔬 Нано-технолог: {smallest_name} ({smallest.size_cm} см)"
        
        text = "\n".join(lines) + stats_section + smallest_line + "\n\n📋 /games"
        
        # Generate multi-line chart for all top 10 players
        try:
            chart_bytes = top_chart_generator.generate_top10_chart(top10)
            if chart_bytes:
                photo = BufferedInputFile(chart_bytes, filename="top10_chart.png")
                await bot.send_photo(
                    chat_id=msg.chat.id,
                    message_thread_id=msg.message_thread_id,
                    photo=photo,
                    caption=text
                )
                return
        except Exception as e:
            logger.warning(f"Failed to generate top10 chart: {e}")
        
        # Fallback: send text only
        await msg.reply(text)


@router.message(F.text.startswith("/top_rep"))
async def cmd_top_rep(msg: Message):
    async_session = get_session()
    async with async_session() as session:
        res = await session.execute(select(GameStat).order_by(GameStat.reputation.desc()).limit(10))
        top10 = res.scalars().all()
        if not top10:
            return await msg.reply("Пусто. Ни у кого нет репутации.")
        lines = []
        for i, s in enumerate(top10, start=1):
            name = s.username or str(s.tg_user_id)
            lines.append(f"{i}. {name}: {s.reputation} репутации")
        await msg.reply(
            "⭐ Топ-10 по репутации:\n" + "\n".join(lines) +
            "\n📋 /games"
        )


@router.message(F.text.startswith("/top_grow"))
async def cmd_top_grow(msg: Message, bot: Bot):
    """
    Команда /top_grow — топ-10 игроков по количеству ростов с графиками.
    
    Features:
    - Top 10 players by grow_count (most active growers)
    - Multi-line growth chart showing activity
    - Statistics: total grows, average per player
    - Special titles for most active players
    """
    from app.services.top_chart import top_chart_generator
    
    async_session = get_session()
    async with async_session() as session:
        # Get top 10 by grow_count (descending)
        res = await session.execute(
            select(GameStat).order_by(GameStat.grow_count.desc()).limit(10)
        )
        top10 = res.scalars().all()
        if not top10:
            return await msg.reply("Пусто. Никто не растил свою гордость.")
        
        # Calculate statistics
        total_grows = sum(s.grow_count for s in top10)
        avg_grows = total_grows // len(top10)
        max_grows = top10[0].grow_count
        
        # Calculate total size for comparison
        total_size = sum(s.size_cm for s in top10)
        avg_size = total_size // len(top10)
        
        # Build top 10 list
        lines = ["🌱 ТОП-10 ПО КОЛИЧЕСТВУ РОСТОВ\n"]
        
        for i, s in enumerate(top10, start=1):
            name = s.username or str(s.tg_user_id)
            size_rank = get_rank_by_size(s.size_cm)
            
            # Special titles for grow leaders
            special_title = ""
            if i == 1:
                special_title = " 👑 Король роста"
            elif i == 2:
                special_title = " 🥈 Мастер культивации"
            elif i == 3:
                special_title = " 🥉 Опытный садовник"
            elif s.grow_count > 200:
                special_title = " 🌟 Легенда роста"
            elif s.grow_count > 100:
                special_title = " ⭐ Профессионал"
            elif s.grow_count > 50:
                special_title = " 🌿 Энтузиаст"
            
            # Efficiency indicator (size per grow)
            efficiency = s.size_cm / s.grow_count if s.grow_count > 0 else 0
            efficiency_icon = ""
            if efficiency > 2.0:
                efficiency_icon = " 💎"  # High efficiency
            elif efficiency > 1.5:
                efficiency_icon = " ⚡"  # Good efficiency
            elif efficiency < 0.5:
                efficiency_icon = " 🐌"  # Low efficiency
            
            # Medal for top 3
            medal = ""
            if i == 1:
                medal = "🥇 "
            elif i == 2:
                medal = "🥈 "
            elif i == 3:
                medal = "🥉 "
            else:
                medal = f"{i}. "
            
            lines.append(
                f"{medal}{name}: {s.grow_count} ростов{efficiency_icon}\n"
                f"   └ Размер: {s.size_cm} см ({size_rank}){special_title}"
            )
        
        # Add statistics section
        stats_section = (
            f"\n\n📊 СТАТИСТИКА АКТИВНОСТИ\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Игроков в топе: {len(top10)}\n"
            f"🌱 Всего ростов: {total_grows}\n"
            f"📊 Средне на игрока: {avg_grows} ростов\n"
            f"📏 Средний размер: {avg_size} см\n"
            f"🏆 Рекорд: {max_grows} ростов\n"
            f"\n💎 = высокая эффективность | ⚡ = хорошая | 🐌 = низкая"
        )
        
        text = "\n".join(lines) + stats_section + "\n\n📋 /games"
        
        # Generate multi-line chart for top growers
        try:
            chart_bytes = top_chart_generator.generate_top10_chart(top10)
            if chart_bytes:
                photo = BufferedInputFile(chart_bytes, filename="top_grow_chart.png")
                await bot.send_photo(
                    chat_id=msg.chat.id,
                    message_thread_id=msg.message_thread_id,
                    photo=photo,
                    caption=text
                )
                return
        except Exception as e:
            logger.warning(f"Failed to generate top_grow chart: {e}")
        
        # Fallback: send text only
        await msg.reply(text)


@router.message(F.text.startswith("/profile"))
async def cmd_profile(msg: Message, bot: Bot):
    """
    Displays the user's comprehensive profile data as a generated image.
    
    Generates a PNG profile card with:
    - Avatar with league-colored ring
    - Username and rank title
    - League badge with progress to next
    - Stats (size, balance, wins, reputation, etc.)
    - Social info (marriage, guild, duo)
    - Achievement and quest progress
    - Growth sparkline
    """
    from app.database.models import Marriage, UserAchievement, UserQuest
    from sqlalchemy import or_
    
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    async with async_session() as session:
        user, game_stat, wallet, user_achievements, user_quests, guild_memberships, duo_team = \
            await get_full_user_profile(session, user.tg_user_id)

        if not user:
            return await msg.reply("Профиль не найден. Начни играть с /grow!")

        # Get league status
        try:
            league_status = await league_service.get_status(user.tg_user_id, session)
            elo = league_status.elo
            league = league_status.league
        except Exception as e:
            logger.warning(f"Failed to get league status: {e}")
            elo = 1000
            league = League.SCRAP
        
        # Get avatar
        avatar_bytes = None
        try:
            photos = await bot.get_user_profile_photos(msg.from_user.id, limit=1)
            if photos.total_count > 0:
                photo = photos.photos[0][-1]
                file = await bot.get_file(photo.file_id)
                avatar_data = io.BytesIO()
                await bot.download_file(file.file_path, avatar_data)
                avatar_bytes = avatar_data.getvalue()
        except Exception as e:
            logger.debug(f"Failed to get avatar: {e}")
        
        # Get rank title
        rank_title = get_rank_by_size(game_stat.size_cm)
        
        # Calculate wins/losses
        wins = game_stat.pvp_wins
        losses = max(0, (wins * 5 - game_stat.reputation) // 2) if game_stat.reputation < wins * 5 else 0
        
        # Get marriage info
        spouse_name = None
        try:
            marriage = await session.scalar(
                select(Marriage).where(
                    or_(
                        Marriage.user1_id == user.tg_user_id,
                        Marriage.user2_id == user.tg_user_id
                    ),
                    Marriage.divorced_at.is_(None)
                )
            )
            if marriage:
                spouse_id = marriage.user2_id if marriage.user1_id == user.tg_user_id else marriage.user1_id
                spouse = await session.scalar(select(User).where(User.tg_user_id == spouse_id))
                if spouse:
                    spouse_name = spouse.username or spouse.first_name
        except Exception:
            pass
        
        # Guild name
        guild_name = None
        if guild_memberships:
            guild_name = guild_memberships[0].guild.name
        
        # Duo partner
        duo_partner = None
        if duo_team:
            partner = duo_team.user1 if duo_team.user2.id == user.id else duo_team.user2
            duo_partner = partner.username or partner.first_name
        
        # Count achievements
        achievements_count = len(user_achievements) if user_achievements else 0
        
        # Count completed quests
        quests_done = sum(1 for uq in user_quests if uq.completed_at) if user_quests else 0
        quests_total = len(user_quests) if user_quests else 3
        
        # Growth history from game_stat
        growth_history = []
        if game_stat.grow_history:
            growth_history = [entry.get("size", 0) for entry in game_stat.grow_history]
        
        # Next league ELO threshold
        next_league_elo = {
            League.SCRAP: 1200,
            League.SILICON: 1500,
            League.QUANTUM: 2000,
            League.ELITE: 3000,
        }.get(league, 3000)
        
        # Create profile data
        profile_data = ProfileData(
            username=user.username or user.first_name or f"User {user.tg_user_id}",
            avatar_bytes=avatar_bytes,
            elo=elo,
            league=league,
            wins=wins,
            losses=losses,
            size_cm=game_stat.size_cm,
            rank_title=rank_title,
            reputation=game_stat.reputation,
            balance=wallet.balance if wallet else 0,
            grow_count=game_stat.grow_count,
            casino_jackpots=game_stat.casino_jackpots,
            spouse_name=spouse_name,
            guild_name=guild_name,
            duo_partner=duo_partner,
            achievements_count=achievements_count,
            achievements_total=24,
            quests_done=quests_done,
            quests_total=quests_total,
            growth_history=growth_history,
            next_league_elo=next_league_elo,
        )
        
        # Generate profile image
        try:
            image_bytes = profile_generator.generate(profile_data)
            photo = BufferedInputFile(image_bytes, filename="profile.png")
            
            # Build interactive keyboard
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            kb = InlineKeyboardBuilder()
            kb.button(text="🎮 Игры", callback_data="gamehub_main")
            kb.button(text="🏪 Магазин", callback_data="shop_main")
            kb.button(text="📜 Квесты", callback_data="profile_quests")
            kb.button(text="🏆 Достижения", callback_data="profile_achievements")
            kb.adjust(2, 2)
            
            await msg.reply_photo(photo=photo, reply_markup=kb.as_markup())
            
        except Exception as e:
            logger.error(f"Failed to generate profile image: {e}")
            await _send_text_profile(msg, user, game_stat, wallet, league, elo, 
                                    guild_memberships, duo_team, user_achievements, user_quests)


async def _send_text_profile(msg: Message, user, game_stat, wallet, league, elo,
                             guild_memberships, duo_team, user_achievements, user_quests):
    """Fallback text profile when image generation fails."""
    size_rank = get_rank_by_size(game_stat.size_cm)
    
    profile_text = (
        f"📈 <b>Ваш профиль, {user.username or user.first_name}:</b>\n"
        f"📏 Размер: {game_stat.size_cm} см\n"
        f"🏆 Ранг: {size_rank}\n"
        f"🏅 Репутация: {game_stat.reputation}\n"
        f"💰 Баланс: {wallet.balance if wallet else 0} монет\n"
        f"⚔️ Побед в PvP: {game_stat.pvp_wins}\n"
        f"🌱 Выращиваний: {game_stat.grow_count}\n"
        f"🎰 Джекпотов в казино: {game_stat.casino_jackpots}\n"
        f"\n🎖️ <b>Лига:</b> {league.display_name}\n"
        f"📊 ELO: {elo}\n"
    )

    if guild_memberships:
        guild_name = guild_memberships[0].guild.name
        guild_role = guild_memberships[0].role
        profile_text += f"🛡️ Гильдия: {guild_name} ({guild_role})\n"
    
    if duo_team:
        partner = duo_team.user1 if duo_team.user2.id == user.id else duo_team.user2
        profile_text += f"🤝 Дуэт: @{partner.username or str(partner.tg_user_id)} (Рейтинг: {duo_team.stats.rating})\n"

    if user_achievements:
        profile_text += "\n🏆 <b>Достижения:</b>\n"
        for ua in user_achievements:
            profile_text += f"  - {ua.achievement.name}\n"
    
    if user_quests:
        profile_text += "\n📜 <b>Активные квесты:</b>\n"
        for uq in user_quests:
            status = "Выполнено" if uq.completed_at else f"Прогресс: {uq.progress}/{uq.quest.target_value}"
            profile_text += f"  - {uq.quest.name} ({status})\n"

    profile_text += "\n📋 /games"
    await msg.reply(profile_text, parse_mode="HTML")


@router.callback_query(F.data == "profile_quests")
async def cb_profile_quests(callback: CallbackQuery):
    """Show quests from profile button."""
    from app.services.quests import get_user_quests, assign_daily_quests
    
    user_id = callback.from_user.id
    quests = await get_user_quests(user_id)
    
    if not quests:
        assigned = await assign_daily_quests(user_id, count=3)
        if assigned:
            quests = await get_user_quests(user_id)
    
    if not quests:
        await callback.answer("📜 Квесты временно недоступны", show_alert=True)
        return
    
    text = "📜 <b>Твои квесты:</b>\n\n"
    for quest, user_quest in quests:
        progress_pct = min(100, int((user_quest.progress / quest.target_value) * 100))
        filled = progress_pct // 10
        bar = "█" * filled + "░" * (10 - filled)
        text += f"<b>{quest.name}</b>\n[{bar}] {user_quest.progress}/{quest.target_value}\n🎁 {quest.reward_amount} монет\n\n"
    
    await callback.answer()
    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "profile_achievements")
async def cb_profile_achievements(callback: CallbackQuery):
    """Show achievements from profile button."""
    from app.services.achievements import check_and_award_achievements
    from app.database.models import UserAchievement, Achievement
    from sqlalchemy import func
    
    user_id = callback.from_user.id
    
    # Check for new achievements
    await check_and_award_achievements(user_id)
    
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_user_id == user_id))
        if not user:
            await callback.answer("Профиль не найден", show_alert=True)
            return
        
        # Get user achievements
        result = await session.execute(
            select(UserAchievement, Achievement)
            .join(Achievement)
            .where(UserAchievement.user_id == user.id)
        )
        user_achs = result.fetchall()
        
        # Count total
        total = await session.scalar(select(func.count(Achievement.id)))
    
    text = f"🏆 <b>Твои достижения ({len(user_achs)}/{total}):</b>\n\n"
    
    if user_achs:
        for ua, ach in user_achs:
            text += f"{ach.name}\n"
    else:
        text += "<i>Пока нет достижений. Играй чтобы получить!</i>\n"
    
    text += "\n/achievements — все доступные"
    
    await callback.answer()
    await callback.message.answer(text, parse_mode="HTML")


@router.message(F.text.startswith("/pvp"))
async def cmd_pvp(msg: Message):
    """
    Redirect /pvp to /challenge for proper consent-based PvP.
    
    Old /pvp worked without opponent consent which was unfair.
    Now redirects to /challenge which requires acceptance.
    """
    # Parse arguments to pass to challenge
    parts = (msg.text or "").split()
    
    # Build help message
    help_text = (
        "⚔️ <b>PvP Дуэли</b>\n\n"
        "Используй /challenge для честных дуэлей:\n\n"
        "• <code>/challenge @username</code> — вызов игрока (ждёт согласия)\n"
        "• <code>/challenge @username 100</code> — вызов со ставкой\n"
        "• <code>/challenge</code> — бой с Олегом (ИИ)\n\n"
        "Соперник должен принять вызов кнопкой ✅\n"
        "Таймаут: 5 минут"
    )
    
    # If user specified opponent, suggest the command
    if len(parts) >= 2:
        opponent = parts[1]
        bet = parts[2] if len(parts) >= 3 else ""
        help_text += f"\n\n💡 Попробуй: <code>/challenge {opponent} {bet}</code>"
    
    await msg.reply(help_text, parse_mode="HTML")


SLOTS = ["🍒", "🍋", "🔧", "🧰", "🎮", "🔥"]


def roll_slots():
    return [random.choice(SLOTS) for _ in range(3)]


def slots_payout(reel: list[str]) -> int:
    # 3 same -> x5; 2 same -> x2; else 0
    if reel[0] == reel[1] == reel[2]:
        return 5
    if reel[0] == reel[1] or reel[1] == reel[2] or reel[0] == reel[2]:
        return 2
    return 0


@router.message(F.text.startswith("/casino"))
async def cmd_casino(msg: Message):
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    # Check if user is already playing (Requirements 2.2, 2.3)
    if await state_manager.is_playing(user_id, chat_id):
        session = await state_manager.get_session(user_id, chat_id)
        game_name = session.game_type if session else "игру"
        return await msg.reply(
            f"⚠️ Ты уже играешь в {game_name}! Заверши текущую игру."
        )
    
    async_session = get_session()
    user = await ensure_user(msg.from_user)
    parts = (msg.text or "").split()
    bet = 10
    if len(parts) >= 2:
        try:
            bet = int(parts[1])
        except Exception:
            pass
    bet = max(1, min(1000, bet))
    async with async_session() as session:
        # load wallet
        resw = await session.execute(select(Wallet).where(Wallet.user_id == user.id))
        w = resw.scalars().first()
        if not w:
            w = Wallet(user_id=user.id, balance=100)
            session.add(w)
            await session.flush()
        if w.balance < bet:
            return await msg.reply(f"У тебя {w.balance}, а ставка {bet}. Бедно живёшь. Пополнись победами в /pvp.")
        w.balance -= bet
        reel = roll_slots()
        mult = slots_payout(reel)
        
        # Event Modifier: CASINO_LUCK (Second chance)
        if mult == 0 and await event_service.has_modifier(EventModifier.CASINO_LUCK):
            if random.random() < 0.15:  # 15% chance to force a win
                # Force a pair
                symbol = random.choice(SLOTS)
                reel = [symbol, symbol, random.choice([s for s in SLOTS if s != symbol])]
                mult = 2
                logger.info(f"User {user_id} saved by CASINO_LUCK event")

        win = bet * mult
        
        # Event Modifier: DOUBLE_COINS
        if win > 0 and await event_service.has_modifier(EventModifier.DOUBLE_COINS):
            win *= 2
            
        w.balance += win

        gs_res = await session.execute(select(GameStat).where(GameStat.user_id == user.id))
        gs = gs_res.scalars().first()

        board = " ".join(reel)
        
        # Determine text prefix based on event
        event_prefix = "🔥 ИВЕНТ x2! " if await event_service.has_modifier(EventModifier.DOUBLE_COINS) and win > 0 else ""
        
        if mult == 5:
            gs.casino_jackpots += 1
            text = (
                f"🎰 {board}\n"
                f"{event_prefix}🎉 Джекпот! Выигрыш: {win} монет\n"
                f"💰 Баланс: {w.balance}\n"
                f"📋 /games"
            )
        elif mult == 2:
            text = (
                f"🎰 {board}\n"
                f"{event_prefix}✨ Норм, удвоил! Выигрыш: {win} монет\n"
                f"💰 Баланс: {w.balance}\n"
                f"📋 /games"
            )
        else:
            text = (
                f"🎰 {board}\n"
                f"😢 Мимо, дружище\n"
                f"💰 Баланс: {w.balance}\n"
                f"📋 /games"
            )
        
        await session.commit()

        if mult == 5: # Only check for achievements if a jackpot occurred
            new_achievements = await check_and_award_achievements(session, msg.bot, user, gs, "casino_jackpot")
            for achievement in new_achievements:
                await msg.answer(f"🎉 Новое достижение: {achievement}!")
            
            updated_quests = await check_and_update_quests(session, user, "casino_jackpot")
            for quest in updated_quests:
                await msg.answer(f"✅ Выполнили квест: {quest.name}! Награда: {quest.reward_amount} {quest.reward_type}!")

        
        await msg.reply(text)


@router.message(Command("roulette"))
async def cmd_roulette(msg: Message):
    """
    Команда /roulette — Русская рулетка с анимацией.
    
    Использование:
      /roulette - стандартный режим (фиксированные очки)
      /roulette <ставка> - режим ставок (ставка на выживание)
    
    Игрок крутит барабан с 1 пулей в 6 камерах.
    - Выстрел (1/6): теряет очки/ставку
    - Выживание (5/6): получает очки/выигрыш
    
    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
    """
    import asyncio
    
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    # Check if user is already playing (Requirements 2.2, 2.3)
    if await state_manager.is_playing(user_id, chat_id):
        session = await state_manager.get_session(user_id, chat_id)
        game_name = session.game_type if session else "игру"
        return await msg.reply(
            f"⚠️ Ты уже играешь в {game_name}! Заверши текущую игру."
        )
    
    # Ensure user exists in DB
    await ensure_user(msg.from_user)
    
    # Parse bet amount from command (Requirements 5.4)
    parts = (msg.text or "").split()
    bet_amount = 0
    if len(parts) >= 2:
        try:
            bet_amount = int(parts[1])
            if bet_amount < 0:
                bet_amount = 0
        except ValueError:
            pass
    
    # Animation Phase 1: "Заряжаем..." (Requirements 5.1)
    bet_info = f"\n💰 Ставка: {bet_amount} очков" if bet_amount > 0 else ""
    anim_msg = await msg.reply(
        f"🔫 <b>Русская рулетка</b>{bet_info}\n\n"
        f"🔄 Заряжаем барабан...",
        parse_mode="HTML"
    )
    
    await asyncio.sleep(2)
    
    # Animation Phase 2: "Крутим..." (Requirements 5.1)
    await anim_msg.edit_text(
        f"🔫 <b>Русская рулетка</b>{bet_info}\n\n"
        f"🎰 Крутим барабан...",
        parse_mode="HTML"
    )
    
    await asyncio.sleep(2)
    
    # Play roulette using async wrapper with wallet_service
    result = await play_roulette_async(user_id, bet_amount)
    
    # Handle errors (insufficient balance, etc.)
    if not result.success:
        await anim_msg.edit_text(
            f"🔫 <b>Русская рулетка</b>\n\n"
            f"❌ {result.message}",
            parse_mode="HTML"
        )
        return
    
    # Log the result
    logger.info(
        f"Roulette: @{msg.from_user.username or user_id} - "
        f"{'SHOT' if result.shot else 'SURVIVED'}, bet={bet_amount}, "
        f"change: {result.points_change}, balance: {result.new_balance}"
    )
    
    # Update tournament score for roulette survival (Requirement 10.1)
    if not result.shot:  # Only count survivals
        try:
            await tournament_service.update_score(
                user_id=user_id,
                discipline=TournamentDiscipline.ROULETTE,
                delta=1,  # 1 point per survival
                username=msg.from_user.username
            )
        except Exception as e:
            logger.warning(f"Failed to update tournament score: {e}")
    
    # Animation Phase 3: Result with dramatic effect (Requirements 5.2, 5.3)
    if result.shot:
        # Shot result (Requirements 5.2)
        result_emoji = "💥 БАХ! 💀"
    else:
        # Survival result (Requirements 5.3)
        result_emoji = "🔫 Щёлк... 😅"
    
    # Final message with result
    await anim_msg.edit_text(
        f"🔫 <b>Русская рулетка</b>{bet_info}\n\n"
        f"{result_emoji}\n\n"
        f"{result.message}\n\n"
        f"💰 Баланс: {result.new_balance} очков\n"
        f"📋 /games",
        parse_mode="HTML"
    )


@router.message(Command("coinflip"))
async def cmd_coinflip(msg: Message):
    """
    Команда /coinflip — Подбрасывание монетки.
    
    Использование: /coinflip <ставка> <орёл|решка|heads|tails>
    Примеры:
      /coinflip 50 heads
      /coinflip 100 tails
      /coinflip 50 орёл
      /coinflip 100 решка
    
    - 50/50 вероятность
    - Выигрыш: удвоение ставки
    - Проигрыш: потеря ставки
    
    Requirements: 8.1, 8.2, 8.3, 8.4
    """
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    # Check if user is already playing (Requirements 2.2, 2.3)
    if await state_manager.is_playing(user_id, chat_id):
        session = await state_manager.get_session(user_id, chat_id)
        game_name = session.game_type if session else "игру"
        return await msg.reply(
            f"⚠️ Ты уже играешь в {game_name}! Заверши текущую игру."
        )
    
    # Ensure user exists in DB
    await ensure_user(msg.from_user)
    
    # Parse command arguments
    parts = (msg.text or "").split()
    
    # Default values
    bet_amount = 10
    choice = None
    
    # Parse bet amount and choice
    if len(parts) >= 2:
        try:
            bet_amount = int(parts[1])
        except ValueError:
            # Maybe they put choice first?
            choice = parts[1].lower()
    
    if len(parts) >= 3:
        choice = parts[2].lower()
    elif len(parts) == 2 and choice is None:
        # Only bet amount provided, no choice
        return await msg.reply(
            "🪙 <b>Монетка</b>\n\n"
            "Использование: <code>/coinflip &lt;ставка&gt; &lt;орёл|решка&gt;</code>\n"
            "Примеры:\n"
            "  <code>/coinflip 50 орёл</code>\n"
            "  <code>/coinflip 100 решка</code>\n"
            "  <code>/coinflip 50 heads</code>\n\n"
            "Выбери сторону: орёл (heads) или решка (tails)",
            parse_mode="HTML"
        )
    
    # Map Russian input to internal heads/tails (Requirements 8.1)
    choice = map_coinflip_choice(choice)
    
    # Validate choice
    if choice not in ("heads", "tails"):
        return await msg.reply(
            "🪙 <b>Монетка</b>\n\n"
            "Использование: <code>/coinflip &lt;ставка&gt; &lt;орёл|решка&gt;</code>\n"
            "Примеры:\n"
            "  <code>/coinflip 50 орёл</code>\n"
            "  <code>/coinflip 100 решка</code>\n"
            "  <code>/coinflip 50 heads</code>\n\n"
            "Выбери сторону: орёл (heads) или решка (tails)",
            parse_mode="HTML"
        )
    
    # Validate bet amount
    if bet_amount <= 0:
        return await msg.reply(
            "🪙 Ставка должна быть положительной, гений.",
            parse_mode="HTML"
        )
    
    # Play coin flip using async wrapper with wallet_service
    result = await flip_coin_async(user_id, bet_amount, choice)
    
    # Log the result
    logger.info(
        f"CoinFlip: @{msg.from_user.username or user_id} - "
        f"choice={result.choice}, result={result.result}, won={result.won}, "
        f"bet={result.bet_amount}, change={result.balance_change}, balance={result.new_balance}"
    )
    
    # Handle errors
    if not result.success:
        await msg.reply(
            f"🪙 <b>Монетка</b>\n\n"
            f"{result.message}",
            parse_mode="HTML"
        )
        return
    
    # Format choice display
    choice_display = "орёл" if result.choice == "heads" else "решка"
    result_display = "орёл" if result.result == "heads" else "решка"
    
    # Send the result message
    if result.won:
        emoji = "🎉"
        outcome = f"Выпало: {result_display.upper()}! Ты угадал!"
    else:
        emoji = "😢"
        outcome = f"Выпало: {result_display.upper()}! Мимо..."
    
    await msg.reply(
        f"🪙 <b>Монетка</b>\n\n"
        f"Твой выбор: {choice_display}\n"
        f"{emoji} {outcome}\n\n"
        f"{result.message}\n\n"
        f"💰 Баланс: {result.new_balance} очков\n"
        f"📋 /games",
        parse_mode="HTML"
    )
