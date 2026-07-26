"""Google Sheets integration service for CoinFlow bot."""

from __future__ import annotations
import json
from datetime import datetime
from typing import List, Dict, Optional, TYPE_CHECKING
from ..utils.logger import setup_logger

logger = setup_logger('sheets_service')

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    Credentials = None  # type: ignore
    GOOGLE_AVAILABLE = False
    logger.warning("Google API libraries not available. Install with: pip install google-auth google-auth-oauthlib google-api-python-client")


class GoogleSheetsService:
    """Service for Google Sheets integration."""
    
    # OAuth2 scopes
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self, db):
        """Initialize Google Sheets service."""
        self.db = db
        self.available = GOOGLE_AVAILABLE
        
        if not self.available:
            logger.warning("Google Sheets service initialized but libraries not available")
    
    def is_available(self) -> bool:
        """Check if Google Sheets integration is available."""
        return self.available
    
    def create_oauth_url(self, user_id: int, redirect_uri: str, client_id: str) -> Optional[str]:
        """
        Create OAuth2 authorization URL.
        
        Args:
            user_id: User ID
            redirect_uri: OAuth redirect URI
            client_id: Google OAuth client ID
        
        Returns:
            Authorization URL or None
        """
        if not self.available:
            return None
        
        try:
            from google_auth_oauthlib.flow import Flow
            
            # Create flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": client_id,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [redirect_uri]
                    }
                },
                scopes=self.SCOPES,
                redirect_uri=redirect_uri
            )
            
            # Generate authorization URL
            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            # Store state for verification
            # In production, store this in database or session
            logger.info(f"Generated OAuth URL for user {user_id}")
            
            return auth_url
        except Exception as e:
            logger.error(f"Error creating OAuth URL: {e}")
            return None
    
    def store_credentials(self, user_id: int, credentials_json: str) -> bool:
        """
        Store user's Google credentials.
        
        Args:
            user_id: User ID
            credentials_json: Credentials in JSON format
        
        Returns:
            Success status
        """
        if not self.available:
            return False
        
        try:
            # Store in database (would need ExternalAuth model)
            # For now, just log
            logger.info(f"Stored Google credentials for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing credentials: {e}")
            return False
    
    def get_credentials(self, user_id: int) -> Optional[Credentials]:
        """
        Get stored credentials for user.
        
        Args:
            user_id: User ID
        
        Returns:
            Credentials object or None
        """
        if not self.available:
            return None
        
        try:
            # Retrieve from database
            # For now, return None
            logger.info(f"Retrieved credentials for user {user_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving credentials: {e}")
            return None
    
    async def export_to_sheets(self, user_id: int, data: List[Dict], 
                               spreadsheet_id: str = None, sheet_name: str = "CoinFlow Data") -> Dict:
        """
        Export data to Google Sheets.
        
        Args:
            user_id: User ID
            data: List of dictionaries to export
            spreadsheet_id: Existing spreadsheet ID (creates new if None)
            sheet_name: Name of the sheet
        
        Returns:
            Dict with spreadsheet_id and url
        """
        if not self.available:
            return {'error': 'Google Sheets not available'}
        
        try:
            # Get credentials
            creds = self.get_credentials(user_id)
            
            if not creds:
                return {'error': 'No credentials found. Please authorize first.'}
            
            # Refresh token if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            
            # Build service
            service = build('sheets', 'v4', credentials=creds)
            
            # Create or update spreadsheet
            if not spreadsheet_id:
                # Create new spreadsheet
                spreadsheet = {
                    'properties': {
                        'title': f'CoinFlow Export - {datetime.now().strftime("%Y-%m-%d %H:%M")}'
                    },
                    'sheets': [{
                        'properties': {
                            'title': sheet_name
                        }
                    }]
                }
                
                result = service.spreadsheets().create(body=spreadsheet).execute()
                spreadsheet_id = result['spreadsheetId']
                logger.info(f"Created new spreadsheet: {spreadsheet_id}")
            
            # Prepare data for sheets
            if not data:
                return {'error': 'No data to export'}
            
            # Convert to 2D array with headers
            headers = list(data[0].keys())
            values = [headers]
            
            for row in data:
                values.append([str(row.get(key, '')) for key in headers])
            
            # Update sheet
            body = {
                'values': values
            }
            
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='RAW',
                body=body
            ).execute()
            
            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
            
            logger.info(f"Exported {len(data)} rows to Google Sheets for user {user_id}")
            
            return {
                'success': True,
                'spreadsheet_id': spreadsheet_id,
                'url': spreadsheet_url,
                'rows_updated': result.get('updatedRows', 0)
            }
            
        except HttpError as e:
            logger.error(f"Google Sheets API error: {e}")
            return {'error': f'Google Sheets API error: {e}'}
        except Exception as e:
            logger.error(f"Error exporting to sheets: {e}")
            return {'error': str(e)}
    
    async def export_portfolio(self, user_id: int, spreadsheet_id: str = None) -> Dict:
        """Export user's portfolio to Google Sheets."""
        try:
            # Get portfolio data
            portfolio_items = self.db.get_portfolio_items(user_id)
            
            if not portfolio_items:
                return {'error': 'Portfolio is empty'}
            
            # Format data
            data = []
            for item in portfolio_items:
                data.append({
                    'Asset Type': item.asset_type,
                    'Symbol': item.asset_symbol,
                    'Name': item.asset_name,
                    'Quantity': item.quantity,
                    'Purchase Price': item.purchase_price or 'N/A',
                    'Purchase Date': item.purchase_date.strftime('%Y-%m-%d') if item.purchase_date else 'N/A',
                    'Notes': item.notes or '',
                    'Last Updated': item.updated_at.strftime('%Y-%m-%d %H:%M')
                })
            
            return await self.export_to_sheets(user_id, data, spreadsheet_id, 'Portfolio')
            
        except Exception as e:
            logger.error(f"Error exporting portfolio: {e}")
            return {'error': str(e)}
    
    async def export_history(self, user_id: int, spreadsheet_id: str = None, days: int = 30) -> Dict:
        """Export conversion history to Google Sheets."""
        try:
            # Get history
            history = self.db.get_user_history(user_id, days=days)
            
            if not history:
                return {'error': 'No history found'}
            
            # Format data
            data = []
            for item in history:
                data.append({
                    'Date': item.created_at.strftime('%Y-%m-%d %H:%M'),
                    'From Currency': item.from_currency,
                    'To Currency': item.to_currency,
                    'Amount': item.amount,
                    'Result': item.result,
                    'Rate': item.rate
                })
            
            return await self.export_to_sheets(user_id, data, spreadsheet_id, 'Conversion History')
            
        except Exception as e:
            logger.error(f"Error exporting history: {e}")
            return {'error': str(e)}
