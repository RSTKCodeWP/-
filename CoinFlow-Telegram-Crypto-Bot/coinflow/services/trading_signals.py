"""Trading signals service with technical indicators."""

import numpy as np
import pandas as pd
from typing import Optional, Dict, List
from datetime import datetime
from ..utils.logger import setup_logger

logger = setup_logger('trading_signals')


class TradingSignalsService:
    """Service for technical analysis and trading signals."""
    
    def __init__(self, stock_service):
        """
        Initialize trading signals service.
        
        Args:
            stock_service: StockService instance for data
        """
        self.stock_service = stock_service
        logger.info("Trading signals service initialized")
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> Dict:
        """
        Calculate Relative Strength Index (RSI).
        
        Args:
            prices: List of historical prices
            period: RSI period (default 14)
        
        Returns:
            Dictionary with RSI value and signal
        """
        try:
            if len(prices) < period + 1:
                return {'success': False, 'error': 'Not enough data'}
            
            prices_array = np.array(prices)
            
            # Calculate price changes
            deltas = np.diff(prices_array)
            
            # Separate gains and losses
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            # Calculate average gains and losses
            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            # Generate signal
            if rsi > 70:
                signal = "SELL"
                interpretation = "Overbought"
            elif rsi < 30:
                signal = "BUY"
                interpretation = "Oversold"
            else:
                signal = "NEUTRAL"
                interpretation = "Normal range"
            
            return {
                'success': True,
                'indicator': 'RSI',
                'value': round(rsi, 2),
                'signal': signal,
                'interpretation': interpretation,
                'period': period
            }
        
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_macd(self, prices: List[float], fast: int = 12, 
                       slow: int = 26, signal: int = 9) -> Dict:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            prices: List of historical prices
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period
        
        Returns:
            Dictionary with MACD values and signal
        """
        try:
            if len(prices) < slow + signal:
                return {'success': False, 'error': 'Not enough data'}
            
            df = pd.DataFrame({'price': prices})
            
            # Calculate EMAs
            ema_fast = df['price'].ewm(span=fast, adjust=False).mean()
            ema_slow = df['price'].ewm(span=slow, adjust=False).mean()
            
            # MACD line
            macd_line = ema_fast - ema_slow
            
            # Signal line
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()
            
            # Histogram
            histogram = macd_line - signal_line
            
            # Current values
            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            current_histogram = histogram.iloc[-1]
            
            # Previous histogram for trend detection
            prev_histogram = histogram.iloc[-2] if len(histogram) > 1 else 0
            
            # Generate trading signal
            if current_histogram > 0 and prev_histogram <= 0:
                trade_signal = "BUY"
                interpretation = "Bullish crossover"
            elif current_histogram < 0 and prev_histogram >= 0:
                trade_signal = "SELL"
                interpretation = "Bearish crossover"
            elif current_histogram > 0:
                trade_signal = "BUY"
                interpretation = "Bullish momentum"
            elif current_histogram < 0:
                trade_signal = "SELL"
                interpretation = "Bearish momentum"
            else:
                trade_signal = "NEUTRAL"
                interpretation = "No clear signal"
            
            return {
                'success': True,
                'indicator': 'MACD',
                'macd_line': round(current_macd, 4),
                'signal_line': round(current_signal, 4),
                'histogram': round(current_histogram, 4),
                'signal': trade_signal,
                'interpretation': interpretation
            }
        
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_moving_averages(self, prices: List[float], 
                                  short_period: int = 20, 
                                  long_period: int = 50) -> Dict:
        """
        Calculate Moving Averages and generate signals.
        
        Args:
            prices: List of historical prices
            short_period: Short MA period
            long_period: Long MA period
        
        Returns:
            Dictionary with MA values and signal
        """
        try:
            if len(prices) < long_period:
                return {'success': False, 'error': 'Not enough data'}
            
            prices_array = np.array(prices)
            
            # Calculate SMAs
            sma_short = np.mean(prices_array[-short_period:])
            sma_long = np.mean(prices_array[-long_period:])
            
            # Previous SMAs for crossover detection
            if len(prices) > long_period + 1:
                prev_sma_short = np.mean(prices_array[-(short_period+1):-1])
                prev_sma_long = np.mean(prices_array[-(long_period+1):-1])
            else:
                prev_sma_short = sma_short
                prev_sma_long = sma_long
            
            current_price = prices_array[-1]
            
            # Generate signal
            if sma_short > sma_long and prev_sma_short <= prev_sma_long:
                signal = "BUY"
                interpretation = "Golden Cross - Bullish crossover"
            elif sma_short < sma_long and prev_sma_short >= prev_sma_long:
                signal = "SELL"
                interpretation = "Death Cross - Bearish crossover"
            elif sma_short > sma_long:
                signal = "BUY"
                interpretation = "Short MA above Long MA - Bullish"
            elif sma_short < sma_long:
                signal = "SELL"
                interpretation = "Short MA below Long MA - Bearish"
            else:
                signal = "NEUTRAL"
                interpretation = "MAs aligned"
            
            # Price relative to MAs
            price_vs_short = ((current_price - sma_short) / sma_short) * 100
            price_vs_long = ((current_price - sma_long) / sma_long) * 100
            
            return {
                'success': True,
                'indicator': 'MA',
                'sma_short': round(sma_short, 2),
                'sma_long': round(sma_long, 2),
                'current_price': round(current_price, 2),
                'price_vs_short_ma': round(price_vs_short, 2),
                'price_vs_long_ma': round(price_vs_long, 2),
                'signal': signal,
                'interpretation': interpretation
            }
        
        except Exception as e:
            logger.error(f"Error calculating moving averages: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_bollinger_bands(self, prices: List[float], 
                                  period: int = 20, 
                                  std_dev: float = 2.0) -> Dict:
        """
        Calculate Bollinger Bands.
        
        Args:
            prices: List of historical prices
            period: Period for moving average
            std_dev: Number of standard deviations
        
        Returns:
            Dictionary with Bollinger Bands and signal
        """
        try:
            if len(prices) < period:
                return {'success': False, 'error': 'Not enough data'}
            
            prices_array = np.array(prices)
            
            # Middle band (SMA)
            middle_band = np.mean(prices_array[-period:])
            
            # Standard deviation
            std = np.std(prices_array[-period:])
            
            # Upper and lower bands
            upper_band = middle_band + (std_dev * std)
            lower_band = middle_band - (std_dev * std)
            
            current_price = prices_array[-1]
            
            # Calculate position within bands
            band_width = upper_band - lower_band
            position = ((current_price - lower_band) / band_width) * 100 if band_width > 0 else 50
            
            # Generate signal
            if current_price >= upper_band:
                signal = "SELL"
                interpretation = "Price at upper band - Overbought"
            elif current_price <= lower_band:
                signal = "BUY"
                interpretation = "Price at lower band - Oversold"
            elif position > 75:
                signal = "SELL"
                interpretation = "Approaching upper band"
            elif position < 25:
                signal = "BUY"
                interpretation = "Approaching lower band"
            else:
                signal = "NEUTRAL"
                interpretation = "Price in normal range"
            
            return {
                'success': True,
                'indicator': 'Bollinger Bands',
                'upper_band': round(upper_band, 2),
                'middle_band': round(middle_band, 2),
                'lower_band': round(lower_band, 2),
                'current_price': round(current_price, 2),
                'position': round(position, 1),
                'signal': signal,
                'interpretation': interpretation
            }
        
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_trading_signals(self, symbol: str, period_days: int = 30) -> Dict:
        """
        Get comprehensive trading signals for an asset.
        
        Args:
            symbol: Asset symbol
            period_days: Historical period in days
        
        Returns:
            Dictionary with all indicators and overall signal
        """
        try:
            # Get historical data
            stock_data = self.stock_service.get_stock_chart(symbol, period_days)
            
            if not stock_data or 'error' in stock_data:
                return {'success': False, 'error': 'Could not fetch data'}
            
            prices = stock_data.get('prices', [])
            
            if len(prices) < 50:  # Need at least 50 days for all indicators
                return {'success': False, 'error': 'Not enough historical data'}
            
            # Calculate all indicators
            rsi = self.calculate_rsi(prices)
            macd = self.calculate_macd(prices)
            ma = self.calculate_moving_averages(prices)
            bb = self.calculate_bollinger_bands(prices)
            
            # Aggregate signals
            signals = []
            if rsi.get('success'):
                signals.append(rsi['signal'])
            if macd.get('success'):
                signals.append(macd['signal'])
            if ma.get('success'):
                signals.append(ma['signal'])
            if bb.get('success'):
                signals.append(bb['signal'])
            
            # Overall signal (majority vote)
            buy_count = signals.count('BUY')
            sell_count = signals.count('SELL')
            
            if buy_count > sell_count:
                overall_signal = "BUY"
                confidence = (buy_count / len(signals)) * 100
            elif sell_count > buy_count:
                overall_signal = "SELL"
                confidence = (sell_count / len(signals)) * 100
            else:
                overall_signal = "NEUTRAL"
                confidence = 50
            
            return {
                'success': True,
                'symbol': symbol,
                'period_days': period_days,
                'current_price': prices[-1],
                'rsi': rsi if rsi.get('success') else None,
                'macd': macd if macd.get('success') else None,
                'moving_averages': ma if ma.get('success') else None,
                'bollinger_bands': bb if bb.get('success') else None,
                'overall_signal': overall_signal,
                'confidence': round(confidence, 1),
                'bullish_indicators': buy_count,
                'bearish_indicators': sell_count,
                'neutral_indicators': signals.count('NEUTRAL')
            }
        
        except Exception as e:
            logger.error(f"Error getting trading signals: {e}")
            return {'success': False, 'error': str(e)}
