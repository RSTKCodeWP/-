#!/usr/bin/env python3
"""
CoinFlow Bot v3.1.0 - Main entry point
Personal Investment Consultant with advanced analytics and trading tools
"""

import sys
from coinflow.bot import setup_bot
from coinflow.utils import setup_logger
from coinflow.config import config

logger = setup_logger('main', config.LOG_FILE, config.LOG_LEVEL)


def main():
    """Main function to run the bot."""
    try:
        logger.info("="*50)
        logger.info("Starting CoinFlow Bot v3.1.0")
        logger.info("="*50)
        
        # Setup bot
        app = setup_bot()
        
        # Run the bot
        logger.info("🤖 CoinFlow Bot v3.1.0 is running...")
        logger.info("Press Ctrl+C to stop")
        
        app.run_polling(allowed_updates=['message', 'callback_query', 'inline_query'])
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
