"""Configuration management for the EFT Helper bot."""
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Bot settings loaded from environment variables."""
    
    def __init__(self):
        self.BOT_TOKEN = os.getenv("BOT_TOKEN", "")
        self.ADMIN_IDS = os.getenv("ADMIN_IDS", "")
        self.DATABASE_PATH = os.getenv("DATABASE_PATH", "eft_helper.db")
        
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required in .env file")
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Parse admin IDs from comma-separated string."""
        if not self.ADMIN_IDS:
            return []
        return [int(id_.strip()) for id_ in self.ADMIN_IDS.split(",") if id_.strip()]


settings = Settings()
