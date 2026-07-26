"""Advanced analytics service for financial metrics."""

import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from ..utils.logger import setup_logger

logger = setup_logger('analytics_service')


class AnalyticsService:
    """Service for advanced financial analytics."""
    
    def __init__(self, converter, stock_service):
        """
        Initialize analytics service.
        
        Args:
            converter: CurrencyConverter instance
            stock_service: StockService instance
        """
        self.converter = converter
        self.stock_service = stock_service
        logger.info("Analytics service initialized")
    
    def calculate_volatility(self, prices: List[float], period: int = 30) -> Dict:
        """
        Calculate volatility metrics.
        
        Args:
            prices: List of historical prices
            period: Period for rolling calculations
        
        Returns:
            Dictionary with volatility metrics
        """
        try:
            if len(prices) < 2:
                return {'error': 'Not enough data'}
            
            prices_array = np.array(prices)
            
            # Calculate returns
            returns = np.diff(prices_array) / prices_array[:-1]
            
            # Standard deviation (volatility)
            volatility = np.std(returns) * 100  # Convert to percentage
            
            # Annualized volatility (assuming daily data)
            annualized_vol = volatility * np.sqrt(365)
            
            # Rolling volatility
            if len(prices) >= period:
                df = pd.DataFrame({'price': prices})
                df['returns'] = df['price'].pct_change()
                rolling_vol = df['returns'].rolling(window=period).std() * 100
                current_rolling_vol = rolling_vol.iloc[-1] if not pd.isna(rolling_vol.iloc[-1]) else None
            else:
                current_rolling_vol = None
            
            return {
                'success': True,
                'volatility': round(volatility, 2),
                'annualized_volatility': round(annualized_vol, 2),
                'rolling_volatility': round(current_rolling_vol, 2) if current_rolling_vol else None,
                'period': period
            }
        
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_sharpe_ratio(self, prices: List[float], risk_free_rate: float = 0.02) -> Dict:
        """
        Calculate Sharpe ratio.
        
        Args:
            prices: List of historical prices
            risk_free_rate: Annual risk-free rate (default 2%)
        
        Returns:
            Dictionary with Sharpe ratio
        """
        try:
            if len(prices) < 2:
                return {'error': 'Not enough data'}
            
            prices_array = np.array(prices)
            
            # Calculate returns
            returns = np.diff(prices_array) / prices_array[:-1]
            
            # Average return
            avg_return = np.mean(returns)
            
            # Standard deviation
            std_return = np.std(returns)
            
            if std_return == 0:
                return {'success': False, 'error': 'Zero volatility'}
            
            # Annualize
            annual_return = avg_return * 365
            annual_std = std_return * np.sqrt(365)
            
            # Sharpe ratio
            sharpe = (annual_return - risk_free_rate) / annual_std
            
            return {
                'success': True,
                'sharpe_ratio': round(sharpe, 3),
                'annual_return': round(annual_return * 100, 2),
                'annual_volatility': round(annual_std * 100, 2),
                'risk_free_rate': risk_free_rate * 100
            }
        
        except Exception as e:
            logger.error(f"Error calculating Sharpe ratio: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_correlation(self, prices1: List[float], prices2: List[float]) -> Dict:
        """
        Calculate correlation between two assets.
        
        Args:
            prices1: First asset prices
            prices2: Second asset prices
        
        Returns:
            Dictionary with correlation coefficient
        """
        try:
            if len(prices1) != len(prices2):
                return {'success': False, 'error': 'Price arrays must have same length'}
            
            if len(prices1) < 2:
                return {'success': False, 'error': 'Not enough data'}
            
            # Calculate returns
            returns1 = np.diff(prices1) / np.array(prices1[:-1])
            returns2 = np.diff(prices2) / np.array(prices2[:-1])
            
            # Correlation coefficient
            correlation = np.corrcoef(returns1, returns2)[0, 1]
            
            # Interpretation
            if abs(correlation) >= 0.7:
                strength = "Strong"
            elif abs(correlation) >= 0.4:
                strength = "Moderate"
            else:
                strength = "Weak"
            
            direction = "positive" if correlation > 0 else "negative"
            
            return {
                'success': True,
                'correlation': round(correlation, 3),
                'strength': strength,
                'direction': direction,
                'interpretation': f"{strength} {direction} correlation"
            }
        
        except Exception as e:
            logger.error(f"Error calculating correlation: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_max_drawdown(self, prices: List[float]) -> Dict:
        """
        Calculate maximum drawdown.
        
        Args:
            prices: List of historical prices
        
        Returns:
            Dictionary with max drawdown
        """
        try:
            if len(prices) < 2:
                return {'success': False, 'error': 'Not enough data'}
            
            prices_array = np.array(prices)
            
            # Calculate running maximum
            running_max = np.maximum.accumulate(prices_array)
            
            # Calculate drawdown
            drawdown = (prices_array - running_max) / running_max * 100
            
            # Maximum drawdown
            max_dd = np.min(drawdown)
            max_dd_idx = np.argmin(drawdown)
            
            # Find peak before max drawdown
            peak_idx = np.argmax(prices_array[:max_dd_idx+1]) if max_dd_idx > 0 else 0
            
            return {
                'success': True,
                'max_drawdown': round(max_dd, 2),
                'peak_index': int(peak_idx),
                'trough_index': int(max_dd_idx),
                'current_drawdown': round(drawdown[-1], 2)
            }
        
        except Exception as e:
            logger.error(f"Error calculating max drawdown: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_risk_metrics(self, prices: List[float]) -> Dict:
        """
        Calculate comprehensive risk metrics.
        
        Args:
            prices: List of historical prices
        
        Returns:
            Dictionary with multiple risk metrics
        """
        try:
            volatility = self.calculate_volatility(prices)
            sharpe = self.calculate_sharpe_ratio(prices)
            drawdown = self.calculate_max_drawdown(prices)
            
            # Value at Risk (VaR) - 95% confidence
            returns = np.diff(prices) / np.array(prices[:-1])
            var_95 = np.percentile(returns, 5) * 100
            
            # Conditional VaR (CVaR/Expected Shortfall)
            cvar_95 = np.mean(returns[returns <= np.percentile(returns, 5)]) * 100
            
            return {
                'success': True,
                'volatility': volatility.get('volatility'),
                'sharpe_ratio': sharpe.get('sharpe_ratio'),
                'max_drawdown': drawdown.get('max_drawdown'),
                'var_95': round(var_95, 2),
                'cvar_95': round(cvar_95, 2)
            }
        
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_asset_analytics(self, symbol: str, asset_type: str = 'crypto', 
                                  period_days: int = 30) -> Dict:
        """
        Get comprehensive analytics for an asset.
        
        Args:
            symbol: Asset symbol
            asset_type: 'crypto' or 'stock'
            period_days: Historical period in days
        
        Returns:
            Dictionary with analytics
        """
        try:
            # Get historical prices
            if asset_type == 'crypto':
                # Get from converter's historical data if available
                # For now, we'll use current price as placeholder
                current_price = self.converter.get_crypto_rate_aggregated(symbol, 'USDT')
                if not current_price:
                    return {'success': False, 'error': 'Could not fetch price'}
                
                # TODO: Implement historical price fetching
                # For now, return limited analytics
                return {
                    'success': True,
                    'symbol': symbol,
                    'current_price': current_price,
                    'message': 'Historical data not available for full analytics'
                }
            
            elif asset_type == 'stock':
                stock_data = self.stock_service.get_stock_chart(symbol, period_days)
                if not stock_data or 'error' in stock_data:
                    return {'success': False, 'error': 'Could not fetch stock data'}
                
                prices = stock_data.get('prices', [])
                if len(prices) < 2:
                    return {'success': False, 'error': 'Not enough historical data'}
                
                # Calculate all metrics
                volatility = self.calculate_volatility(prices, period=min(30, len(prices)))
                sharpe = self.calculate_sharpe_ratio(prices)
                drawdown = self.calculate_max_drawdown(prices)
                
                return {
                    'success': True,
                    'symbol': symbol,
                    'period_days': period_days,
                    'data_points': len(prices),
                    'current_price': prices[-1],
                    'volatility': volatility,
                    'sharpe_ratio': sharpe,
                    'max_drawdown': drawdown
                }
        
        except Exception as e:
            logger.error(f"Error getting asset analytics: {e}")
            return {'success': False, 'error': str(e)}
    
    async def compare_assets_correlation(self, symbol1: str, symbol2: str, 
                                        period_days: int = 30) -> Dict:
        """
        Compare correlation between two assets.
        
        Args:
            symbol1: First asset symbol
            symbol2: Second asset symbol
            period_days: Historical period
        
        Returns:
            Correlation analysis
        """
        try:
            # Get historical data for both assets
            data1 = self.stock_service.get_stock_chart(symbol1, period_days)
            data2 = self.stock_service.get_stock_chart(symbol2, period_days)
            
            if not data1 or not data2:
                return {'success': False, 'error': 'Could not fetch data'}
            
            prices1 = data1.get('prices', [])
            prices2 = data2.get('prices', [])
            
            if len(prices1) < 2 or len(prices2) < 2:
                return {'success': False, 'error': 'Not enough data'}
            
            # Align lengths
            min_len = min(len(prices1), len(prices2))
            prices1 = prices1[-min_len:]
            prices2 = prices2[-min_len:]
            
            # Calculate correlation
            correlation = self.calculate_correlation(prices1, prices2)
            
            if correlation.get('success'):
                correlation['asset1'] = symbol1
                correlation['asset2'] = symbol2
                correlation['period_days'] = period_days
            
            return correlation
        
        except Exception as e:
            logger.error(f"Error comparing assets: {e}")
            return {'success': False, 'error': str(e)}
