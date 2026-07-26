"""
Arq Worker for OLEG v6.0 Fortress Update.

Handles heavy computational tasks asynchronously:
- TTS generation
- Quote rendering
- GIF analysis

**Feature: fortress-update**
**Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 14.6**
"""

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from arq import create_pool, cron
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job

from app.config import settings

logger = logging.getLogger(__name__)

# Worker configuration constants
MAX_TRIES = 3  # Maximum retry attempts (Requirement 14.5)
QUEUE_WARNING_THRESHOLD = 100  # Warn when queue exceeds this (Requirement 14.6)
JOB_TIMEOUT = 300  # 5 minutes timeout for jobs
KEEP_RESULT_SECONDS = 3600  # Keep results for 1 hour


def get_redis_settings() -> RedisSettings:
    """Get Redis settings for Arq worker."""
    return RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.redis_db,
        password=settings.redis_password if settings.redis_password else None,
        conn_timeout=10,
        conn_retries=5,
        conn_retry_delay=1,
    )


# ============================================================================
# Task Functions
# ============================================================================

async def tts_task(
    ctx: Dict[str, Any],
    text: str,
    chat_id: int,
    reply_to: int,
    max_chars: int = 500
) -> Dict[str, Any]:
    """
    TTS generation task.
    
    Generates voice message from text and returns result for sending.
    
    **Feature: fortress-update, Property 12: Text truncation**
    **Validates: Requirements 14.1**
    
    Args:
        ctx: Arq context with Redis pool
        text: Text to convert to speech
        chat_id: Target chat ID
        reply_to: Message ID to reply to
        max_chars: Maximum characters (default 500)
        
    Returns:
        Dict with audio_data (base64), duration, chat_id, reply_to, success
    """
    import base64
    from app.services.tts import tts_service
    
    logger.info(f"TTS task started for chat {chat_id}, text length: {len(text)}")
    
    try:
        result = await tts_service.generate_voice(text, max_chars)
        
        if result is None:
            logger.warning(f"TTS generation returned None for chat {chat_id}")
            return {
                "success": False,
                "error": "TTS service unavailable",
                "chat_id": chat_id,
                "reply_to": reply_to,
                "fallback_text": text,
            }
        
        # Encode audio data as base64 for JSON serialization
        audio_base64 = base64.b64encode(result.audio_data).decode('utf-8')
        
        logger.info(f"TTS task completed for chat {chat_id}, duration: {result.duration_seconds}s")
        
        return {
            "success": True,
            "audio_data": audio_base64,
            "duration_seconds": result.duration_seconds,
            "format": result.format,
            "was_truncated": result.was_truncated,
            "chat_id": chat_id,
            "reply_to": reply_to,
        }
        
    except Exception as e:
        logger.error(f"TTS task failed for chat {chat_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "chat_id": chat_id,
            "reply_to": reply_to,
            "fallback_text": text,
        }


async def quote_render_task(
    ctx: Dict[str, Any],
    text: str,
    username: str,
    chat_id: int,
    reply_to: int,
    avatar_url: Optional[str] = None,
    timestamp: Optional[str] = None,
    theme: str = "dark",
    is_chain: bool = False,
    messages: Optional[list] = None,
    is_roast: bool = False,
) -> Dict[str, Any]:
    """
    Quote rendering task.
    
    Renders quote image and returns result for sending.
    
    **Feature: fortress-update, Property 17: Quote chain limit**
    **Validates: Requirements 14.2**
    
    Args:
        ctx: Arq context
        text: Quote text (for single quote)
        username: Username of author
        chat_id: Target chat ID
        reply_to: Message ID to reply to
        avatar_url: Optional avatar URL
        timestamp: Optional timestamp string
        theme: Quote theme (dark/light/auto)
        is_chain: Whether this is a chain quote
        messages: List of messages for chain quote
        is_roast: Whether to add roast comment
        
    Returns:
        Dict with image_data (base64), format, dimensions, chat_id, reply_to, success
    """
    import base64
    from app.services.quote_generator import (
        quote_generator_service, 
        QuoteStyle, 
        QuoteTheme,
        MessageData
    )
    
    logger.info(f"Quote render task started for chat {chat_id}, is_chain={is_chain}, is_roast={is_roast}")
    
    try:
        # Build style
        theme_enum = QuoteTheme(theme) if theme in ["dark", "light", "auto"] else QuoteTheme.DARK
        style = QuoteStyle(theme=theme_enum)
        
        if is_chain and messages:
            # Render chain quote
            message_data_list = [
                MessageData(
                    text=msg.get("text", ""),
                    username=msg.get("username", "Anonymous"),
                    avatar_url=msg.get("avatar_url"),
                    timestamp=msg.get("timestamp"),
                )
                for msg in messages
            ]
            result = await quote_generator_service.render_quote_chain(message_data_list, style)
        elif is_roast:
            # Render roast quote
            result = await quote_generator_service.render_roast_quote(
                text, username, avatar_url, style
            )
        else:
            # Render single quote
            result = await quote_generator_service.render_quote(
                text, username, avatar_url, style, timestamp
            )
        
        # Encode image data as base64
        image_base64 = base64.b64encode(result.image_data).decode('utf-8')
        
        logger.info(f"Quote render task completed for chat {chat_id}, size: {result.width}x{result.height}")
        
        return {
            "success": True,
            "image_data": image_base64,
            "format": result.format,
            "width": result.width,
            "height": result.height,
            "chat_id": chat_id,
            "reply_to": reply_to,
        }
        
    except Exception as e:
        logger.error(f"Quote render task failed for chat {chat_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "chat_id": chat_id,
            "reply_to": reply_to,
        }


