"""Currency rate caching system."""

from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
import threading


class CurrencyCache:
    """Thread-safe cache for currency rates."""
    
    def __init__(self, ttl_seconds: int = 60):
        """
        Initialize cache.
        
        Args:
            ttl_seconds: Time to live for cached entries in seconds
        """
        self.cache: Dict[str, Tuple[float, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self.lock = threading.Lock()
    
    def get(self, key: str) -> Optional[float]:
        """
        Get cached rate if not expired.
        
        Args:
            key: Cache key (e.g., "BTC_USD")
        
        Returns:
            Cached rate or None if not found/expired
        """
        with self.lock:
            if key in self.cache:
                rate, timestamp = self.cache[key]
                if datetime.now() - timestamp < self.ttl:
                    return rate
                else:
                    # Expired, remove it
                    del self.cache[key]
        return None
    
    def set(self, key: str, rate: float):
        """
        Cache a rate.
        
        Args:
            key: Cache key (e.g., "BTC_USD")
            rate: Rate value to cache
        """
        with self.lock:
            self.cache[key] = (rate, datetime.now())
    
    def clear(self):
        """Clear all cached entries."""
        with self.lock:
            self.cache.clear()
    
    def cleanup_expired(self):
        """Remove expired entries from cache."""
        with self.lock:
            now = datetime.now()
            expired_keys = [
                key for key, (_, timestamp) in self.cache.items()
                if now - timestamp >= self.ttl
            ]
            for key in expired_keys:
                del self.cache[key]
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self.lock:
            total = len(self.cache)
            now = datetime.now()
            valid = sum(1 for _, timestamp in self.cache.values() 
                       if now - timestamp < self.ttl)
            return {
                'total_entries': total,
                'valid_entries': valid,
                'expired_entries': total - valid
            }


# Alias for backward compatibility
Cache = CurrencyCache
