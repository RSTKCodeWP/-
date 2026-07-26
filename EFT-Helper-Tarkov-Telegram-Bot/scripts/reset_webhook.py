"""Reset webhook for Telegram bot."""
import asyncio
import sys
import os
from dotenv import load_dotenv
import aiohttp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


async def reset_webhook():
    """Reset webhook to use long polling."""
    bot_token = os.getenv("BOT_TOKEN")
    
    if not bot_token:
        print("ERROR: BOT_TOKEN not found in .env")
        return
    
    url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    
    print("Resetting webhook...")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"drop_pending_updates": True}) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("ok"):
                    print("SUCCESS: Webhook deleted!")
                    print("You can now use long polling.")
                else:
                    print(f"ERROR: {data}")
            else:
                print(f"ERROR: HTTP {response.status}")


if __name__ == "__main__":
    asyncio.run(reset_webhook())