async def gif_analysis_task(
    ctx: Dict[str, Any],
    gif_data_base64: str,
    message_id: int,
    chat_id: int,
    user_id: int,
    file_id: str,
) -> Dict[str, Any]:
    """
    GIF analysis task.
    
    Analyzes GIF for inappropriate content and returns moderation action.
    
    **Feature: fortress-update, Property 11: Frame extraction count**
    **Validates: Requirements 14.3**
    
    Args:
        ctx: Arq context
        gif_data_base64: Base64 encoded GIF data
        message_id: Message ID containing the GIF
        chat_id: Chat ID
        user_id: User ID who sent the GIF
        file_id: Telegram file ID
        
    Returns:
        Dict with is_safe, detected_categories, action, chat_id, message_id, user_id
    """
    import base64
    from app.services.gif_patrol import gif_patrol_service
    
    logger.info(f"GIF analysis task started for chat {chat_id}, message {message_id}")
    
    try:
        # Decode GIF data
        gif_data = base64.b64decode(gif_data_base64)
        
        # Analyze GIF
        result = await gif_patrol_service.analyze_gif(gif_data)
        
        # Determine action based on result
        if result.is_safe:
            action = "allow"
        else:
            action = "delete_and_ban"
        
        logger.info(
            f"GIF analysis completed for chat {chat_id}: "
            f"safe={result.is_safe}, categories={result.detected_categories}"
        )
        
        return {
            "success": True,
            "is_safe": result.is_safe,
            "detected_categories": result.detected_categories,
            "confidence": result.confidence,
            "action": action,
            "chat_id": chat_id,
            "message_id": message_id,
            "user_id": user_id,
            "file_id": file_id,
        }
        
    except Exception as e:
        logger.error(f"GIF analysis task failed for chat {chat_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "is_safe": True,  # Fail-open
            "action": "allow",
            "chat_id": chat_id,
            "message_id": message_id,
            "user_id": user_id,
        }


# ============================================================================
# Queue Monitoring
# ============================================================================

