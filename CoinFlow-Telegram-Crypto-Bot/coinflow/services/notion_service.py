"""Notion integration service for CoinFlow bot."""

from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Optional, TYPE_CHECKING
from ..utils.logger import setup_logger

logger = setup_logger('notion_service')

if TYPE_CHECKING:
    from notion_client import Client

try:
    from notion_client import Client
    NOTION_AVAILABLE = True
except ImportError:
    Client = None  # type: ignore
    NOTION_AVAILABLE = False
    logger.warning("Notion client not available. Install with: pip install notion-client")


class NotionService:
    """Service for Notion integration."""
    
    def __init__(self, db):
        """Initialize Notion service."""
        self.db = db
        self.available = NOTION_AVAILABLE
        
        if not self.available:
            logger.warning("Notion service initialized but library not available")
    
    def is_available(self) -> bool:
        """Check if Notion integration is available."""
        return self.available
    
    def create_client(self, api_token: str) -> Optional[Client]:
        """
        Create Notion client with API token.
        
        Args:
            api_token: Notion integration token
        
        Returns:
            Notion client or None
        """
        if not self.available:
            return None
        
        try:
            client = Client(auth=api_token)
            logger.info("Created Notion client")
            return client
        except Exception as e:
            logger.error(f"Error creating Notion client: {e}")
            return None
    
    def get_token(self, user_id: int) -> Optional[str]:
        """
        Get stored Notion token for user.
        
        Args:
            user_id: User ID
        
        Returns:
            API token or None
        """
        try:
            # Retrieve from database (would need ExternalAuth model)
            # For now, return None
            logger.info(f"Retrieved Notion token for user {user_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving token: {e}")
            return None
    
    async def create_database(self, client: Client, parent_page_id: str, 
                             database_name: str, properties: Dict) -> Optional[str]:
        """
        Create a new Notion database.
        
        Args:
            client: Notion client
            parent_page_id: Parent page ID
            database_name: Name for the database
            properties: Database schema properties
        
        Returns:
            Database ID or None
        """
        if not self.available:
            return None
        
        try:
            database = client.databases.create(
                parent={"page_id": parent_page_id},
                title=[{"type": "text", "text": {"content": database_name}}],
                properties=properties
            )
            
            database_id = database["id"]
            logger.info(f"Created Notion database: {database_id}")
            return database_id
            
        except Exception as e:
            logger.error(f"Error creating Notion database: {e}")
            return None
    
    async def add_page_to_database(self, client: Client, database_id: str, 
                                   properties: Dict) -> bool:
        """
        Add a page to Notion database.
        
        Args:
            client: Notion client
            database_id: Target database ID
            properties: Page properties
        
        Returns:
            Success status
        """
        if not self.available:
            return False
        
        try:
            client.pages.create(
                parent={"database_id": database_id},
                properties=properties
            )
            return True
        except Exception as e:
            logger.error(f"Error adding page to database: {e}")
            return False
    
    async def export_portfolio_to_notion(self, user_id: int, api_token: str, 
                                        parent_page_id: str) -> Dict:
        """
        Export portfolio to Notion database.
        
        Args:
            user_id: User ID
            api_token: Notion API token
            parent_page_id: Parent page ID in Notion
        
        Returns:
            Result dictionary
        """
        if not self.available:
            return {'error': 'Notion integration not available'}
        
        try:
            # Create client
            client = self.create_client(api_token)
            if not client:
                return {'error': 'Failed to create Notion client'}
            
            # Get portfolio data
            portfolio_items = self.db.get_portfolio_items(user_id)
            
            if not portfolio_items:
                return {'error': 'Portfolio is empty'}
            
            # Define database schema
            properties = {
                "Asset": {"title": {}},
                "Type": {"select": {}},
                "Symbol": {"rich_text": {}},
                "Quantity": {"number": {}},
                "Purchase Price": {"number": {}},
                "Purchase Date": {"date": {}},
                "Notes": {"rich_text": {}},
                "Last Updated": {"date": {}}
            }
            
            # Create database
            database_name = f"CoinFlow Portfolio - {datetime.now().strftime('%Y-%m-%d')}"
            database_id = await self.create_database(
                client, 
                parent_page_id, 
                database_name, 
                properties
            )
            
            if not database_id:
                return {'error': 'Failed to create database'}
            
            # Add items
            added_count = 0
            for item in portfolio_items:
                page_properties = {
                    "Asset": {
                        "title": [{"text": {"content": item.asset_name}}]
                    },
                    "Type": {
                        "select": {"name": item.asset_type.capitalize()}
                    },
                    "Symbol": {
                        "rich_text": [{"text": {"content": item.asset_symbol}}]
                    },
                    "Quantity": {
                        "number": float(item.quantity)
                    },
                    "Notes": {
                        "rich_text": [{"text": {"content": item.notes or ""}}]
                    },
                    "Last Updated": {
                        "date": {"start": item.updated_at.isoformat()}
                    }
                }
                
                # Add optional fields
                if item.purchase_price:
                    page_properties["Purchase Price"] = {"number": float(item.purchase_price)}
                
                if item.purchase_date:
                    page_properties["Purchase Date"] = {"date": {"start": item.purchase_date.isoformat()}}
                
                # Add to database
                success = await self.add_page_to_database(client, database_id, page_properties)
                if success:
                    added_count += 1
            
            logger.info(f"Exported {added_count} items to Notion for user {user_id}")
            
            return {
                'success': True,
                'database_id': database_id,
                'items_added': added_count,
                'total_items': len(portfolio_items)
            }
            
        except Exception as e:
            logger.error(f"Error exporting to Notion: {e}")
            return {'error': str(e)}
    
    async def export_history_to_notion(self, user_id: int, api_token: str, 
                                       parent_page_id: str, days: int = 30) -> Dict:
        """
        Export conversion history to Notion database.
        
        Args:
            user_id: User ID
            api_token: Notion API token
            parent_page_id: Parent page ID in Notion
            days: Number of days of history
        
        Returns:
            Result dictionary
        """
        if not self.available:
            return {'error': 'Notion integration not available'}
        
        try:
            # Create client
            client = self.create_client(api_token)
            if not client:
                return {'error': 'Failed to create Notion client'}
            
            # Get history
            history = self.db.get_user_history(user_id, days=days)
            
            if not history:
                return {'error': 'No history found'}
            
            # Define database schema
            properties = {
                "Conversion": {"title": {}},
                "From": {"rich_text": {}},
                "To": {"rich_text": {}},
                "Amount": {"number": {}},
                "Result": {"number": {}},
                "Rate": {"number": {}},
                "Date": {"date": {}}
            }
            
            # Create database
            database_name = f"CoinFlow History - {datetime.now().strftime('%Y-%m-%d')}"
            database_id = await self.create_database(
                client, 
                parent_page_id, 
                database_name, 
                properties
            )
            
            if not database_id:
                return {'error': 'Failed to create database'}
            
            # Add items
            added_count = 0
            for item in history:
                page_properties = {
                    "Conversion": {
                        "title": [{"text": {"content": f"{item.from_currency} → {item.to_currency}"}}]
                    },
                    "From": {
                        "rich_text": [{"text": {"content": item.from_currency}}]
                    },
                    "To": {
                        "rich_text": [{"text": {"content": item.to_currency}}]
                    },
                    "Amount": {
                        "number": float(item.amount)
                    },
                    "Result": {
                        "number": float(item.result)
                    },
                    "Rate": {
                        "number": float(item.rate)
                    },
                    "Date": {
                        "date": {"start": item.created_at.isoformat()}
                    }
                }
                
                # Add to database
                success = await self.add_page_to_database(client, database_id, page_properties)
                if success:
                    added_count += 1
            
            logger.info(f"Exported {added_count} history items to Notion for user {user_id}")
            
            return {
                'success': True,
                'database_id': database_id,
                'items_added': added_count,
                'total_items': len(history)
            }
            
        except Exception as e:
            logger.error(f"Error exporting history to Notion: {e}")
            return {'error': str(e)}
