"""Обработчик событий добавления бота в чат (Plug & Play)."""

import logging
import random
from datetime import timedelta
from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated, CallbackQuery
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import Chat, User, PendingVerification
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()

# Время на верификацию (в минутах)
VERIFICATION_TIMEOUT_MINUTES = 5

# Обновляем модель ChatConfig, чтобы она использовалась в новых чатах
async def create_chat(chat_id: int, chat_title: str, chat_type: str, owner_user_id: int, is_forum: bool):
    """Создает конфигурацию для нового чата."""
    async_session = get_session()
    async with async_session() as session:
        # Проверяем, существует ли уже конфигурация для этого чата
        config_res = await session.execute(
            select(Chat).filter_by(id=chat_id)
        )
        config = config_res.scalars().first()
        
        if config:
            # Если уже существует, обновляем название
            config.title = chat_title
        else:
            # Создаем новую конфигурацию
            config = Chat(
                id=chat_id,
                title=chat_title,
                is_forum=is_forum,
                owner_user_id=owner_user_id,
            )
            session.add(config)
        
        await session.commit()
        return config



async def send_welcome_message(bot, chat_id: int, chat_title: str):
    """
    Отправляет приветственное сообщение в чат.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        chat_title: Название чата
    """
    welcome_messages = [
        f"О, новый чатик '{chat_title}'! Я Олег, ваш персональный надзиратель. Следите за базаром, не троллите почем зря, и будете жить.",
        f"Так, {chat_title}, значит. Я Олег, и я здесь, чтобы вносить порядок. Или хаос. По настроению.",
        f"Привет, {chat_title}. Я Олег. Посмотрим, как вы тут себя ведете.",
        f"Зовите меня Олег. Я ваш новый лучший друг и худший кошмар. Зависит от вас.",
        f"Наконец-то я в {chat_title}. Олег на месте. Начинаем веселье.",
    ]
    try:
        await bot.send_message(chat_id=chat_id, text=random.choice(welcome_messages))
    except Exception as e:
        logger.error(f"Ошибка при отправке приветствия в чат {chat_id}: {e}")


async def create_pending_verification(user_id: int, chat_id: int, username: str, message_id: int = None):
    """
    Создает запись о pending верификации пользователя.
    """
    async_session = get_session()
    async with async_session() as session:
        # Удаляем старые записи для этого пользователя в этом чате
        old_records = await session.execute(
            select(PendingVerification).filter_by(user_id=user_id, chat_id=chat_id)
        )
        for record in old_records.scalars().all():
            await session.delete(record)
        
        # Создаем новую запись
        verification = PendingVerification(
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            welcome_message_id=message_id,
            expires_at=utc_now() + timedelta(minutes=VERIFICATION_TIMEOUT_MINUTES),
            is_verified=False,
            is_kicked=False
        )
        session.add(verification)
        await session.commit()
        logger.info(f"Создана pending верификация для user {user_id} в чате {chat_id}")


async def mark_user_verified(user_id: int, chat_id: int) -> bool:
    """
    Отмечает пользователя как верифицированного.
    
    Returns:
        True если запись найдена и обновлена
    """
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(PendingVerification).filter_by(
                user_id=user_id, 
                chat_id=chat_id,
                is_verified=False,
                is_kicked=False
            )
        )
        verification = result.scalars().first()
        
        if verification:
            verification.is_verified = True
            await session.commit()
            logger.info(f"Пользователь {user_id} верифицирован в чате {chat_id}")
            return True
        return False

@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def bot_added_to_chat(event: ChatMemberUpdated):
    """
    Обработчик события добавления бота в чат.
    """
    chat_id = event.chat.id
    chat_title = event.chat.title or "Без названия"
    chat_type = event.chat.type
    is_forum = event.chat.is_forum or False

    logger.info(f"Бот добавлен в чат {chat_title} (ID: {chat_id}, тип: {chat_type})")

    # Ищем создателя чата
    chat_admins = await event.bot.get_chat_administrators(chat_id)
    creator = next((admin for admin in chat_admins if admin.status == 'creator'), None)
    owner_id = creator.user.id if creator else None

    # Создаем конфигурацию для чата
    await create_chat(chat_id, chat_title, chat_type, owner_id, is_forum)

    # Отправляем приветственное сообщение
    await send_welcome_message(event.bot, chat_id, chat_title)


