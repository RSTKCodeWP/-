"""Export service for CoinFlow bot."""

import csv
import io
import zipfile
from datetime import datetime
from typing import Dict, List
from ..utils.logger import setup_logger

logger = setup_logger('export')


class ExportService:
    """Service for exporting user data."""
    
    def __init__(self, db):
        """Initialize export service."""
        self.db = db
    
    def export_portfolio_csv(self, user_id: int, portfolio_data: List[Dict]) -> str:
        """
        Export portfolio to CSV format.
        
        Args:
            user_id: User's Telegram ID
            portfolio_data: Portfolio items with current values
        
        Returns:
            CSV string
        """
        try:
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'Asset Type',
                'Symbol',
                'Name',
                'Quantity',
                'Current Price (USD)',
                'Total Value (USD)',
                'Purchase Price (USD)',
                'Profit/Loss (USD)',
                'Profit/Loss (%)',
                'Added Date'
            ])
            
            # Data rows
            for item in portfolio_data:
                writer.writerow([
                    item.get('asset_type', ''),
                    item.get('asset_symbol', ''),
                    item.get('asset_name', ''),
                    item.get('quantity', 0),
                    item.get('current_price_usd', 0) or 0,
                    item.get('current_value_usd', 0) or 0,
                    item.get('purchase_price', '') or '',
                    item.get('profit_loss_usd', '') or '',
                    item.get('profit_loss_pct', '') or '',
                    item.get('created_at', '')
                ])
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error exporting portfolio to CSV: {e}")
            return ""
    
    def export_alerts_csv(self, user_id: int) -> str:
        """
        Export alerts to CSV format.
        
        Args:
            user_id: User's Telegram ID
        
        Returns:
            CSV string
        """
        try:
            alerts = self.db.get_alerts(user_id)
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'Pair',
                'Condition',
                'Target Price',
                'Created Date'
            ])
            
            # Data rows
            for alert in alerts:
                writer.writerow([
                    alert.pair,
                    alert.condition,
                    alert.target,
                    alert.created_at.isoformat()
                ])
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error exporting alerts to CSV: {e}")
            return ""
    
    def export_history_csv(self, user_id: int) -> str:
        """
        Export conversion history to CSV format.
        
        Args:
            user_id: User's Telegram ID
        
        Returns:
            CSV string
        """
        try:
            history = self.db.get_conversion_history(user_id, limit=100)
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'From Currency',
                'To Currency',
                'Amount',
                'Result',
                'Rate',
                'Timestamp'
            ])
            
            # Data rows
            for h in history:
                writer.writerow([
                    h.from_currency,
                    h.to_currency,
                    h.amount,
                    h.result,
                    h.rate,
                    h.timestamp.isoformat()
                ])
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error exporting history to CSV: {e}")
            return ""
    
    def create_export_zip(self, user_id: int, portfolio_data: List[Dict] = None) -> bytes:
        """
        Create ZIP archive with all user data.
        
        Args:
            user_id: User's Telegram ID
            portfolio_data: Optional portfolio data (to avoid re-fetching)
        
        Returns:
            ZIP file bytes
        """
        try:
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Portfolio
                if portfolio_data:
                    portfolio_csv = self.export_portfolio_csv(user_id, portfolio_data)
                    if portfolio_csv:
                        zip_file.writestr('portfolio.csv', portfolio_csv)
                
                # Alerts
                alerts_csv = self.export_alerts_csv(user_id)
                if alerts_csv:
                    zip_file.writestr('alerts.csv', alerts_csv)
                
                # History
                history_csv = self.export_history_csv(user_id)
                if history_csv:
                    zip_file.writestr('conversion_history.csv', history_csv)
                
                # Favorites
                favorites = self.db.get_favorites(user_id)
                if favorites:
                    favorites_csv = "Currency\n" + "\n".join(favorites)
                    zip_file.writestr('favorites.txt', favorites_csv)
                
                # User info
                user = self.db.get_user(user_id)
                if user:
                    user_info = f"""User Information
====================
Telegram ID: {user.telegram_id}
Language: {user.lang}
Prediction Model: {user.prediction_model}
RUB Source: {user.rub_source}
Account Created: {user.created_at.isoformat()}
Last Updated: {user.updated_at.isoformat()}

Export Date: {datetime.utcnow().isoformat()}
"""
                    zip_file.writestr('user_info.txt', user_info)
            
            zip_buffer.seek(0)
            return zip_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error creating export ZIP: {e}")
            return b""
    
    def get_export_filename(self, user_id: int, export_type: str) -> str:
        """
        Generate filename for export.
        
        Args:
            user_id: User's Telegram ID
            export_type: Type of export (portfolio, alerts, history, all)
        
        Returns:
            Filename string
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        
        if export_type == 'all':
            return f"coinflow_export_{user_id}_{timestamp}.zip"
        else:
            return f"coinflow_{export_type}_{user_id}_{timestamp}.csv"
