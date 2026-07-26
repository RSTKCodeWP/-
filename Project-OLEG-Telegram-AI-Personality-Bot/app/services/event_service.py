"""
Event Service - Dynamic Weekly/Daily Events System.

Manages AI-generated random events that modify game mechanics and engage users.
Requirements: Dynamic events, AI generation, Integration with existing systems.
"""

import logging
import random
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

from aiogram import Bot
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.models import GlobalEvent  # We will need to create this model
from app.utils import utc_now
from app.services.ollama_client import generate_text_reply

logger = logging.getLogger(__name__)

# Constants
EVENT_CHANNEL_ID = -1002739723  # Steam Deck OC
EVENT_TOPIC_ID = 739723  # Games topic

class EventType(str, Enum):
    WEEKLY = "weekly"
    DAILY = "daily"

class EventModifier(str, Enum):
    """Possible game modifiers activated by events."""
    DOUBLE_EXP = "double_exp"          # 2x XP/Reputation
    DOUBLE_COINS = "double_coins"      # 2x Coins from games
    GUILD_BOOST = "guild_boost"        # 2x Guild Points
    MARRIAGE_BOOST = "marriage_boost"  # 2x Love points / shared inventory luck
    PVP_FRENZY = "pvp_frenzy"          # No penalty for losing PvP
    FISHING_LUCK = "fishing_luck"      # Better fish chances
    GROW_BOOST = "grow_boost"          # +50% growth size
    QUEST_REWARD = "quest_reward"      # 2x Quest rewards
    CASINO_LUCK = "casino_luck"        # Higher win chance (slightly)

