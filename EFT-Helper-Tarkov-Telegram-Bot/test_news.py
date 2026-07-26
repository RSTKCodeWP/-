"""Quick test to check news content."""
import asyncio
import sys
from services.news_service import NewsService

async def main():
    ns = NewsService()
    news = await ns.get_latest_news('ru', 30)
    
    print(f"\n{'='*80}")
    print(f"Found {len(news)} news items from Telegram RSS")
    print(f"{'='*80}\n")
    
    found_release = False
    
    for i, item in enumerate(news, 1):
        title_lower = item['title'].lower()
        desc_lower = item['description'].lower()
        combined = f"{title_lower} {desc_lower}"
        
        # Check for release keywords
        has_15 = '15' in combined
        has_november = 'ноябр' in combined or 'november' in combined
        has_release = 'релиз' in combined or 'release' in combined
        has_close = 'близко' in combined or 'close' in combined
        has_steam = 'steam' in combined or 'стим' in combined
        has_exact = '15 ноябр' in combined or '15 november' in combined
        
        if has_exact or (has_15 and has_november) or (has_release and has_close):
            print(f"\n🔥 NEWS #{i} - POTENTIAL RELEASE INFO:")
            print(f"   Title: {item['title']}")
            print(f"   Date: {item['date']}")
            print(f"   Desc: {item['description'][:200]}...")
            print(f"   Flags: 15={has_15}, nov={has_november}, release={has_release}, close={has_close}, steam={has_steam}, exact={has_exact}")
            found_release = True
        elif has_steam or has_release:
            print(f"\n💎 NEWS #{i} - Steam/Release mention:")
            print(f"   Title: {item['title'][:80]}")
            print(f"   Flags: release={has_release}, steam={has_steam}")
    
    print(f"\n{'='*80}")
    if found_release:
        print("✅ Found news with release date info!")
    else:
        print("❌ No news with '15 ноября' found in {len(news)} items")
        print("\nThis means the post is either:")
        print("  1. Older than the RSS feed limit")
        print("  2. Not in the Telegram channel")
        print("  3. Removed or edited")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    asyncio.run(main())
