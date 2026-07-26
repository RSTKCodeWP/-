"""Utility functions for the bot."""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """
    Get current UTC time (Python 3.12+ compatible).
    
    Replaces deprecated utc_now().
    
    Returns:
        Current UTC datetime with timezone info
    """
    return datetime.now(timezone.utc)


def markdown_to_html(text: str) -> str:
    """
    Конвертирует Markdown разметку в HTML для Telegram.
    
    Поддерживает:
    - **жирный** или __жирный__ → <b>жирный</b>
    - *курсив* или _курсив_ → <i>курсив</i>
    - `код` → <code>код</code>
    - ```блок кода``` → <pre>блок кода</pre>
    - ~~зачёркнутый~~ → <s>зачёркнутый</s>
    - [текст](url) → <a href="url">текст</a>
    
    Args:
        text: Текст с Markdown разметкой
        
    Returns:
        Текст с HTML разметкой для Telegram
    """
    if not text:
        return text
    
    # Сначала экранируем HTML-спецсимволы (кроме тех что мы сами добавим)
    # НЕ экранируем < и > чтобы не сломать уже существующий HTML
    text = text.replace("&", "&amp;")
    
    # Блоки кода с языком ```python\ncode``` → <pre><code class="language-python">code</code></pre>
    def replace_code_block_with_lang(match):
        lang = match.group(1) or ""
        code = match.group(2)
        if lang:
            return f'<pre><code class="language-{lang}">{code}</code></pre>'
        return f"<pre>{code}</pre>"
    
    text = re.sub(r'```(\w*)\n?(.*?)```', replace_code_block_with_lang, text, flags=re.DOTALL)
    
    # Инлайн код `code` → <code>code</code>
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    
    # Жирный **text** или __text__ → <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    
    # Курсив *text* или _text_ → <i>text</i>
    # Но не внутри слов (например user_name не должен стать user<i>name)
    text = re.sub(r'(?<!\w)\*([^*]+)\*(?!\w)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'<i>\1</i>', text)
    
    # Зачёркнутый ~~text~~ → <s>text</s>
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)
    
    # Ссылки [text](url) → <a href="url">text</a>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    
    return text


def escape_html(text: str) -> str:
    """
    Экранирует HTML-спецсимволы для безопасной отправки в Telegram.
    
    Args:
        text: Исходный текст
        
    Returns:
        Текст с экранированными спецсимволами
    """
    if not text:
        return text
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def safe_reply(
    msg: Message,
    text: str,
    parse_mode: Optional[str] = "HTML",
    disable_web_page_preview: bool = True,
    convert_markdown: bool = True
) -> bool:
    """
    Безопасная отправка ответа с поддержкой старых топиков форума.
    
    Для форумов использует reply_parameters через прямой API вызов,
    что работает для всех топиков включая старые (id < 1000).
    
    Args:
        msg: Исходное сообщение для ответа
        text: Текст ответа
        parse_mode: Режим парсинга (HTML, Markdown, None). По умолчанию HTML.
        disable_web_page_preview: Отключить превью ссылок
        convert_markdown: Конвертировать Markdown в HTML (по умолчанию True)
        
    Returns:
        True если сообщение отправлено успешно
    """
    is_forum = getattr(msg.chat, 'is_forum', False)
    topic_id = getattr(msg, 'message_thread_id', None)
    
    # Конвертируем Markdown в HTML если нужно
    if convert_markdown and parse_mode == "HTML":
        text = markdown_to_html(text)
    
    try:
        if is_forum:
            # Для форумов используем reply_parameters — работает для всех топиков
            logger.debug(f"[SAFE_REPLY] Форум: отправка через reply_parameters (topic={topic_id})")
            bot_token = msg.bot.token
            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": msg.chat.id,
                "text": text,
                "reply_parameters": {
                    "message_id": msg.message_id,
                    "chat_id": msg.chat.id
                },
                "disable_web_page_preview": disable_web_page_preview
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(api_url, json=payload)
                result = resp.json()
                if result.get("ok"):
                    logger.debug(f"[SAFE_REPLY] OK через reply_parameters")
                    return True
                else:
                    error_desc = result.get("description", "Unknown error")
                    logger.error(f"[SAFE_REPLY] API error: {error_desc}")
                    # Если ошибка парсинга — пробуем без форматирования
                    if "can't parse" in error_desc.lower() or "parse" in error_desc.lower():
                        logger.warning(f"[SAFE_REPLY] Parse error, retrying without formatting")
                        payload["parse_mode"] = None
                        resp = await client.post(api_url, json=payload)
                        if resp.json().get("ok"):
                            return True
                    # Пробуем fallback через msg.answer()
                    await msg.answer(text, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
                    return True
        else:
            # Для обычных чатов используем стандартный reply
            try:
                await msg.reply(text, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
                return True
            except TelegramBadRequest as e:
                if "can't parse" in str(e).lower():
                    # Ошибка парсинга — отправляем без форматирования
                    logger.warning(f"[SAFE_REPLY] Parse error, retrying without formatting: {e}")
                    await msg.reply(text, parse_mode=None, disable_web_page_preview=disable_web_page_preview)
                    return True
                raise
            
    except TelegramBadRequest as e:
        error_msg = str(e).lower()
        if "thread not found" in error_msg or "message to reply not found" in error_msg:
            logger.warning(f"[SAFE_REPLY] Топик/сообщение удалено, пробуем answer(): {e}")
            try:
                await msg.answer(text, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
                return True
            except Exception as fallback_err:
                logger.error(f"[SAFE_REPLY] Fallback answer() тоже не сработал: {fallback_err}")
                return False
        logger.error(f"[SAFE_REPLY] TelegramBadRequest: {e}")
        return False
    except Exception as e:
        logger.error(f"[SAFE_REPLY] Unexpected error: {e}")
        return False
