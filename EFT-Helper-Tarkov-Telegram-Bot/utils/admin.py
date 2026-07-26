"""Admin utilities for checking admin rights."""
import os
from typing import List


def get_admin_ids() -> List[int]:
    """Get list of admin user IDs from environment variables."""
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    if not admin_ids_str:
        return []
    
    try:
        return [int(admin_id.strip()) for admin_id in admin_ids_str.split(",") if admin_id.strip()]
    except ValueError:
        return []


def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in get_admin_ids()
