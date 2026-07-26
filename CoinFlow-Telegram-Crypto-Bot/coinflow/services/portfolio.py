"""Portfolio management service for CoinFlow bot."""

from typing import Dict, List, Optional
from datetime import datetime
from ..database.repository import DatabaseRepository
from ..utils.logger import setup_logger

logger = setup_logger('portfolio')


class PortfolioService:
    """Service for managing user portfolios."""
    
    def __init__(self, db: DatabaseRepository, converter, stock_service, cs2_service):
        """
        Initialize portfolio service.
        
        Args:
            db: Database repository
            converter: Currency converter service
            stock_service: Stock market service
            cs2_service: CS2 market service
        """
        self.db = db
        self.converter = converter
        self.stock_service = stock_service
        self.cs2_service = cs2_service
    
    def add_asset(self, user_id: int, asset_type: str, asset_symbol: str,
                  quantity: float, purchase_price: float = None,
                  notes: str = None) -> Dict:
        """
        Add an asset to user's portfolio.
        
        Args:
            user_id: User's Telegram ID
            asset_type: Type of asset ('crypto', 'stock', 'fiat', 'cs2')
            asset_symbol: Asset symbol/ticker
            quantity: Quantity owned
            purchase_price: Optional purchase price in USD
            notes: Optional notes
        
        Returns:
            Dict with result status and item info
        """
        try:
            # Get asset name based on type
            asset_name = self._get_asset_name(asset_type, asset_symbol)
            
            if not asset_name:
                return {
                    'success': False,
                    'error': f'Unknown asset: {asset_symbol}'
                }
            
            # Add to database
            item = self.db.add_portfolio_item(
                user_id=user_id,
                asset_type=asset_type,
                asset_symbol=asset_symbol,
                asset_name=asset_name,
                quantity=quantity,
                purchase_price=purchase_price,
                purchase_date=datetime.utcnow() if purchase_price else None,
                notes=notes
            )
            
            logger.info(f"Added {quantity} {asset_symbol} to portfolio for user {user_id}")
            
            return {
                'success': True,
                'item': item.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Error adding asset to portfolio: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_portfolio(self, user_id: int, asset_type: str = None) -> List[Dict]:
        """
        Get user's portfolio with current valuations.
        
        Args:
            user_id: User's Telegram ID
            asset_type: Optional filter by asset type
        
        Returns:
            List of portfolio items with current values
        """
        try:
            items = self.db.get_portfolio_items(user_id, asset_type)
            
            portfolio = []
            for item in items:
                # Get current price
                current_price = self._get_current_price(item.asset_type, item.asset_symbol, user_id)
                
                # Calculate values
                current_value_usd = current_price * item.quantity if current_price else None
                
                # Calculate profit/loss if purchase price is available
                profit_loss_usd = None
                profit_loss_pct = None
                if item.purchase_price and current_price:
                    profit_loss_usd = (current_price - item.purchase_price) * item.quantity
                    profit_loss_pct = ((current_price - item.purchase_price) / item.purchase_price) * 100
                
                portfolio.append({
                    **item.to_dict(),
                    'current_price_usd': current_price,
                    'current_value_usd': current_value_usd,
                    'profit_loss_usd': profit_loss_usd,
                    'profit_loss_pct': profit_loss_pct
                })
            
            return portfolio
            
        except Exception as e:
            logger.error(f"Error getting portfolio: {e}")
            return []
    
    def get_portfolio_summary(self, user_id: int) -> Dict:
        """
        Get portfolio summary with total values and distribution.
        
        Args:
            user_id: User's Telegram ID
        
        Returns:
            Dict with summary statistics
        """
        try:
            portfolio = self.get_portfolio(user_id)
            
            if not portfolio:
                return {
                    'total_items': 0,
                    'total_value_usd': 0,
                    'total_value_rub': 0,
                    'by_type': {},
                    'total_profit_loss_usd': 0,
                    'total_profit_loss_pct': 0
                }
            
            # Calculate totals
            total_value_usd = sum(item.get('current_value_usd', 0) or 0 for item in portfolio)
            total_invested = sum(
                (item.get('purchase_price', 0) or 0) * item['quantity'] 
                for item in portfolio if item.get('purchase_price')
            )
            
            total_profit_loss_usd = sum(item.get('profit_loss_usd', 0) or 0 for item in portfolio)
            total_profit_loss_pct = 0
            if total_invested > 0:
                total_profit_loss_pct = (total_profit_loss_usd / total_invested) * 100
            
            # Get USD to RUB rate
            usd_to_rub = 1.0
            try:
                usd_to_rub = self.converter.get_crypto_rate_aggregated('USD', 'RUB', user_id) or 1.0
            except:
                pass
            
            total_value_rub = total_value_usd * usd_to_rub
            
            # Distribution by type
            by_type = {}
            for item in portfolio:
                asset_type = item['asset_type']
                value = item.get('current_value_usd', 0) or 0
                if asset_type not in by_type:
                    by_type[asset_type] = {
                        'count': 0,
                        'total_value_usd': 0,
                        'percentage': 0
                    }
                by_type[asset_type]['count'] += 1
                by_type[asset_type]['total_value_usd'] += value
            
            # Calculate percentages
            for asset_type in by_type:
                if total_value_usd > 0:
                    by_type[asset_type]['percentage'] = (by_type[asset_type]['total_value_usd'] / total_value_usd) * 100
            
            return {
                'total_items': len(portfolio),
                'total_value_usd': total_value_usd,
                'total_value_rub': total_value_rub,
                'total_invested': total_invested,
                'total_profit_loss_usd': total_profit_loss_usd,
                'total_profit_loss_pct': total_profit_loss_pct,
                'by_type': by_type,
                'items': portfolio
            }
            
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            return {
                'total_items': 0,
                'total_value_usd': 0,
                'total_value_rub': 0,
                'by_type': {},
                'total_profit_loss_usd': 0,
                'total_profit_loss_pct': 0
            }
    
    def update_asset(self, user_id: int, item_id: int, **kwargs) -> Dict:
        """
        Update a portfolio item.
        
        Args:
            user_id: User's Telegram ID
            item_id: Portfolio item ID
            **kwargs: Fields to update
        
        Returns:
            Dict with result status
        """
        try:
            item = self.db.update_portfolio_item(item_id, user_id, **kwargs)
            
            if not item:
                return {
                    'success': False,
                    'error': 'Item not found'
                }
            
            logger.info(f"Updated portfolio item {item_id} for user {user_id}")
            
            return {
                'success': True,
                'item': item.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Error updating portfolio item: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_asset(self, user_id: int, item_id: int) -> Dict:
        """
        Delete a portfolio item.
        
        Args:
            user_id: User's Telegram ID
            item_id: Portfolio item ID
        
        Returns:
            Dict with result status
        """
        try:
            deleted = self.db.delete_portfolio_item(item_id, user_id)
            
            if deleted:
                logger.info(f"Deleted portfolio item {item_id} for user {user_id}")
                return {'success': True}
            else:
                return {
                    'success': False,
                    'error': 'Item not found'
                }
            
        except Exception as e:
            logger.error(f"Error deleting portfolio item: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_asset_name(self, asset_type: str, asset_symbol: str) -> Optional[str]:
        """Get full asset name based on type and symbol."""
        try:
            if asset_type == 'crypto':
                # For crypto, we can use the symbol as name or fetch from converter
                return asset_symbol.upper()
            
            elif asset_type == 'stock':
                # Check if it's a global or Russian stock
                if asset_symbol.upper() in self.stock_service.GLOBAL_STOCKS:
                    return self.stock_service.GLOBAL_STOCKS[asset_symbol.upper()]
                elif asset_symbol.upper() in self.stock_service.RUSSIAN_STOCKS:
                    return self.stock_service.RUSSIAN_STOCKS[asset_symbol.upper()]
                else:
                    return asset_symbol.upper()
            
            elif asset_type == 'fiat':
                return asset_symbol.upper()
            
            elif asset_type == 'cs2':
                # Get CS2 item name
                if asset_symbol in self.cs2_service.POPULAR_ITEMS:
                    return self.cs2_service.POPULAR_ITEMS[asset_symbol]['name']
                else:
                    return asset_symbol
            
            return asset_symbol.upper()
            
        except Exception as e:
            logger.error(f"Error getting asset name: {e}")
            return asset_symbol.upper()
    
    def _get_current_price(self, asset_type: str, asset_symbol: str, user_id: int) -> Optional[float]:
        """Get current price in USD for an asset."""
        try:
            if asset_type == 'crypto':
                # Get crypto price in USD
                return self.converter.get_crypto_rate_aggregated(asset_symbol, 'USDT', user_id)
            
            elif asset_type == 'stock':
                # Get stock price
                if asset_symbol.upper() in self.stock_service.GLOBAL_STOCKS:
                    stock_data = self.stock_service.get_global_stock(asset_symbol)
                    return stock_data['price'] if stock_data else None
                elif asset_symbol.upper() in self.stock_service.RUSSIAN_STOCKS:
                    stock_data = self.stock_service.get_russian_stock(asset_symbol)
                    if stock_data:
                        # Convert RUB to USD
                        rub_price = stock_data['price']
                        usd_to_rub = self.converter.get_crypto_rate_aggregated('USD', 'RUB', user_id) or 90.0
                        return rub_price / usd_to_rub
                    return None
            
            elif asset_type == 'fiat':
                # Get fiat to USD rate
                if asset_symbol.upper() == 'USD':
                    return 1.0
                else:
                    return self.converter.get_crypto_rate_aggregated(asset_symbol, 'USD', user_id)
            
            elif asset_type == 'cs2':
                # Get CS2 item price
                price_data = self.cs2_service.get_item_prices(asset_symbol)
                return price_data['avg_price'] if price_data else None
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting current price for {asset_symbol}: {e}")
            return None