class EventService:
    def __init__(self):
        self.current_weekly_event: Optional[Dict] = None
        self.current_daily_event: Optional[Dict] = None
    
    async def get_active_modifiers(self) -> List[EventModifier]:
        """Get all currently active modifiers from daily and weekly events."""
        modifiers = []
        if self.current_weekly_event:
            modifiers.extend(self.current_weekly_event.get("modifiers", []))
        if self.current_daily_event:
            modifiers.extend(self.current_daily_event.get("modifiers", []))
        return modifiers

    async def has_modifier(self, modifier: EventModifier) -> bool:
        """Check if a specific modifier is active."""
        active_mods = await self.get_active_modifiers()
        return modifier in active_mods

    async def generate_event(self, event_type: EventType, bot: Bot) -> None:
        """Generate and start a new event."""
        logger.info(f"Generating new {event_type} event...")
        
        # 1. Select Random Modifiers & Theme
        available_modifiers = list(EventModifier)
        selected_modifier = random.choice(available_modifiers)
        
        # 2. Generate Flavor Text via AI
        prompt = (
            f"Придумай крутое, веселое название и описание для игрового ивента в чате.\n"
            f"Тип: {event_type.value} (длится {'неделю' if event_type == EventType.WEEKLY else 'день'}).\n"
            f"Бонус: {self._get_modifier_description(selected_modifier)}.\n"
            f"Стиль: киберпанк, фэнтези, или треш-угар. С юмором.\n"
            f"Ответ верни в JSON формате: {{'title': '...', 'description': '...', 'lore': '...'}}"
        )
        
        try:
            ai_response = await generate_text_reply(
                user_text=prompt,
                username="system",
                chat_context=None,
                conversation_history=None
            )
            # Clean up response to get JSON
            ai_response = ai_response.replace("```json", "").replace("```", "").strip()
            event_data = json.loads(ai_response)
        except Exception as e:
            logger.error(f"AI Generation failed: {e}. Using fallback.")
            event_data = {
                "title": f"Ивент: {selected_modifier.value.upper()}",
                "description": self._get_modifier_description(selected_modifier),
                "lore": "Система дала сбой, но вам это на руку!"
            }

        # 3. Save to DB
        async_session = get_session()
        async with async_session() as session:
            # Deactivate previous events of same type
            await session.execute(
                update(GlobalEvent)
                .where(GlobalEvent.type == event_type.value, GlobalEvent.is_active == True)
                .values(is_active=False)
            )
            
            new_event = GlobalEvent(
                type=event_type.value,
                title=event_data.get("title", "Unknown Event"),
                description=event_data.get("description", ""),
                lore=event_data.get("lore", ""),
                modifiers=json.dumps([selected_modifier.value]),
                start_time=utc_now(),
                end_time=utc_now() + timedelta(days=7 if event_type == EventType.WEEKLY else 1),
                is_active=True
            )
            session.add(new_event)
            await session.commit()
            
            # Cache in memory
            event_obj = {
                "type": event_type,
                "title": new_event.title,
                "description": new_event.description,
                "lore": new_event.lore,
                "modifiers": [selected_modifier],
                "start_time": new_event.start_time,
                "end_time": new_event.end_time
            }
        
        if event_type == EventType.WEEKLY:
            self.current_weekly_event = event_obj
        else:
            self.current_daily_event = event_obj
            
        # 4. Announce
        await self._announce_event(bot, event_obj)

    async def load_active_events(self):
        """Load active events from DB on startup."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(GlobalEvent).where(GlobalEvent.is_active == True)
            )
            events = result.scalars().all()
            
            self.current_weekly_event = None
            self.current_daily_event = None
            
            now = utc_now()
            for event in events:
                # Check expiration - ensure both datetimes are timezone-aware
                if event.end_time:
                    # Make end_time timezone-aware if it's naive
                    end_time_aware = event.end_time if event.end_time.tzinfo else event.end_time.replace(tzinfo=now.tzinfo)
                    if end_time_aware < now:
                        event.is_active = False
                        continue
                
                event_obj = {
                    "type": EventType(event.type),
                    "title": event.title,
                    "description": event.description,
                    "lore": event.lore,
                    "modifiers": [EventModifier(m) for m in json.loads(event.modifiers)],
                    "start_time": event.start_time,
                    "end_time": event.end_time
                }
                
                if event.type == EventType.WEEKLY.value:
                    self.current_weekly_event = event_obj
                elif event.type == EventType.DAILY.value:
                    self.current_daily_event = event_obj
            
            await session.commit()

    def _get_modifier_description(self, modifier: EventModifier) -> str:
        descriptions = {
            EventModifier.DOUBLE_EXP: "Двойной опыт и репутация",
            EventModifier.DOUBLE_COINS: "Двойные монеты в играх",
            EventModifier.GUILD_BOOST: "Усиление гильдий (очки x2)",
            EventModifier.MARRIAGE_BOOST: "Время любви (бонусы парам)",
            EventModifier.PVP_FRENZY: "PvP без потерь рейтинга",
            EventModifier.FISHING_LUCK: "Удачная рыбалка (редкая рыба чаще)",
            EventModifier.GROW_BOOST: "Гормональный всплеск (+50% к росту)",
            EventModifier.QUEST_REWARD: "Щедрые заказчики (награды x2)",
            EventModifier.CASINO_LUCK: "Счастливый случай в казино",
        }
        return descriptions.get(modifier, "Бонусы активны")

    async def _announce_event(self, bot: Bot, event: Dict) -> None:
        """Send announcement to the special topic."""
        duration = "Эта неделя" if event["type"] == EventType.WEEKLY else "Сегодня"
        
        text = (
            f"🚨 <b>НОВЫЙ ИВЕНТ: {event['title']}</b> 🚨\n\n"
            f"{event['lore']}\n\n"
            f"⚡ <b>Бонус:</b> {event['description']}\n"
            f"⏳ <b>Длительность:</b> {duration}\n\n"
            f"<i>Успей воспользоваться!</i>"
        )
        
        try:
            await bot.send_message(
                chat_id=EVENT_CHANNEL_ID,
                message_thread_id=EVENT_TOPIC_ID,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to announce event: {e}")

# Singleton
event_service = EventService()