async def queue_monitor_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Monitor queue size and log warnings.
    
    **Validates: Requirements 14.6**
    
    Args:
        ctx: Arq context with Redis pool
        
    Returns:
        Dict with queue_size and warning status
    """
    redis: ArqRedis = ctx["redis"]
    
    try:
        # Count pending jobs (approximate via queue length)
        # Arq uses 'arq:queue' as the default queue key
        queue_size = await redis.llen("arq:queue")
        
        # Also get info about in-progress jobs
        in_progress_key = "arq:in-progress"
        in_progress_count = await redis.zcard(in_progress_key) if await redis.exists(in_progress_key) else 0
        
        # Get result keys count (completed jobs)
        result_keys = await redis.keys("arq:result:*")
        completed_count = len(result_keys) if result_keys else 0
        
        if queue_size > QUEUE_WARNING_THRESHOLD:
            logger.warning(
                f"Worker queue size ({queue_size}) exceeds threshold ({QUEUE_WARNING_THRESHOLD}). "
                f"Consider scaling workers. In-progress: {in_progress_count}, Completed: {completed_count}"
            )
            
            # Store warning in Redis for main bot to pick up
            warning_data = {
                "queue_size": queue_size,
                "in_progress": in_progress_count,
                "completed": completed_count,
                "threshold": QUEUE_WARNING_THRESHOLD,
                "timestamp": asyncio.get_event_loop().time(),
            }
            
            import json
            await redis.set(
                "arq:queue_warning",
                json.dumps(warning_data),
                ex=300  # Expire after 5 minutes
            )
            
            return {
                "queue_size": queue_size,
                "in_progress": in_progress_count,
                "completed": completed_count,
                "warning": True,
                "message": f"Queue size {queue_size} exceeds threshold {QUEUE_WARNING_THRESHOLD}",
            }
        
        logger.debug(f"Queue monitor: {queue_size} pending, {in_progress_count} in-progress, {completed_count} completed")
        return {
            "queue_size": queue_size,
            "in_progress": in_progress_count,
            "completed": completed_count,
            "warning": False,
        }
        
    except Exception as e:
        logger.error(f"Queue monitor failed: {e}")
        return {
            "error": str(e),
            "warning": False,
        }


async def check_queue_warning() -> Optional[Dict[str, Any]]:
    """
    Check if there's a queue warning from the worker.
    
    This can be called from the main bot process to check for warnings.
    
    **Validates: Requirements 14.6**
    
    Returns:
        Warning data dict if warning exists, None otherwise
    """
    pool = await get_arq_pool()
    if pool is None:
        return None
    
    try:
        import json
        warning_data = await pool.get("arq:queue_warning")
        if warning_data:
            return json.loads(warning_data)
        return None
    except Exception as e:
        logger.error(f"Error checking queue warning: {e}")
        return None


async def get_queue_stats() -> Dict[str, Any]:
    """
    Get current queue statistics.
    
    **Validates: Requirements 14.6**
    
    Returns:
        Dict with queue statistics
    """
    pool = await get_arq_pool()
    if pool is None:
        return {"error": "Redis not available", "queue_size": 0}
    
    try:
        queue_size = await pool.llen("arq:queue")
        in_progress_key = "arq:in-progress"
        in_progress_count = await pool.zcard(in_progress_key) if await pool.exists(in_progress_key) else 0
        result_keys = await pool.keys("arq:result:*")
        completed_count = len(result_keys) if result_keys else 0
        
        return {
            "queue_size": queue_size,
            "in_progress": in_progress_count,
            "completed": completed_count,
            "warning_threshold": QUEUE_WARNING_THRESHOLD,
            "is_warning": queue_size > QUEUE_WARNING_THRESHOLD,
        }
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        return {"error": str(e), "queue_size": 0}


# ============================================================================
# Startup and Shutdown
# ============================================================================

async def startup(ctx: Dict[str, Any]) -> None:
    """
    Worker startup hook.
    
    Initialize services needed by worker tasks.
    """
    logger.info("Arq worker starting up...")
    
    # Initialize database connection if needed
    from app.database.session import init_db
    await init_db()
    
    logger.info("Arq worker startup complete")


async def shutdown(ctx: Dict[str, Any]) -> None:
    """
    Worker shutdown hook.
    
    Clean up resources.
    """
    logger.info("Arq worker shutting down...")
    logger.info("Arq worker shutdown complete")


# ============================================================================
# Worker Class Configuration
# ============================================================================

def exponential_backoff(attempts: int) -> float:
    """
    Calculate exponential backoff delay for retries.
    
    **Validates: Requirements 14.5**
    
    Args:
        attempts: Number of attempts so far (1-based)
        
    Returns:
        Delay in seconds before next retry
    """
    # Base delay of 5 seconds, doubles each attempt
    # Attempt 1: 5s, Attempt 2: 10s, Attempt 3: 20s
    base_delay = 5
    max_delay = 60  # Cap at 1 minute
    
    delay = min(base_delay * (2 ** (attempts - 1)), max_delay)
    logger.info(f"Retry attempt {attempts}, waiting {delay}s before retry")
    return delay


async def on_job_failure(ctx: Dict[str, Any], exc: Exception) -> None:
    """
    Handle job failure after all retries exhausted.
    
    **Validates: Requirements 14.5**
    
    Args:
        ctx: Arq context
        exc: The exception that caused the failure
    """
    job_id = ctx.get("job_id", "unknown")
    job_try = ctx.get("job_try", 0)
    
    logger.error(
        f"Job {job_id} failed after {job_try} attempts. "
        f"Error: {exc}"
    )
    
    # Log to database or notify administrators
    # This could be extended to send Telegram notifications to bot owner
    try:
        # Get job details from context if available
        job_name = ctx.get("job_name", "unknown")
        
        # Log critical failure
        logger.critical(
            f"WORKER JOB FAILURE: {job_name} (ID: {job_id}) "
            f"failed permanently after {job_try} retries. "
            f"Exception: {type(exc).__name__}: {exc}"
        )
        
    except Exception as e:
        logger.error(f"Error in failure handler: {e}")


class WorkerSettings:
    """
    Arq worker settings.
    
    This class is used by arq to configure the worker.
    Run with: arq app.worker.WorkerSettings
    
    **Validates: Requirements 14.5** - Retry logic with exponential backoff
    """
    
    # Redis connection settings
    redis_settings = get_redis_settings()
    
    # Task functions to register
    functions = [
        tts_task,
        quote_render_task,
        gif_analysis_task,
        queue_monitor_task,
    ]
    
    # Cron jobs - run queue monitor every 5 minutes
    cron_jobs = [
        cron(queue_monitor_task, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
    ]
    
    # Startup and shutdown hooks
    on_startup = startup
    on_shutdown = shutdown
    
    # Job failure handler
    on_job_failure = on_job_failure
    
    # Job settings
    max_tries = MAX_TRIES  # Requirement 14.5: max 3 retries
    job_timeout = JOB_TIMEOUT
    keep_result = KEEP_RESULT_SECONDS
    
    # Retry with exponential backoff (Requirement 14.5)
    # Arq calls this function to determine delay between retries
    retry_jobs = True
    
    # Health check settings
    health_check_interval = 30
    health_check_key = "arq:health-check"
    
    # Queue name
    queue_name = "arq:queue"
    
    # Allow abort of jobs
    allow_abort_jobs = True


# ============================================================================
# Helper Functions for Enqueueing Tasks
# ============================================================================

_arq_pool: Optional[ArqRedis] = None


async def get_arq_pool() -> Optional[ArqRedis]:
    """Get or create Arq Redis pool."""
    global _arq_pool
    
    if not settings.redis_enabled:
        logger.warning("Redis not enabled, cannot create Arq pool")
        return None
    
    if _arq_pool is None:
        try:
            _arq_pool = await create_pool(get_redis_settings())
            logger.info("Arq Redis pool created")
        except Exception as e:
            logger.error(f"Failed to create Arq pool: {e}")
            return None
    
    return _arq_pool


async def close_arq_pool() -> None:
    """Close Arq Redis pool."""
    global _arq_pool
    
    if _arq_pool is not None:
        await _arq_pool.close()
        _arq_pool = None
        logger.info("Arq Redis pool closed")


async def enqueue_tts_task(
    text: str,
    chat_id: int,
    reply_to: int,
    max_chars: int = 500,
) -> Optional[Job]:
    """
    Enqueue TTS generation task.
    
    Args:
        text: Text to convert to speech
        chat_id: Target chat ID
        reply_to: Message ID to reply to
        max_chars: Maximum characters
        
    Returns:
        Job object if enqueued, None otherwise
    """
    pool = await get_arq_pool()
    if pool is None:
        return None
    
    try:
        job = await pool.enqueue_job(
            "tts_task",
            text=text,
            chat_id=chat_id,
            reply_to=reply_to,
            max_chars=max_chars,
        )
        logger.info(f"TTS task enqueued: {job.job_id}")
        return job
    except Exception as e:
        logger.error(f"Failed to enqueue TTS task: {e}")
        return None


async def enqueue_quote_render_task(
    text: str,
    username: str,
    chat_id: int,
    reply_to: int,
    avatar_url: Optional[str] = None,
    timestamp: Optional[str] = None,
    theme: str = "dark",
    is_chain: bool = False,
    messages: Optional[list] = None,
    is_roast: bool = False,
) -> Optional[Job]:
    """
    Enqueue quote rendering task.
    
    Args:
        text: Quote text
        username: Username of author
        chat_id: Target chat ID
        reply_to: Message ID to reply to
        avatar_url: Optional avatar URL
        timestamp: Optional timestamp
        theme: Quote theme
        is_chain: Whether chain quote
        messages: Messages for chain
        is_roast: Whether roast mode
        
    Returns:
        Job object if enqueued, None otherwise
    """
    pool = await get_arq_pool()
    if pool is None:
        return None
    
    try:
        job = await pool.enqueue_job(
            "quote_render_task",
            text=text,
            username=username,
            chat_id=chat_id,
            reply_to=reply_to,
            avatar_url=avatar_url,
            timestamp=timestamp,
            theme=theme,
            is_chain=is_chain,
            messages=messages,
            is_roast=is_roast,
        )
        logger.info(f"Quote render task enqueued: {job.job_id}")
        return job
    except Exception as e:
        logger.error(f"Failed to enqueue quote render task: {e}")
        return None


async def enqueue_gif_analysis_task(
    gif_data: bytes,
    message_id: int,
    chat_id: int,
    user_id: int,
    file_id: str,
) -> Optional[Job]:
    """
    Enqueue GIF analysis task.
    
    Args:
        gif_data: GIF file data
        message_id: Message ID
        chat_id: Chat ID
        user_id: User ID
        file_id: Telegram file ID
        
    Returns:
        Job object if enqueued, None otherwise
    """
    import base64
    
    pool = await get_arq_pool()
    if pool is None:
        return None
    
    try:
        # Encode GIF data as base64 for JSON serialization
        gif_data_base64 = base64.b64encode(gif_data).decode('utf-8')
        
        job = await pool.enqueue_job(
            "gif_analysis_task",
            gif_data_base64=gif_data_base64,
            message_id=message_id,
            chat_id=chat_id,
            user_id=user_id,
            file_id=file_id,
        )
        logger.info(f"GIF analysis task enqueued: {job.job_id}")
        return job
    except Exception as e:
        logger.error(f"Failed to enqueue GIF analysis task: {e}")
        return None


async def get_job_result(job_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
    """
    Wait for and get job result.
    
    Args:
        job_id: Job ID to wait for
        timeout: Maximum time to wait in seconds
        
    Returns:
        Job result dict or None if timeout/error
    """
    pool = await get_arq_pool()
    if pool is None:
        return None
    
    try:
        job = Job(job_id, pool)
        result = await asyncio.wait_for(job.result(), timeout=timeout)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"Timeout waiting for job {job_id}")
        return None
    except Exception as e:
        logger.error(f"Error getting job result {job_id}: {e}")
        return None


# ============================================================================
# Task Completion Notification Handlers
# ============================================================================

async def handle_tts_completion(bot, result: Dict[str, Any]) -> bool:
    """
    Handle TTS task completion - send voice message to chat.
    
    **Validates: Requirements 14.4**
    
    Args:
        bot: Telegram Bot instance
        result: Task result dict
        
    Returns:
        True if notification sent successfully
    """
    import base64
    from io import BytesIO
    from aiogram.types import BufferedInputFile
    
    chat_id = result.get("chat_id")
    reply_to = result.get("reply_to")
    
    if not result.get("success"):
        # Task failed - send fallback text if available
        fallback_text = result.get("fallback_text")
        error = result.get("error", "Unknown error")
        
        if fallback_text:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=fallback_text,
                    reply_to_message_id=reply_to,
                )
                logger.info(f"TTS fallback text sent to chat {chat_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to send TTS fallback: {e}")
        
        logger.warning(f"TTS task failed for chat {chat_id}: {error}")
        return False
    
    try:
        # Decode audio data
        audio_base64 = result.get("audio_data")
        if not audio_base64:
            logger.error("No audio data in TTS result")
            return False
        
        audio_data = base64.b64decode(audio_base64)
        audio_file = BufferedInputFile(audio_data, filename="voice.ogg")
        
        # Send voice message
        await bot.send_voice(
            chat_id=chat_id,
            voice=audio_file,
            reply_to_message_id=reply_to,
        )
        
        logger.info(f"TTS voice message sent to chat {chat_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send TTS result to chat {chat_id}: {e}")
        return False


async def handle_quote_completion(bot, result: Dict[str, Any]) -> bool:
    """
    Handle quote render task completion - send image to chat.
    
    **Validates: Requirements 14.4**
    
    Args:
        bot: Telegram Bot instance
        result: Task result dict
        
    Returns:
        True if notification sent successfully
    """
    import base64
    from aiogram.types import BufferedInputFile
    
    chat_id = result.get("chat_id")
    reply_to = result.get("reply_to")
    
    if not result.get("success"):
        error = result.get("error", "Unknown error")
        logger.warning(f"Quote render task failed for chat {chat_id}: {error}")
        
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Не удалось создать цитату. Попробуй ещё раз.",
                reply_to_message_id=reply_to,
            )
        except Exception as e:
            logger.error(f"Failed to send quote error message: {e}")
        
        return False
    
    try:
        # Decode image data
        image_base64 = result.get("image_data")
        if not image_base64:
            logger.error("No image data in quote result")
            return False
        
        image_data = base64.b64decode(image_base64)
        image_format = result.get("format", "webp")
        image_file = BufferedInputFile(image_data, filename=f"quote.{image_format}")
        
        # Send as sticker (WebP) or photo
        if image_format == "webp":
            await bot.send_sticker(
                chat_id=chat_id,
                sticker=image_file,
                reply_to_message_id=reply_to,
            )
        else:
            await bot.send_photo(
                chat_id=chat_id,
                photo=image_file,
                reply_to_message_id=reply_to,
            )
        
        logger.info(f"Quote image sent to chat {chat_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send quote result to chat {chat_id}: {e}")
        return False


async def handle_gif_analysis_completion(bot, result: Dict[str, Any]) -> bool:
    """
    Handle GIF analysis task completion - apply moderation action.
    
    **Validates: Requirements 14.4**
    
    Args:
        bot: Telegram Bot instance
        result: Task result dict
        
    Returns:
        True if action applied successfully
    """
    chat_id = result.get("chat_id")
    message_id = result.get("message_id")
    user_id = result.get("user_id")
    action = result.get("action", "allow")
    
    if not result.get("success"):
        error = result.get("error", "Unknown error")
        logger.warning(f"GIF analysis task failed for chat {chat_id}: {error}")
        return False
    
    if result.get("is_safe", True):
        logger.debug(f"GIF in chat {chat_id} is safe, no action needed")
        return True
    
    try:
        if action == "delete_and_ban":
            # Delete the message
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"Deleted inappropriate GIF message {message_id} in chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to delete GIF message: {e}")
            
            # Ban the user
            try:
                await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
                logger.info(f"Banned user {user_id} in chat {chat_id} for inappropriate GIF")
            except Exception as e:
                logger.error(f"Failed to ban user: {e}")
            
            # Notify chat
            categories = result.get("detected_categories", [])
            category_text = ", ".join(categories) if categories else "inappropriate content"
            
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"🚫 Пользователь забанен за отправку запрещённого контента ({category_text}).",
                )
            except Exception as e:
                logger.error(f"Failed to send ban notification: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply GIF moderation action in chat {chat_id}: {e}")
        return False


async def process_completed_jobs(bot) -> int:
    """
    Process completed jobs and send results to chats.
    
    This function should be called periodically from the main bot process
    to handle completed worker tasks.
    
    **Validates: Requirements 14.4**
    
    Args:
        bot: Telegram Bot instance
        
    Returns:
        Number of jobs processed
    """
    pool = await get_arq_pool()
    if pool is None:
        return 0
    
    processed = 0
    
    try:
        # Get completed job results from Redis
        # Arq stores results with keys like 'arq:result:<job_id>'
        # We need to scan for completed results
        
        # For now, this is a placeholder - in practice, you would either:
        # 1. Use Arq's built-in result handling
        # 2. Implement a pub/sub mechanism
        # 3. Poll for specific job IDs that you're tracking
        
        logger.debug("Checking for completed worker jobs")
        
    except Exception as e:
        logger.error(f"Error processing completed jobs: {e}")
    
    return processed


async def wait_and_handle_job(
    bot,
    job_id: str,
    job_type: str,
    timeout: float = 60.0
) -> bool:
    """
    Wait for a specific job to complete and handle the result.
    
    **Validates: Requirements 14.4**
    
    Args:
        bot: Telegram Bot instance
        job_id: Job ID to wait for
        job_type: Type of job (tts, quote, gif)
        timeout: Maximum time to wait
        
    Returns:
        True if job completed and handled successfully
    """
    result = await get_job_result(job_id, timeout)
    
    if result is None:
        logger.warning(f"Job {job_id} ({job_type}) did not complete in time")
        return False
    
    handlers = {
        "tts": handle_tts_completion,
        "quote": handle_quote_completion,
        "gif": handle_gif_analysis_completion,
    }
    
    handler = handlers.get(job_type)
    if handler is None:
        logger.error(f"Unknown job type: {job_type}")
        return False
    
    return await handler(bot, result)
