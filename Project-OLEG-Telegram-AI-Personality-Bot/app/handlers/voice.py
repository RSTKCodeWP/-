"""Voice command handlers for TTS and STT functionality.

This module provides handlers for:
- /say command for text-to-speech conversion
- Incoming voice message recognition (STT)
- Auto-voice integration for responses

Uses Edge TTS for Russian voice synthesis (Microsoft API).
Uses faster-whisper for speech recognition (STT).

**Feature: fortress-update, grand-casino-dictator**
**Validates: Requirements 5.1, 5.2, 5.4, 15.1, 15.2, 15.3, 15.4**
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from app.services.tts import tts_service
from app.services.tts_edge import edge_tts_service
from app.services.alive_ui import alive_ui_service
from app.services.voice_recognition import transcribe_voice_message, transcribe_video_note, is_available as stt_available
from app.services.ollama_client import generate_reply_with_context, is_ollama_available
from app.utils import safe_reply

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.voice)
async def handle_voice_message(msg: Message):
    """
    Handle incoming voice messages - transcribe and respond.
    
    Uses faster-whisper for speech recognition.
    Only responds in private chats or when replying to bot's message.
    """
    # Проверяем включена ли функция
    from app.services.bot_config import is_feature_enabled
    if msg.chat.type != "private" and not await is_feature_enabled(msg.chat.id, "voice"):
        return
    
    if not stt_available():
        logger.warning("STT not available, skipping voice message")
        return
    
    # В группах отвечаем только если это реплай на сообщение бота
    if msg.chat.type != "private":
        if not msg.reply_to_message:
            return
        if not msg.reply_to_message.from_user:
            return
        if msg.reply_to_message.from_user.id != msg.bot.id:
            return
    
    # Проверяем доступность Ollama перед обработкой
    if not await is_ollama_available():
        logger.debug("Skipping voice message - Ollama not available")
        return
    
    logger.info(f"Voice message from @{msg.from_user.username or msg.from_user.id}")
    
    # Show typing indicator
    await msg.bot.send_chat_action(msg.chat.id, "typing")
    
    try:
        # Transcribe voice message
        text = await transcribe_voice_message(msg.bot, msg.voice.file_id)
        
        if not text:
            await safe_reply(msg, "🎤 Не удалось распознать голосовое сообщение")
            return
        
        logger.info(f"Transcribed: {text[:100]}...")
        
        # Get Oleg's response
        response = await generate_reply_with_context(
            text,
            username=msg.from_user.username or msg.from_user.first_name,
            chat_id=msg.chat.id,
            user_id=msg.from_user.id
        )
        
        if response:
            # Reply with transcription and response
            reply_text = f"🎤 <i>{text}</i>\n\n{response}"
            await safe_reply(msg, reply_text, parse_mode="HTML")
        else:
            # Just show transcription if no response
            await safe_reply(msg, f"🎤 <i>{text}</i>", parse_mode="HTML")
            
    except TelegramBadRequest as e:
        error_msg = str(e).lower()
        if "message to be replied not found" in error_msg or "message to reply not found" in error_msg or "thread not found" in error_msg:
            logger.warning(f"Voice message: cannot reply - topic/message deleted: {e}")
            return
        logger.error(f"Voice message handling failed: {e}")
    except Exception as e:
        logger.error(f"Voice message handling failed: {e}")


@router.message(F.video_note)
async def handle_video_note(msg: Message):
    """
    Handle incoming video notes (circles) - extract audio, transcribe, 
    extract frames for visual analysis, and respond.
    
    Combines STT (speech-to-text) with vision analysis for comprehensive
    understanding of video messages.
    
    Only responds in private chats or when replying to bot's message.
    """
    # Проверяем включена ли функция (только для групп)
    from app.services.bot_config import is_feature_enabled
    if msg.chat.type != "private" and not await is_feature_enabled(msg.chat.id, "voice"):
        return
    
    # В группах отвечаем только если это реплай на сообщение бота
    if msg.chat.type != "private":
        if not msg.reply_to_message:
            return
        if not msg.reply_to_message.from_user:
            return
        if msg.reply_to_message.from_user.id != msg.bot.id:
            return
    
    # Проверяем доступность Ollama перед обработкой
    if not await is_ollama_available():
        logger.debug("Skipping video note - Ollama not available")
        return
    
    logger.info(f"Video note from @{msg.from_user.username or msg.from_user.id}")
    
    # Show typing indicator
    await msg.bot.send_chat_action(msg.chat.id, "typing")
    
    transcribed_text = None
    visual_description = None
    
    try:
        # 1. Транскрибируем аудио (если STT доступен)
        if stt_available():
            try:
                transcribed_text = await transcribe_video_note(msg.bot, msg.video_note.file_id)
                if transcribed_text:
                    logger.info(f"Transcribed video note: {transcribed_text[:100]}...")
            except Exception as stt_err:
                logger.warning(f"STT failed for video note: {stt_err}")
        
        # 2. Извлекаем кадры и анализируем визуально
        try:
            from app.services.gif_patrol import gif_patrol_service
            from app.services.ollama_client import analyze_image_content
            
            # Скачиваем видео
            file = await msg.bot.get_file(msg.video_note.file_id)
            video_data = await msg.bot.download_file(file.file_path)
            video_bytes = video_data.read() if hasattr(video_data, 'read') else video_data
            
            # Извлекаем кадры (используем метод из gif_patrol)
            frames = gif_patrol_service.extract_frames(video_bytes)
            
            if frames:
                # Анализируем средний кадр (самый репрезентативный)
                middle_frame = frames[len(frames) // 2]
                visual_description = await analyze_image_content(
                    middle_frame,
                    query="Опиши что видишь на этом кадре из видеосообщения. Кратко, 1-2 предложения."
                )
                logger.info(f"Visual analysis: {visual_description[:100]}...")
                
        except Exception as vision_err:
            logger.warning(f"Vision analysis failed for video note: {vision_err}")
        
        # 3. Формируем контекст для ответа
        if not transcribed_text and not visual_description:
            await safe_reply(msg, "🎥 Не удалось обработать кружочек — ни речь, ни картинку")
            return
        
        # Собираем полный контекст
        context_parts = []
        if transcribed_text:
            context_parts.append(f"Человек говорит: {transcribed_text}")
        if visual_description:
            context_parts.append(f"На видео видно: {visual_description}")
        
        full_context = "\n".join(context_parts)
        
        # 4. Генерируем ответ с учётом и аудио, и видео
        response = await generate_reply_with_context(
            full_context,
            username=msg.from_user.username or msg.from_user.first_name,
            chat_id=msg.chat.id,
            user_id=msg.from_user.id
        )
        
        # 5. Формируем красивый ответ
        reply_parts = ["🎥"]
        if transcribed_text:
            reply_parts.append(f"<i>«{transcribed_text}»</i>")
        if visual_description and not transcribed_text:
            # Показываем описание только если нет речи
            reply_parts.append(f"<i>(видно: {visual_description[:100]})</i>")
        
        if response:
            reply_parts.append(f"\n\n{response}")
        
        await safe_reply(msg, " ".join(reply_parts), parse_mode="HTML")
            
    except TelegramBadRequest as e:
        error_msg = str(e).lower()
        if "message to be replied not found" in error_msg or "message to reply not found" in error_msg or "thread not found" in error_msg:
            logger.warning(f"Video note: cannot reply - topic/message deleted: {e}")
            return
        logger.error(f"Video note handling failed: {e}")
    except Exception as e:
        logger.error(f"Video note handling failed: {e}")


@router.message(Command("say"))
async def cmd_say(msg: Message):
    """
    Command /say <text> — convert text to voice message.
    
    Generates a voice message with Oleg's characteristic voice
    and sends it as a voice note. Uses EdgeTTSService with proper
    temp file lifecycle management (Create → Send → Delete).
    
    Supports:
    - /say <text> — озвучить текст
    - /say (реплаем на сообщение) — озвучить текст из реплая
    
    **Validates: Requirements 5.1, 15.1, 15.2, 15.3**
    
    Args:
        msg: Incoming message with /say command
    """
    # Extract text after /say command
    text = msg.text
    if text:
        # Remove the /say command prefix
        text = text.replace("/say", "", 1).strip()
    
    # Если текст пустой, но есть реплай — берём текст из реплая
    if not text and msg.reply_to_message:
        reply = msg.reply_to_message
        if reply.text:
            text = reply.text
        elif reply.caption:
            text = reply.caption
    
    if not text:
        await msg.reply(
            "Напиши текст после команды или ответь на сообщение:\n"
            "• <code>/say Привет, я Олег!</code>\n"
            "• <code>/say</code> (реплаем на сообщение)",
            parse_mode="HTML"
        )
        return
    
    logger.info(f"TTS requested by @{msg.from_user.username or msg.from_user.id}: {text[:50]}...")
    
    # Try to generate voice with Alive UI status
    status = None
    thread_id = getattr(msg, 'message_thread_id', None)
    try:
        # Start status message for TTS generation
        status = await alive_ui_service.start_status(
            msg.chat.id, "tts", msg.bot, message_thread_id=thread_id
        )
        
        # Use Edge TTS (Microsoft API)
        result = await edge_tts_service.send_voice_with_notification(
            bot=msg.bot,
            chat_id=msg.chat.id,
            text=text,
            reply_to_message_id=msg.message_id
        )
        
        # Clean up status message
        if status:
            await alive_ui_service.finish_status(status, msg.bot)
            status = None
        
        if result.error:
            logger.warning(f"Edge TTS failed: {result.error}")
        else:
            logger.info(f"Voice sent successfully, file lifecycle: created={result.created}, sent={result.sent}, deleted={result.deleted}")
            
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        
        if status:
            await alive_ui_service.show_error(status, "Не удалось сгенерировать голос", msg.bot)
        
        # Fallback to text on any error
        await msg.reply(
            f"🔊 <i>(голосом Олега)</i>\n\n{text}",
            parse_mode="HTML"
        )


async def maybe_voice_response(text: str, msg: Message) -> bool:
    """
    Check if response should be auto-voiced and send voice if so.
    
    This function implements the 0.1% auto-voice probability.
    
    Args:
        text: Response text to potentially voice
        msg: Original message to reply to
        
    Returns:
        True if voice was sent, False if text should be sent instead
    """
    if not tts_service.should_auto_voice():
        return False
    
    logger.info(f"Auto-voice triggered for response to @{msg.from_user.username or msg.from_user.id}")
    
    try:
        # Use Edge TTS
        result = await edge_tts_service.send_voice(
            bot=msg.bot,
            chat_id=msg.chat.id,
            text=text,
            reply_to_message_id=msg.message_id
        )
        
        if result.error:
            logger.warning(f"Auto-voice Edge TTS failed: {result.error}")
            return False
        
        return result.sent
        
    except Exception as e:
        logger.error(f"Auto-voice generation failed: {e}")
        return False
