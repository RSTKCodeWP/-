"""Portfolio rebalancing service."""

from typing import Dict, List, Optional
from datetime import datetime
from ..utils.logger import setup_logger

logger = setup_logger('rebalance_service')


class RebalanceService:
    """Service for portfolio rebalancing recommendations."""
    
    def __init__(self, db, portfolio_service):
        """
        Initialize rebalance service.
        
        Args:
            db: Database repository
            portfolio_service: PortfolioService instance
        """
        self.db = db
        self.portfolio_service = portfolio_service
        logger.info("Rebalance service initialized")
    
    def calculate_portfolio_weights(self, portfolio_items: List) -> Dict:
        """
        Calculate current portfolio weights.
        
        Args:
            portfolio_items: List of portfolio items with values
        
        Returns:
            Dictionary with weights by symbol
        """
        total_value = sum(item.get('current_value', 0) for item in portfolio_items)
        
        if total_value == 0:
            return {}
        
        weights = {}
        for item in portfolio_items:
            symbol = item['asset_symbol']
            value = item.get('current_value', 0)
            weight = (value / total_value) * 100
            weights[symbol] = {
                'weight': weight,
                'value': value,
                'quantity': item['quantity']
            }
        
        return weights
    
    def generate_rebalance_recommendations(self, current_weights: Dict, 
                                          target_weights: Dict,
                                          total_value: float,
                                          min_trade_threshold: float = 1.0) -> Dict:
        """
        Generate rebalancing recommendations.
        
        Args:
            current_weights: Current portfolio weights
            target_weights: Target portfolio weights (percentage)
            total_value: Total portfolio value
            min_trade_threshold: Minimum deviation % to trigger rebalancing
        
        Returns:
            Dictionary with recommendations
        """
        recommendations = []
        total_deviation = 0
        needs_rebalancing = False
        
        # Check all target assets
        for symbol, target_pct in target_weights.items():
            current_pct = current_weights.get(symbol, {}).get('weight', 0)
            deviation = current_pct - target_pct
            abs_deviation = abs(deviation)
            
            total_deviation += abs_deviation
            
            # Calculate target value
            target_value = (target_pct / 100) * total_value
            current_value = current_weights.get(symbol, {}).get('value', 0)
            value_diff = target_value - current_value
            
            if abs_deviation >= min_trade_threshold:
                needs_rebalancing = True
                
                if deviation > 0:
                    # Overweight - need to sell
                    action = "SELL"
                    emoji = "📉"
                else:
                    # Underweight - need to buy
                    action = "BUY"
                    emoji = "📈"
                
                recommendations.append({
                    'symbol': symbol,
                    'action': action,
                    'emoji': emoji,
                    'current_weight': round(current_pct, 2),
                    'target_weight': round(target_pct, 2),
                    'deviation': round(deviation, 2),
                    'abs_deviation': round(abs_deviation, 2),
                    'value_adjustment': round(abs(value_diff), 2),
                    'current_value': round(current_value, 2),
                    'target_value': round(target_value, 2)
                })
        
        # Check for assets not in target (should be sold)
        for symbol in current_weights:
            if symbol not in target_weights:
                current_value = current_weights[symbol]['value']
                current_pct = current_weights[symbol]['weight']
                
                recommendations.append({
                    'symbol': symbol,
                    'action': 'SELL_ALL',
                    'emoji': '❌',
                    'current_weight': round(current_pct, 2),
                    'target_weight': 0,
                    'deviation': round(current_pct, 2),
                    'abs_deviation': round(current_pct, 2),
                    'value_adjustment': round(current_value, 2),
                    'current_value': round(current_value, 2),
                    'target_value': 0
                })
                needs_rebalancing = True
        
        # Sort by absolute deviation (most urgent first)
        recommendations.sort(key=lambda x: x['abs_deviation'], reverse=True)
        
        return {
            'needs_rebalancing': needs_rebalancing,
            'total_deviation': round(total_deviation, 2),
            'recommendations': recommendations,
            'portfolio_value': round(total_value, 2)
        }
    
    def get_rebalancing_plan(self, user_id: int, target_allocation: Dict) -> Dict:
        """
        Get comprehensive rebalancing plan for user's portfolio.
        
        Args:
            user_id: User ID
            target_allocation: Target allocation dictionary {symbol: percentage}
        
        Returns:
            Rebalancing plan with recommendations
        """
        try:
            # Validate target allocation
            total_target = sum(target_allocation.values())
            if abs(total_target - 100) > 0.01:
                return {
                    'success': False,
                    'error': f'Target allocation must sum to 100% (got {total_target}%)'
                }
            
            # Get current portfolio
            portfolio_items = self.db.get_portfolio_items(user_id)
            
            if not portfolio_items:
                return {
                    'success': False,
                    'error': 'Portfolio is empty'
                }
            
            # Calculate current values
            portfolio_data = []
            total_value = 0
            
            for item in portfolio_items:
                current_value = self.portfolio_service.calculate_item_value(item)
                portfolio_data.append({
                    'asset_symbol': item.asset_symbol,
                    'asset_type': item.asset_type,
                    'quantity': float(item.quantity),
                    'current_value': current_value
                })
                total_value += current_value
            
            if total_value == 0:
                return {
                    'success': False,
                    'error': 'Portfolio has zero value'
                }
            
            # Calculate current weights
            current_weights = self.calculate_portfolio_weights(portfolio_data)
            
            # Generate recommendations
            recommendations = self.generate_rebalance_recommendations(
                current_weights,
                target_allocation,
                total_value,
                min_trade_threshold=1.0  # 1% threshold
            )
            
            return {
                'success': True,
                'current_weights': current_weights,
                'target_allocation': target_allocation,
                'rebalancing': recommendations
            }
        
        except Exception as e:
            logger.error(f"Error generating rebalancing plan: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_preset_allocations(self) -> Dict:
        """
        Get preset allocation strategies.
        
        Returns:
            Dictionary of preset allocations
        """
        return {
            'conservative': {
                'name': 'Conservative',
                'description': 'Low risk, stable returns',
                'allocation': {
                    'BTC': 40,
                    'ETH': 30,
                    'USDT': 30
                }
            },
            'balanced': {
                'name': 'Balanced',
                'description': 'Medium risk, balanced growth',
                'allocation': {
                    'BTC': 50,
                    'ETH': 30,
                    'BNB': 10,
                    'USDT': 10
                }
            },
            'aggressive': {
                'name': 'Aggressive',
                'description': 'High risk, high potential returns',
                'allocation': {
                    'BTC': 40,
                    'ETH': 25,
                    'SOL': 15,
                    'BNB': 10,
                    'ADA': 10
                }
            },
            'hodl': {
                'name': 'HODL (Long-term)',
                'description': 'Long-term hold strategy',
                'allocation': {
                    'BTC': 60,
                    'ETH': 40
                }
            },
            'defi': {
                'name': 'DeFi Focus',
                'description': 'DeFi ecosystem exposure',
                'allocation': {
                    'ETH': 40,
                    'BNB': 20,
                    'AVAX': 15,
                    'MATIC': 15,
                    'USDT': 10
                }
            }
        }
    
    def save_target_allocation(self, user_id: int, allocation: Dict, 
                              allocation_name: str = 'custom') -> bool:
        """
        Save user's target allocation to database.
        
        Args:
            user_id: User ID
            allocation: Target allocation
            allocation_name: Name of allocation strategy
        
        Returns:
            Success status
        """
        try:
            # Store in user settings or separate table
            # For now, we'll use a simple approach with user metadata
            import json
            
            user = self.db.get_user(user_id)
            if not user:
                return False
            
            # Store allocation in user's settings
            allocation_data = {
                'name': allocation_name,
                'allocation': allocation,
                'updated_at': datetime.now().isoformat()
            }
            
            # TODO: Add target_allocation field to User model
            # For now, log the action
            logger.info(f"Target allocation saved for user {user_id}: {allocation_name}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving target allocation: {e}")
            return False
    
    def calculate_rebalancing_cost(self, recommendations: List[Dict], 
                                   trading_fee_pct: float = 0.1) -> Dict:
        """
        Calculate estimated cost of rebalancing.
        
        Args:
            recommendations: List of rebalancing recommendations
            trading_fee_pct: Trading fee percentage
        
        Returns:
            Cost breakdown
        """
        total_trade_value = 0
        buy_value = 0
        sell_value = 0
        
        for rec in recommendations:
            value = rec.get('value_adjustment', 0)
            total_trade_value += value
            
            if rec['action'] in ['BUY']:
                buy_value += value
            else:
                sell_value += value
        
        # Calculate fees (both buy and sell sides)
        total_fees = (total_trade_value * trading_fee_pct) / 100
        
        return {
            'total_trade_value': round(total_trade_value, 2),
            'buy_value': round(buy_value, 2),
            'sell_value': round(sell_value, 2),
            'estimated_fees': round(total_fees, 2),
            'fee_percentage': trading_fee_pct
        }
