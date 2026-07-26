"""Smart alerts service with ML-based predictions."""

import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from ..utils.logger import setup_logger

logger = setup_logger('smart_alerts')


class SmartAlertsService:
    """Service for intelligent alerts based on market analysis."""
    
    def __init__(self, db, stock_service, analytics_service):
        """
        Initialize smart alerts service.
        
        Args:
            db: Database repository
            stock_service: StockService instance
            analytics_service: AnalyticsService instance
        """
        self.db = db
        self.stock_service = stock_service
        self.analytics_service = analytics_service
        logger.info("Smart alerts service initialized")
    
    def detect_high_volatility(self, prices: List[float], threshold_std: float = 2.0) -> Dict:
        """
        Detect high volatility periods.
        
        Args:
            prices: Historical prices
            threshold_std: Standard deviation multiplier for alert
        
        Returns:
            Volatility analysis
        """
        try:
            if len(prices) < 30:
                return {'detected': False, 'reason': 'Insufficient data'}
            
            # Calculate recent volatility (last 7 days)
            recent_prices = prices[-7:]
            recent_returns = np.diff(recent_prices) / np.array(recent_prices[:-1])
            recent_vol = np.std(recent_returns) * 100
            
            # Calculate baseline volatility (30 days)
            all_returns = np.diff(prices) / np.array(prices[:-1])
            baseline_vol = np.std(all_returns) * 100
            
            # Check if recent volatility exceeds threshold
            if recent_vol > baseline_vol * threshold_std:
                return {
                    'detected': True,
                    'type': 'HIGH_VOLATILITY',
                    'recent_volatility': round(recent_vol, 2),
                    'baseline_volatility': round(baseline_vol, 2),
                    'multiplier': round(recent_vol / baseline_vol, 2),
                    'severity': 'HIGH' if recent_vol > baseline_vol * 3 else 'MODERATE',
                    'message': f'Volatility {round(recent_vol / baseline_vol, 1)}x higher than average'
                }
            
            return {'detected': False}
        
        except Exception as e:
            logger.error(f"Error detecting high volatility: {e}")
            return {'detected': False, 'error': str(e)}
    
    def detect_momentum_shift(self, prices: List[float]) -> Dict:
        """
        Detect significant momentum shifts.
        
        Args:
            prices: Historical prices
        
        Returns:
            Momentum analysis
        """
        try:
            if len(prices) < 20:
                return {'detected': False, 'reason': 'Insufficient data'}
            
            # Calculate short-term and medium-term momentum
            short_ma = np.mean(prices[-5:])
            medium_ma = np.mean(prices[-20:])
            current_price = prices[-1]
            
            # Previous momentum
            prev_short_ma = np.mean(prices[-6:-1])
            prev_medium_ma = np.mean(prices[-21:-1])
            
            # Detect bullish momentum shift
            if (short_ma > medium_ma and prev_short_ma <= prev_medium_ma):
                momentum_strength = ((short_ma - medium_ma) / medium_ma) * 100
                return {
                    'detected': True,
                    'type': 'BULLISH_MOMENTUM',
                    'direction': 'UP',
                    'strength': round(momentum_strength, 2),
                    'current_price': round(current_price, 2),
                    'message': 'Bullish momentum detected - short-term MA crossed above medium-term MA'
                }
            
            # Detect bearish momentum shift
            elif (short_ma < medium_ma and prev_short_ma >= prev_medium_ma):
                momentum_strength = ((medium_ma - short_ma) / medium_ma) * 100
                return {
                    'detected': True,
                    'type': 'BEARISH_MOMENTUM',
                    'direction': 'DOWN',
                    'strength': round(momentum_strength, 2),
                    'current_price': round(current_price, 2),
                    'message': 'Bearish momentum detected - short-term MA crossed below medium-term MA'
                }
            
            return {'detected': False}
        
        except Exception as e:
            logger.error(f"Error detecting momentum shift: {e}")
            return {'detected': False, 'error': str(e)}
    
    def detect_volume_spike(self, volumes: List[float], threshold: float = 2.0) -> Dict:
        """
        Detect unusual trading volume.
        
        Args:
            volumes: Historical volume data
            threshold: Volume multiplier for alert
        
        Returns:
            Volume analysis
        """
        try:
            if len(volumes) < 20:
                return {'detected': False, 'reason': 'Insufficient data'}
            
            recent_volume = volumes[-1]
            avg_volume = np.mean(volumes[:-1])
            
            if recent_volume > avg_volume * threshold:
                return {
                    'detected': True,
                    'type': 'VOLUME_SPIKE',
                    'recent_volume': round(recent_volume, 0),
                    'average_volume': round(avg_volume, 0),
                    'multiplier': round(recent_volume / avg_volume, 2),
                    'severity': 'HIGH' if recent_volume > avg_volume * 5 else 'MODERATE',
                    'message': f'Volume {round(recent_volume / avg_volume, 1)}x higher than average'
                }
            
            return {'detected': False}
        
        except Exception as e:
            logger.error(f"Error detecting volume spike: {e}")
            return {'detected': False, 'error': str(e)}
    
    def predict_short_term_movement(self, prices: List[float]) -> Dict:
        """
        Predict short-term price movement using simple heuristics.
        
        Args:
            prices: Historical prices
        
        Returns:
            Prediction with confidence
        """
        try:
            if len(prices) < 30:
                return {'success': False, 'reason': 'Insufficient data'}
            
            # Calculate multiple indicators
            current_price = prices[-1]
            
            # Trend (5-day vs 20-day MA)
            short_ma = np.mean(prices[-5:])
            long_ma = np.mean(prices[-20:])
            trend_bullish = short_ma > long_ma
            
            # Momentum (recent vs older returns)
            recent_return = (prices[-1] - prices[-5]) / prices[-5]
            older_return = (prices[-10] - prices[-15]) / prices[-15]
            momentum_increasing = recent_return > older_return
            
            # Volatility regime
            recent_vol = np.std(np.diff(prices[-7:]) / np.array(prices[-8:-1]))
            baseline_vol = np.std(np.diff(prices) / np.array(prices[:-1]))
            high_volatility = recent_vol > baseline_vol * 1.5
            
            # Simple voting system
            bullish_signals = sum([trend_bullish, momentum_increasing, not high_volatility])
            confidence = (bullish_signals / 3) * 100
            
            if bullish_signals >= 2:
                prediction = 'RISE'
                direction = 'UP'
            else:
                prediction = 'FALL'
                direction = 'DOWN'
            
            return {
                'success': True,
                'prediction': prediction,
                'direction': direction,
                'confidence': round(confidence, 1),
                'current_price': round(current_price, 2),
                'timeframe': '2-6 hours',
                'indicators': {
                    'trend': 'Bullish' if trend_bullish else 'Bearish',
                    'momentum': 'Increasing' if momentum_increasing else 'Decreasing',
                    'volatility': 'High' if high_volatility else 'Normal'
                }
            }
        
        except Exception as e:
            logger.error(f"Error predicting short-term movement: {e}")
            return {'success': False, 'error': str(e)}
    
    async def check_smart_alerts(self, symbol: str, period_days: int = 60) -> Dict:
        """
        Check all smart alert conditions for an asset.
        
        Args:
            symbol: Asset symbol
            period_days: Historical period
        
        Returns:
            Alert analysis
        """
        try:
            # Get historical data
            stock_data = self.stock_service.get_stock_chart(symbol, period_days)
            
            if not stock_data or 'error' in stock_data:
                return {'success': False, 'error': 'Could not fetch data'}
            
            prices = stock_data.get('prices', [])
            volumes = stock_data.get('volumes', [])
            
            if len(prices) < 30:
                return {'success': False, 'error': 'Insufficient data'}
            
            # Check all alert types
            alerts = []
            
            # High volatility
            vol_alert = self.detect_high_volatility(prices)
            if vol_alert.get('detected'):
                alerts.append(vol_alert)
            
            # Momentum shift
            momentum_alert = self.detect_momentum_shift(prices)
            if momentum_alert.get('detected'):
                alerts.append(momentum_alert)
            
            # Volume spike (if available)
            if volumes and len(volumes) >= 20:
                volume_alert = self.detect_volume_spike(volumes)
                if volume_alert.get('detected'):
                    alerts.append(volume_alert)
            
            # Short-term prediction
            prediction = self.predict_short_term_movement(prices)
            
            return {
                'success': True,
                'symbol': symbol,
                'current_price': prices[-1],
                'alerts': alerts,
                'alert_count': len(alerts),
                'prediction': prediction if prediction.get('success') else None,
                'checked_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error checking smart alerts: {e}")
            return {'success': False, 'error': str(e)}
    
    def generate_alert_message(self, symbol: str, alert_data: Dict) -> str:
        """
        Generate user-friendly alert message.
        
        Args:
            symbol: Asset symbol
            alert_data: Alert data from check_smart_alerts
        
        Returns:
            Formatted message
        """
        if not alert_data.get('success'):
            return f"❌ Error checking {symbol}: {alert_data.get('error', 'Unknown')}"
        
        message = f"🔔 **Smart Alert: {symbol}**\n\n"
        message += f"💰 Price: ${alert_data['current_price']:,.2f}\n\n"
        
        alerts = alert_data.get('alerts', [])
        
        if not alerts:
            message += "✅ No alerts triggered\nAll indicators within normal range.\n\n"
        else:
            message += f"⚠️ **{len(alerts)} Alert(s) Triggered:**\n\n"
            
            for alert in alerts:
                alert_type = alert.get('type', 'UNKNOWN')
                
                if alert_type == 'HIGH_VOLATILITY':
                    emoji = '📊' if alert['severity'] == 'MODERATE' else '🔥'
                    message += f"{emoji} **High Volatility**\n"
                    message += f"Recent: {alert['recent_volatility']}%\n"
                    message += f"Baseline: {alert['baseline_volatility']}%\n"
                    message += f"_{alert['message']}_\n\n"
                
                elif alert_type == 'BULLISH_MOMENTUM':
                    message += f"📈 **Bullish Momentum**\n"
                    message += f"Strength: {alert['strength']}%\n"
                    message += f"_{alert['message']}_\n\n"
                
                elif alert_type == 'BEARISH_MOMENTUM':
                    message += f"📉 **Bearish Momentum**\n"
                    message += f"Strength: {alert['strength']}%\n"
                    message += f"_{alert['message']}_\n\n"
                
                elif alert_type == 'VOLUME_SPIKE':
                    emoji = '💥' if alert['severity'] == 'HIGH' else '📊'
                    message += f"{emoji} **Volume Spike**\n"
                    message += f"Current: {alert['recent_volume']:,.0f}\n"
                    message += f"Average: {alert['average_volume']:,.0f}\n"
                    message += f"_{alert['message']}_\n\n"
        
        # Add prediction
        prediction = alert_data.get('prediction')
        if prediction and prediction.get('success'):
            pred_emoji = '🟢' if prediction['prediction'] == 'RISE' else '🔴'
            message += f"{pred_emoji} **Short-term Prediction**\n"
            message += f"Direction: {prediction['prediction']}\n"
            message += f"Confidence: {prediction['confidence']}%\n"
            message += f"Timeframe: {prediction['timeframe']}\n\n"
        
        message += "_Smart alerts use statistical analysis, not financial advice._"
        
        return message
