"""Check if we can get quest build requirements from any source."""
import asyncio
import aiohttp
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient

async def check_wiki_api():
    """Check Tarkov Wiki API for quest data."""
    # Try alternative API endpoint
    url = "https://api.tarkov.dev/graphql"
    
    # Try to get more detailed quest info
    query = """
    {
        task(id: "5ac23c6186f7741247042bad") {
            id
            name
            objectives {
                id
                type
                description
                ... on TaskObjectiveBuildItem {
                    item {
                        id
                        name
                    }
                    attributes {
                        name
                        requirement {
                            compareMethod
                            value
                        }
                    }
                }
            }
        }
    }
    """
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json={"query": query}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print("✅ Got response from API")
                    print(f"Data: {data}")
                    return data
                else:
                    print(f"❌ API returned status {resp.status}")
                    return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

async def check_tarkovdev_specific():
    """Check tarkov.dev specific task endpoint."""
    api = TarkovAPIClient()
    
    # Try getting a specific task with more details
    query = """
    {
        task(id: "5ac23c6186f7741247042bad") {
            id
            name
            minPlayerLevel
            objectives {
                id
                type
                description
                optional
            }
        }
    }
    """
    
    try:
        data = await api._make_graphql_request(query)
        print("\n📋 Specific task query result:")
        print(data)
    finally:
        await api.close()

async def main():
    print("="*70)
    print("Checking quest requirements availability")
    print("="*70)
    
    print("\n1. Trying Wiki API with detailed attributes...")
    await check_wiki_api()
    
    print("\n2. Trying specific task query...")
    await check_tarkovdev_specific()
    
    print("\n" + "="*70)
    print("CONCLUSION:")
    print("If no detailed attributes found, need to use hardcoded data")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())
