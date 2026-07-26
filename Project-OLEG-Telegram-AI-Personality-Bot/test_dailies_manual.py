import asyncio
import logging
from app.services.dailies import dailies_service
from app.database.session import get_session, init_db
from app.database.models import MessageLog
from sqlalchemy import select, func

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHAT_ID = -1002175322045

async def test_summary():
    print("🚀 Initializing DB...")
    await init_db()
    
    print(f"🚀 Testing daily summary for chat {CHAT_ID}...")
    
    async_session = get_session()
    async with async_session() as session:
        # Check message count first
        count = await session.scalar(
            select(func.count(MessageLog.id)).filter(MessageLog.chat_id == CHAT_ID)
        )
        print(f"📊 Total messages in DB for this chat: {count}")
        
        if count == 0:
            print("⚠️ No messages found! Summary will definitely be skipped.")
            return

        # Try to generate summary for TODAY (so far)
        print("⏳ Generating summary for TODAY...")
        try:
            # We pass session to reuse it
            summary = await dailies_service.generate_summary(CHAT_ID, session, for_today=True)
            
            if summary:
                print("✅ Summary object created!")
                print(f"Has activity: {summary.has_activity}")
                print(f"Message count today: {summary.message_count}")
                
                if summary.has_activity:
                    print(f"LLM Summary: {summary.llm_summary}")
                    print("-" * 20)
                    print(dailies_service.format_summary(summary))
                else:
                    print("⚠️ Summary has no activity (filtered out)")
            else:
                print("❌ Summary returned None (error occurred)")
                
        except Exception as e:
            print(f"🔥 Error generating summary: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_summary())