@router.my_chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def bot_removed_from_chat(event: ChatMemberUpdated):
    """
    Обработчик события удаления бота из чата.
    """
    chat_id = event.chat.id
    chat_title = event.chat.title or "Без названия"
    
    logger.info(f"Бот удален из чата {chat_title} (ID: {chat_id})")
    
    # В реальной реализации можно удалить конфигурацию чата или отметить как неактивную
    # Пока что просто логируем событие
    pass


from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


@router.message(F.new_chat_members)
async def new_chat_member_welcome(msg: Message):
    """
    Обработчик события добавления новых участников в чат.
    Создает pending верификацию, которая проверяется scheduler'ом.
    """
    # Удаляем системное сообщение о присоединении (если возможно)
    try:
        await msg.delete()
    except Exception:
        pass

    # Приветствуем каждого нового участника
    for new_member in msg.new_chat_members:
        try:
            # Не приветствуем себя (бота) и других ботов
            if new_member.is_bot:
                continue

            # Генерируем приветствие
            context_info = f"чат '{msg.chat.title}'" if msg.chat.title else "этот чат"
            
            welcome_variants = [
                f"👋 Новое лицо! {new_member.full_name}, добро пожаловать в {context_info}.",
                f"🚪 {new_member.full_name} зашел в {context_info}. Не тролли почем зря.",
                f"👀 О, {new_member.full_name}! Добро пожаловать. Олег следит за тобой.",
            ]
            welcome_text = random.choice(welcome_variants)
            welcome_text += f"\n\n⏱ Нажми кнопку ниже в течение {VERIFICATION_TIMEOUT_MINUTES} минут, иначе будешь кикнут."

            # Создаем inline-кнопку
            keyboard = InlineKeyboardBuilder()
            keyboard.button(
                text="✅ Я не бот",
                callback_data=f"verify_user_{new_member.id}_{msg.chat.id}"
            )
            keyboard.adjust(1)

            # Отправляем приветствие с кнопкой
            welcome_msg = await msg.answer(welcome_text, reply_markup=keyboard.as_markup())

            # Создаем запись в БД для отслеживания (scheduler проверит и кикнет если надо)
            await create_pending_verification(
                user_id=new_member.id,
                chat_id=msg.chat.id,
                username=new_member.username or new_member.full_name,
                message_id=welcome_msg.message_id
            )

            logger.info(f"Новый участник {new_member.id} в чате {msg.chat.id}, ожидает верификации")

        except Exception as e:
            logger.error(f"Ошибка при приветствии участника {new_member.id}: {e}")


@router.callback_query(F.data.startswith("verify_user_"))
async def handle_verification_button(callback: CallbackQuery):
    """Обработка нажатия кнопки подтверждения 'Я не бот'."""
    data_parts = callback.data.split("_")
    if len(data_parts) < 4:
        await callback.answer("Неверный формат данных.")
        return

    user_id = int(data_parts[2])
    chat_id = int(data_parts[3])

    # Проверяем, что пользователь, который нажал, совпадает с тем, для кого была кнопка
    if callback.from_user.id != user_id:
        await callback.answer("Эта кнопка не для тебя.", show_alert=True)
        return

    try:
        # Отмечаем пользователя как верифицированного в БД
        verified = await mark_user_verified(user_id, chat_id)
        
        if verified:
            await callback.message.edit_text(
                f"✅ {callback.from_user.full_name} подтвердил, что он не бот!\n"
                f"Добро пожаловать в чат!"
            )
            await callback.answer("Верификация пройдена! Добро пожаловать.")
        else:
            # Запись не найдена — возможно уже верифицирован или кикнут
            await callback.answer("Верификация уже была обработана.", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка при обработке подтверждения пользователя {user_id}: {e}")
        await callback.answer("Произошла ошибка при подтверждении.", show_alert=True)