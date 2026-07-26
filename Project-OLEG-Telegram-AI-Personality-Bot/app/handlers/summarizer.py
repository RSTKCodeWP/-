"""Summarizer command handlers for content summarization.

This module provides handlers for:
- /tl;dr command for quick summaries
- /summary command for content summarization
- Voice option for summaries

**Feature: fortress-update**
**Validates: Requirements 6.1, 6.2, 6.4**
"""

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.services.summarizer import summarizer_service
from app.services.tts import tts_service

logger = logging.getLogger(__name__)

router = Router()


async def _get_content_to_summarize(msg: Message) -> tuple[str, str]:
    """
    Extract content to summarize from message or reply.
    
    Args:
        msg: Incoming message
        
    Returns:
        Tuple of (content, source_type)
    """
    # Check if this is a reply to another message
    if msg.reply_to_message:
        reply = msg.reply_to_message
        
        # Check for forwarded message
        if reply.forward_from or reply.forward_from_chat:
            source_type = "forwarded"
        else:
            source_type = "message"
        
        # Get text content
        content = reply.text or reply.caption or ""
        
        # Check if the reply contains URLs
        if summarizer_service.contains_url(content):
            urls = summarizer_service.extract_urls(content)
            if urls:
                # Try to fetch article content from first URL
                article_content = await summarizer_service.fetch_article(urls[0])
                if article_content:
                    return article_content, "article"
        
        return content, source_type
    
    # No reply - check if command has text after it
    text = msg.text or ""
    # Remove command prefix
    for cmd in ["/tldr", "/tl;dr", "/summary", "/summarize"]:
        if text.lower().startswith(cmd):
            text = text[len(cmd):].strip()
            break
    
    if text:
        # Check for URLs in the text
        if summarizer_service.contains_url(text):
            urls = summarizer_service.extract_urls(text)
            if urls:
                article_content = await summarizer_service.fetch_article(urls[0])
                if article_content:
                    return article_content, "article"
        return text, "message"
    
    return "", "message"


def _build_voice_keyboard(summary: str, chat_id: int, message_id: int) -> InlineKeyboardMarkup:
    """
    Build inline keyboard with voice option.
    
    **Validates: Requirements 6.4**
    
    Args:
        summary: Summary text for voice
        chat_id: Chat ID
        message_id: Message ID
        
    Returns:
        InlineKeyboardMarkup with voice button
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔊 Озвучить",
            callback_data=f"voice_summary:{chat_id}:{message_id}"
        )]
    ])


@router.message(Command("tldr"))
@router.message(Command("summary"))
@router.message(Command("summarize"))
async def cmd_summarize(msg: Message):
    """
    Commands /tl;dr, /summary, /summarize — summarize content.
    
    Summarizes the replied message or provided text in Oleg's style.
    Offers voice option for the summary.
    
    **Validates: Requirements 6.1, 6.2, 6.4**
    
    Args:
        msg: Incoming message with summarize command
    """
    # Get content to summarize
    content, source_type = await _get_content_to_summarize(msg)
    
    if not content:
        await msg.reply(
            "Ответь на сообщение командой /tldr или /summary, "
            "чтобы я его пересказал. Или скинь ссылку на статью.",
            parse_mode="HTML"
        )
        return
    
    logger.info(
        f"Summary requested by @{msg.from_user.username or msg.from_user.id}: "
        f"source={source_type}, length={len(content)}"
    )
    
    # Generate summary
    try:
        result = await summarizer_service.summarize(content, source_type=source_type)
        
        if result.is_too_short:
            # Content too short - return special message
            # **Validates: Requirements 6.5**
            await msg.reply(result.summary, parse_mode="HTML")
            return
        
        # Build response with Oleg's commentary
        # **Validates: Requirements 6.2**
        response = f"📝 <b>Пересказ от Олега:</b>\n\n{result.summary}"
        
        if source_type == "article":
            response += "\n\n<i>(из статьи)</i>"
        
        # Add voice option button
        # **Validates: Requirements 6.4**
        keyboard = _build_voice_keyboard(
            result.summary,
            msg.chat.id,
            msg.message_id
        )
        
        await msg.reply(response, parse_mode="HTML", reply_markup=keyboard)
        
        logger.info(
            f"Summary generated: {result.original_length} chars -> "
            f"{len(result.summary)} chars ({result.sentence_count} sentences)"
        )
        
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        await msg.reply(
            "Не получилось пересказать. Попробуй ещё раз.",
            parse_mode="HTML"
        )


@router.callback_query(lambda c: c.data and c.data.startswith("voice_summary:"))
async def callback_voice_summary(callback: CallbackQuery):
    """
    Callback handler for voice summary button.
    
    Generates voice version of the summary when user clicks
    the "Озвучить" button.
    
    **Validates: Requirements 6.4**
    
    Args:
        callback: Callback query from inline button
    """
    # Parse callback data
    try:
        _, chat_id, message_id = callback.data.split(":")
        chat_id = int(chat_id)
        message_id = int(message_id)
    except (ValueError, IndexError):
        await callback.answer("Ошибка обработки запроса")
        return
    
    # Get the summary text from the message
    if not callback.message or not callback.message.text:
        await callback.answer("Не могу найти текст для озвучки")
        return
    
    # Extract summary from the message (remove header)
    text = callback.message.text
    if "Пересказ от Олега:" in text:
        text = text.split("Пересказ от Олега:", 1)[1].strip()
    
    # Remove any trailing notes
    if "(из статьи)" in text:
        text = text.replace("(из статьи)", "").strip()
    
    await callback.answer("Генерирую голос...")
    
    try:
        from app.services.ollama_client import get_global_persona
        persona = get_global_persona()
        
        result = await tts_service.generate_voice(text, persona=persona)
        
        if result is None:
            # TTS unavailable - send text fallback
            await callback.message.reply(
                f"🔊 <i>(голосом Олега)</i>\n\n{text}",
                parse_mode="HTML"
            )
            return
        
        # Send voice message
        from aiogram.types import BufferedInputFile
        voice_file = BufferedInputFile(
            file=result.audio_data,
            filename="voice.mp3"
        )
        await callback.message.reply_voice(
            voice=voice_file,
            caption="🎤 Пересказ голосом Олега",
            duration=int(result.duration_seconds)
        )
        
        logger.info(f"Voice summary generated for user {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"Voice summary generation failed: {e}")
        await callback.message.reply(
            f"🔊 <i>(голосом Олега)</i>\n\n{text}",
            parse_mode="HTML"
        )
