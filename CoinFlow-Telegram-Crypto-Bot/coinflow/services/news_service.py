"""News service for CoinFlow bot."""

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from ..utils.logger import setup_logger

logger = setup_logger('news_service')


@dataclass
class NewsItem:
    """News item data class."""
    title: str
    description: str
    link: str
    published: datetime
    source: str
    assets: List[str]  # Detected crypto assets in the news
    category: str  # 'general', 'update', 'hack', 'listing', 'regulation'


class NewsService:
    """Service for fetching and filtering crypto news."""
    
    def __init__(self, cache_ttl: int = 300):
        """
        Initialize news service.
        
        Args:
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        self.cache_ttl = cache_ttl
        self._cache = {}
        self._cache_time = {}
        
        # RSS feed sources
        self.feeds = {
            'coindesk': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
            'cointelegraph': 'https://cointelegraph.com/rss',
            'cryptoslate': 'https://cryptoslate.com/feed/',
            'decrypt': 'https://decrypt.co/feed',
            'bitcoinist': 'https://bitcoinist.com/feed/'
        }
        
        # Common crypto asset keywords
        self.asset_keywords = {
            'BTC': ['bitcoin', 'btc'],
            'ETH': ['ethereum', 'eth', 'ether'],
            'BNB': ['binance coin', 'bnb'],
            'SOL': ['solana', 'sol'],
            'ADA': ['cardano', 'ada'],
            'DOGE': ['dogecoin', 'doge'],
            'XRP': ['ripple', 'xrp'],
            'DOT': ['polkadot', 'dot'],
            'MATIC': ['polygon', 'matic'],
            'AVAX': ['avalanche', 'avax'],
            'LINK': ['chainlink', 'link'],
            'UNI': ['uniswap', 'uni'],
            'LTC': ['litecoin', 'ltc'],
            'ATOM': ['cosmos', 'atom'],
            'XLM': ['stellar', 'xlm'],
        }
        
        # Category detection keywords
        self.category_keywords = {
            'hack': ['hack', 'breach', 'exploit', 'attack', 'stolen', 'vulnerability'],
            'listing': ['listing', 'listed', 'launch', 'launched', 'debut'],
            'update': ['upgrade', 'update', 'fork', 'release', 'version'],
            'regulation': ['regulation', 'sec', 'law', 'legal', 'banned', 'approved', 'etf']
        }
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache is still valid."""
        if key not in self._cache_time:
            return False
        return (datetime.now() - self._cache_time[key]).seconds < self.cache_ttl
    
    async def fetch_news(self, sources: Optional[List[str]] = None, max_age_hours: int = 24) -> List[NewsItem]:
        """
        Fetch news from RSS feeds.
        
        Args:
            sources: List of source names to fetch from (default: all)
            max_age_hours: Maximum age of news items in hours
        
        Returns:
            List of news items
        """
        if not FEEDPARSER_AVAILABLE:
            logger.warning("feedparser not installed, news service unavailable")
            return []
        
        cache_key = f"news_{'_'.join(sources or self.feeds.keys())}"
        
        # Check cache
        if self._is_cache_valid(cache_key):
            logger.info(f"Returning cached news for {cache_key}")
            return self._cache[cache_key]
        
        news_items = []
        sources_to_fetch = sources or list(self.feeds.keys())
        
        for source in sources_to_fetch:
            if source not in self.feeds:
                logger.warning(f"Unknown news source: {source}")
                continue
            
            try:
                feed_url = self.feeds[source]
                logger.info(f"Fetching news from {source}: {feed_url}")
                
                feed = feedparser.parse(feed_url)
                
                if feed.bozo:
                    logger.error(f"Error parsing feed {source}: {feed.bozo_exception}")
                    continue
                
                for entry in feed.entries:
                    # Parse published date
                    pub_date = self._parse_date(entry)
                    
                    # Skip old news
                    if pub_date and (datetime.now() - pub_date).total_seconds() / 3600 > max_age_hours:
                        continue
                    
                    # Extract text for analysis
                    text = f"{entry.get('title', '')} {entry.get('description', '')}".lower()
                    
                    # Detect mentioned assets
                    detected_assets = self._detect_assets(text)
                    
                    # Detect category
                    category = self._detect_category(text)
                    
                    news_item = NewsItem(
                        title=entry.get('title', 'No title'),
                        description=self._clean_html(entry.get('description', '')),
                        link=entry.get('link', ''),
                        published=pub_date or datetime.now(),
                        source=source,
                        assets=detected_assets,
                        category=category
                    )
                    
                    news_items.append(news_item)
                
                logger.info(f"Fetched {len(feed.entries)} items from {source}")
                
            except Exception as e:
                logger.error(f"Error fetching news from {source}: {e}")
                continue
        
        # Sort by date (newest first)
        news_items.sort(key=lambda x: x.published, reverse=True)
        
        # Update cache
        self._cache[cache_key] = news_items
        self._cache_time[cache_key] = datetime.now()
        
        logger.info(f"Total news items fetched: {len(news_items)}")
        return news_items
    
    def _parse_date(self, entry: Dict) -> Optional[datetime]:
        """Parse date from RSS entry."""
        try:
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                return datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                return datetime(*entry.updated_parsed[:6])
        except Exception as e:
            logger.warning(f"Error parsing date: {e}")
        return None
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        clean = re.compile('<.*?>')
        text = re.sub(clean, '', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Limit length
        if len(text) > 300:
            text = text[:297] + '...'
        return text
    
    def _detect_assets(self, text: str) -> List[str]:
        """Detect crypto assets mentioned in text."""
        detected = []
        for asset, keywords in self.asset_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    detected.append(asset)
                    break
        return detected
    
    def _detect_category(self, text: str) -> str:
        """Detect news category from text."""
        for category, keywords in self.category_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return category
        return 'general'
    
    async def filter_by_asset(self, news: List[NewsItem], asset: str) -> List[NewsItem]:
        """
        Filter news items by asset.
        
        Args:
            news: List of news items
            asset: Asset symbol (e.g., 'BTC')
        
        Returns:
            Filtered list of news items
        """
        return [item for item in news if asset in item.assets]
    
    async def filter_by_category(self, news: List[NewsItem], category: str) -> List[NewsItem]:
        """
        Filter news items by category.
        
        Args:
            news: List of news items
            category: Category name
        
        Returns:
            Filtered list of news items
        """
        return [item for item in news if item.category == category]
    
    async def get_latest_for_user(self, user_subscriptions: Dict[str, List[str]], max_items: int = 10) -> List[NewsItem]:
        """
        Get latest news for user subscriptions.
        
        Args:
            user_subscriptions: Dict of {asset: [categories]}
            max_items: Maximum number of items to return
        
        Returns:
            List of relevant news items
        """
        all_news = await self.fetch_news()
        relevant_news = []
        
        for item in all_news:
            for asset, categories in user_subscriptions.items():
                if asset in item.assets:
                    # If no specific categories, include all
                    if not categories or item.category in categories:
                        relevant_news.append(item)
                        break
        
        # Remove duplicates and limit
        seen = set()
        unique_news = []
        for item in relevant_news:
            if item.link not in seen:
                seen.add(item.link)
                unique_news.append(item)
                if len(unique_news) >= max_items:
                    break
        
        return unique_news
    
    def format_news_message(self, item: NewsItem, lang: str = 'en') -> str:
        """
        Format news item as Telegram message.
        
        Args:
            item: News item
            lang: Language ('en' or 'ru')
        
        Returns:
            Formatted message string
        """
        category_emoji = {
            'general': '📰',
            'hack': '🚨',
            'listing': '🎉',
            'update': '🔄',
            'regulation': '⚖️'
        }
        
        emoji = category_emoji.get(item.category, '📰')
        assets_str = ', '.join(item.assets) if item.assets else 'Crypto'
        
        message = f"{emoji} **{item.title}**\n\n"
        message += f"{item.description}\n\n"
        message += f"🏷️ {assets_str} | 📅 {item.published.strftime('%Y-%m-%d %H:%M')}\n"
        message += f"📰 Source: {item.source.title()}\n"
        message += f"🔗 [Read more]({item.link})"
        
        return message
