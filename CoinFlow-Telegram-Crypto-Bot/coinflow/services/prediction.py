"""Price prediction service using AI models with vision analysis."""

import io
import os
import tempfile
import aiohttp
import xml.etree.ElementTree as ET
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.arima.model import ARIMA
from typing import Optional, Tuple, Dict, List
from ..utils.logger import setup_logger
import warnings
warnings.filterwarnings('ignore')

logger = setup_logger('prediction')

# Try to import Prophet (optional, not currently used)
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    # Prophet is optional - we use ARIMA and Linear Regression


class PredictionGenerator:
    """Генератор прогнозов курсов."""
    
    # CBR currency codes mapping
    CBR_CURRENCY_CODES = {
        'USD': 'R01235',
        'EUR': 'R01239',
        'CNY': 'R01375',
        'GBP': 'R01035',
        'JPY': 'R01820',
        'TRY': 'R01700',
        'KZT': 'R01335',
        'BYN': 'R01090'
    }
    
    def __init__(self, dpi: int = 150, db = None, ai_service = None):
        self.dpi = dpi
        self.db = db
        self.ai_service = ai_service  # AI service for vision analysis
    
    async def fetch_cbr_historical_rates(self, currency: str, days: int = 90) -> List[Tuple[datetime, float]]:
        """
        Fetch historical CBR rates for prediction.
        
        Args:
            currency: Currency code (USD, EUR, etc.)
            days: Number of days to fetch
        
        Returns:
            List of (date, rate) tuples
        """
        try:
            currency_code = self.CBR_CURRENCY_CODES.get(currency)
            if not currency_code:
                logger.error(f"Unknown CBR currency: {currency}")
                return []
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            date_from = start_date.strftime('%d/%m/%Y')
            date_to = end_date.strftime('%d/%m/%Y')
            
            url = f"https://www.cbr.ru/scripts/XML_dynamic.asp?date_req1={date_from}&date_req2={date_to}&VAL_NM_RQ={currency_code}"
            
            logger.info(f"Fetching CBR historical rates for {currency} from {date_from} to {date_to}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"CBR API error: {response.status}")
                        return []
                    xml_data = await response.text()
            
            root = ET.fromstring(xml_data)
            rates = []
            
            for record in root.findall('Record'):
                date_str = record.get('Date')
                value_str = record.find('Value').text
                date = datetime.strptime(date_str, '%d.%m.%Y')
                value = float(value_str.replace(',', '.'))
                rates.append((date, value))
            
            logger.info(f"Fetched {len(rates)} CBR rates for {currency}")
            return rates
        
        except Exception as e:
            logger.error(f"Error fetching CBR rates for {currency}: {e}")
            return []
    
    def generate_prediction(self, pair: str, model_type: str = 'arima', 
                          days: int = 90, forecast_days: int = 7) -> Tuple[Optional[bytes], Dict]:
        """
        Создать прогноз для пары валют.
        
        Args:
            pair: Trading pair (e.g., "BTC-USD")
            model_type: 'arima' or 'linear'
            days: Historical days to analyze
            forecast_days: Days to forecast ahead
        
        Returns:
            Tuple of (image bytes, statistics dict)
        """
        try:
            logger.info(f"Generating prediction for {pair}, model: {model_type}, days: {days}")
            
            # Загрузка данных
            ticker = yf.Ticker(pair)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            df = ticker.history(start=start_date, end=end_date)
            
            # Validate data availability
            if df.empty:
                logger.warning(f"No data available for {pair}")
                return None, {'error': 'no_data', 'pair': pair}
            
            if len(df) < 30:
                logger.warning(f"Insufficient data for {pair}: only {len(df)} days")
                return None, {'error': 'insufficient_data', 'pair': pair, 'days_available': len(df)}
            
            prices = df['Close'].values
            current_price = prices[-1]
            
            # Validate price data
            if current_price <= 0 or np.isnan(current_price):
                logger.error(f"Invalid current price for {pair}: {current_price}")
                return None, {'error': 'invalid_price', 'pair': pair}
            
            # Прогнозирование
            forecast = None
            confidence = 'medium'
            
            if model_type == 'prophet' and PROPHET_AVAILABLE:
                try:
                    # Prepare data for Prophet
                    prophet_df = df.reset_index()[['Date', 'Close']].rename(columns={'Date': 'ds', 'Close': 'y'})
                    
                    # Create and fit model
                    model = Prophet(daily_seasonality=True)
                    model.fit(prophet_df)
                    
                    # Make future predictions
                    future = model.make_future_dataframe(periods=forecast_days)
                    forecast_df = model.predict(future)
                    
                    # Extract forecast values
                    forecast = forecast_df['yhat'].tail(forecast_days).values
                    confidence = 'high'
                    logger.info(f"Prophet forecast completed for {pair}")
                except Exception as e:
                    logger.warning(f"Prophet failed for {pair}, falling back to ARIMA: {e}")
                    model_type = 'arima'
            
            if model_type == 'arima' and forecast is None:
                try:
                    model = ARIMA(prices, order=(5, 1, 0))
                    model_fit = model.fit()
                    forecast = model_fit.forecast(steps=forecast_days)
                    confidence = 'high'
                    logger.info(f"ARIMA forecast completed for {pair}")
                except Exception as e:
                    logger.warning(f"ARIMA failed for {pair}, falling back to linear: {e}")
                    model_type = 'linear'
            
            if model_type == 'linear' or forecast is None:
                X = np.arange(len(prices)).reshape(-1, 1)
                y = prices
                model = LinearRegression()
                model.fit(X, y)
                future_X = np.arange(len(prices), len(prices) + forecast_days).reshape(-1, 1)
                forecast = model.predict(future_X)
                confidence = 'medium'
                logger.info(f"Linear regression forecast completed for {pair}")
            
            # Validate forecast
            if forecast is None or len(forecast) == 0:
                logger.error(f"Forecast generation failed for {pair}")
                return None, {'error': 'forecast_failed', 'pair': pair}
            
            forecast_price = forecast[-1]
            
            # Validate forecast price
            if forecast_price <= 0 or np.isnan(forecast_price):
                logger.error(f"Invalid forecast price for {pair}: {forecast_price}")
                return None, {'error': 'invalid_forecast', 'pair': pair}
            
            # Calculate change percentage
            price_change = forecast_price - current_price
            price_change_pct = (price_change / current_price) * 100
            trend = 'up' if forecast_price > current_price else 'down'
            
            # Статистика
            stats = {
                'model': model_type.upper(),
                'current': round(current_price, 2),
                'predicted': round(forecast_price, 2),
                'change': round(price_change_pct, 2),
                'trend': '📈 Upward' if trend == 'up' else '📉 Downward',
                'confidence': confidence,
                'data_source': 'Yahoo Finance',
                'days_analyzed': len(df),
                'forecast_date': (datetime.now() + timedelta(days=forecast_days)).strftime('%Y-%m-%d'),
                'model_type': model_type,
                'forecast_days': forecast_days
            }
            
            # Создание графика
            plt.figure(figsize=(12, 6))
            
            # Исторические данные
            dates = np.arange(len(prices))
            plt.plot(dates, prices, label='Historical Data', linewidth=2, color='#2196F3')
            
            # Прогноз
            forecast_dates = np.arange(len(prices), len(prices) + forecast_days)
            plt.plot(forecast_dates, forecast, label='Forecast', linewidth=2, 
                    color='#FF5722', linestyle='--')
            
            # Тренд
            all_dates = np.concatenate([dates, forecast_dates])
            all_prices = np.concatenate([prices, forecast])
            z = np.polyfit(all_dates, all_prices, 1)
            p = np.poly1d(z)
            plt.plot(all_dates, p(all_dates), 'g--', alpha=0.5, label='Trend Line')
            
            plt.title(f'{pair} - {forecast_days} Day Forecast ({model_type.upper()})', 
                     fontsize=16, fontweight='bold')
            plt.xlabel('Days', fontsize=12)
            plt.ylabel('Price ($)', fontsize=12)
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.axvline(x=len(prices)-1, color='red', linestyle=':', alpha=0.5)
            plt.tight_layout()
            
            # Сохранение в буфер
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi)
            buf.seek(0)
            plt.close()
            
            logger.info(f"Prediction generated successfully for {pair}")
            return buf.getvalue(), stats
            
        except Exception as e:
            logger.error(f"Prediction generation error for {pair}: {e}", exc_info=True)
            return None, {'error': 'exception', 'pair': pair, 'message': str(e)}
    
    def save_prediction(self, user_id: int, pair: str, predicted_price: float, 
                       model_type: str, forecast_days: int = 7):
        """Save prediction to database for accuracy tracking."""
        if not self.db:
            return
        
        try:
            # Extract asset symbol from pair (e.g., BTC-USD -> BTC)
            asset_symbol = pair.split('-')[0]
            
            # Calculate target date
            target_date = datetime.now() + timedelta(days=forecast_days)
            
            # Save to database
            self.db.add_prediction(
                user_id=user_id,
                asset_symbol=asset_symbol,
                model_type=model_type,
                predicted_price=predicted_price,
                target_date=target_date
            )
            logger.info(f"Saved prediction for {asset_symbol} by user {user_id}")
        except Exception as e:
            logger.error(f"Error saving prediction: {e}")
    
    def get_accuracy_comparison(self, asset_symbol: str, days: int = 30) -> Dict:
        """Get accuracy comparison between models."""
        if not self.db:
            return None
        
        try:
            return self.db.get_model_accuracy_stats(asset_symbol, days)
        except Exception as e:
            logger.error(f"Error getting accuracy stats: {e}")
            return None
    
    async def generate_cbr_prediction(self, currency: str, model_type: str = 'arima',
                                     days: int = 90, forecast_days: int = 7) -> Tuple[Optional[bytes], Dict]:
        """
        Generate prediction for CBR exchange rates.
        
        Args:
            currency: Currency code (USD, EUR, etc.)
            model_type: 'arima', 'linear', or 'prophet'
            days: Historical days to analyze
            forecast_days: Days to forecast ahead
        
        Returns:
            Tuple of (image bytes, statistics dict)
        """
        try:
            logger.info(f"Generating CBR prediction for {currency}, model: {model_type}, days: {days}")
            
            # Fetch CBR historical data
            rates_data = await self.fetch_cbr_historical_rates(currency, days)
            
            if not rates_data or len(rates_data) < 30:
                logger.warning(f"Insufficient CBR data for {currency}")
                return None, {'error': 'insufficient_data', 'pair': f"{currency}/RUB", 'days_available': len(rates_data)}
            
            # Extract prices
            dates = [item[0] for item in rates_data]
            prices = np.array([item[1] for item in rates_data])
            current_price = prices[-1]
            
            # Validate price data
            if current_price <= 0 or np.isnan(current_price):
                logger.error(f"Invalid current CBR rate for {currency}: {current_price}")
                return None, {'error': 'invalid_price', 'pair': f"{currency}/RUB"}
            
            # Forecasting (same logic as crypto)
            forecast = None
            confidence = 'medium'
            
            if model_type == 'prophet' and PROPHET_AVAILABLE:
                try:
                    import pandas as pd
                    prophet_df = pd.DataFrame({'ds': dates, 'y': prices})
                    model = Prophet(daily_seasonality=True)
                    model.fit(prophet_df)
                    future = model.make_future_dataframe(periods=forecast_days)
                    forecast_df = model.predict(future)
                    forecast = forecast_df['yhat'].tail(forecast_days).values
                    confidence = 'high'
                    logger.info(f"Prophet forecast completed for CBR {currency}")
                except Exception as e:
                    logger.warning(f"Prophet failed for CBR {currency}, falling back to ARIMA: {e}")
                    model_type = 'arima'
            
            if model_type == 'arima' and forecast is None:
                try:
                    model = ARIMA(prices, order=(5, 1, 0))
                    model_fit = model.fit()
                    forecast = model_fit.forecast(steps=forecast_days)
                    confidence = 'high'
                    logger.info(f"ARIMA forecast completed for CBR {currency}")
                except Exception as e:
                    logger.warning(f"ARIMA failed for CBR {currency}, falling back to linear: {e}")
                    model_type = 'linear'
            
            if model_type == 'linear' or forecast is None:
                X = np.arange(len(prices)).reshape(-1, 1)
                y = prices
                model = LinearRegression()
                model.fit(X, y)
                future_X = np.arange(len(prices), len(prices) + forecast_days).reshape(-1, 1)
                forecast = model.predict(future_X)
                confidence = 'medium'
                logger.info(f"Linear regression forecast completed for CBR {currency}")
            
            # Validate forecast
            if forecast is None or len(forecast) == 0:
                logger.error(f"CBR forecast generation failed for {currency}")
                return None, {'error': 'forecast_failed', 'pair': f"{currency}/RUB"}
            
            forecast_price = forecast[-1]
            
            if forecast_price <= 0 or np.isnan(forecast_price):
                logger.error(f"Invalid CBR forecast price for {currency}: {forecast_price}")
                return None, {'error': 'invalid_forecast', 'pair': f"{currency}/RUB"}
            
            # Calculate statistics
            price_change = forecast_price - current_price
            price_change_pct = (price_change / current_price) * 100
            trend = 'up' if forecast_price > current_price else 'down'
            
            stats = {
                'model': model_type.upper(),
                'current': round(current_price, 4),
                'predicted': round(forecast_price, 4),
                'change': round(price_change_pct, 2),
                'trend': '📈 Upward' if trend == 'up' else '📉 Downward',
                'confidence': confidence,
                'data_source': 'CBR API',
                'days_analyzed': len(rates_data),
                'forecast_date': (datetime.now() + timedelta(days=forecast_days)).strftime('%Y-%m-%d'),
                'model_type': model_type,
                'forecast_days': forecast_days
            }
            
            # Create chart
            plt.figure(figsize=(12, 6))
            
            # Historical data
            hist_x = np.arange(len(prices))
            plt.plot(hist_x, prices, label='Historical Data', linewidth=2, color='#2196F3')
            
            # Forecast
            forecast_x = np.arange(len(prices), len(prices) + forecast_days)
            plt.plot(forecast_x, forecast, label='Forecast', linewidth=2, 
                    color='#FF5722', linestyle='--')
            
            # Trend line
            all_x = np.concatenate([hist_x, forecast_x])
            all_prices = np.concatenate([prices, forecast])
            z = np.polyfit(all_x, all_prices, 1)
            p = np.poly1d(z)
            plt.plot(all_x, p(all_x), 'g--', alpha=0.5, label='Trend Line')
            
            plt.title(f'CBR Rate: {currency}/RUB - {forecast_days} Day Forecast ({model_type.upper()})', 
                     fontsize=16, fontweight='bold')
            plt.xlabel('Days', fontsize=12)
            plt.ylabel('Rate (RUB)', fontsize=12)
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.axvline(x=len(prices)-1, color='red', linestyle=':', alpha=0.5)
            plt.tight_layout()
            
            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi)
            buf.seek(0)
            plt.close()
            
            logger.info(f"CBR prediction generated successfully for {currency}")
            return buf.getvalue(), stats
        
        except Exception as e:
            logger.error(f"CBR prediction generation error for {currency}: {e}", exc_info=True)
            return None, {'error': 'exception', 'pair': f"{currency}/RUB", 'message': str(e)}
    
    def generate_stock_prediction(self, ticker: str, model_type: str = 'arima',
                                 days: int = 90, forecast_days: int = 7) -> Tuple[Optional[bytes], Dict]:
        """
        Generate prediction for stock prices.
        
        Args:
            ticker: Stock ticker (e.g., 'AAPL', 'SBER.ME')
            model_type: 'arima', 'linear', or 'prophet'
            days: Historical days to analyze
            forecast_days: Days to forecast ahead
        
        Returns:
            Tuple of (image bytes, statistics dict)
        """
        try:
            logger.info(f"Generating stock prediction for {ticker}, model: {model_type}, days: {days}")
            
            # Fetch stock data via yfinance
            stock = yf.Ticker(ticker)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            df = stock.history(start=start_date, end=end_date)
            
            # Validate data availability
            if df.empty:
                logger.warning(f"No stock data available for {ticker}")
                return None, {'error': 'no_data', 'pair': ticker}
            
            if len(df) < 30:
                logger.warning(f"Insufficient stock data for {ticker}: only {len(df)} days")
                return None, {'error': 'insufficient_data', 'pair': ticker, 'days_available': len(df)}
            
            prices = df['Close'].values
            current_price = prices[-1]
            
            # Validate price data
            if current_price <= 0 or np.isnan(current_price):
                logger.error(f"Invalid current stock price for {ticker}: {current_price}")
                return None, {'error': 'invalid_price', 'pair': ticker}
            
            # Forecasting (same logic as crypto)
            forecast = None
            confidence = 'medium'
            
            if model_type == 'prophet' and PROPHET_AVAILABLE:
                try:
                    prophet_df = df.reset_index()[['Date', 'Close']].rename(columns={'Date': 'ds', 'Close': 'y'})
                    model = Prophet(daily_seasonality=True)
                    model.fit(prophet_df)
                    future = model.make_future_dataframe(periods=forecast_days)
                    forecast_df = model.predict(future)
                    forecast = forecast_df['yhat'].tail(forecast_days).values
                    confidence = 'high'
                    logger.info(f"Prophet forecast completed for stock {ticker}")
                except Exception as e:
                    logger.warning(f"Prophet failed for stock {ticker}, falling back to ARIMA: {e}")
                    model_type = 'arima'
            
            if model_type == 'arima' and forecast is None:
                try:
                    model = ARIMA(prices, order=(5, 1, 0))
                    model_fit = model.fit()
                    forecast = model_fit.forecast(steps=forecast_days)
                    confidence = 'high'
                    logger.info(f"ARIMA forecast completed for stock {ticker}")
                except Exception as e:
                    logger.warning(f"ARIMA failed for stock {ticker}, falling back to linear: {e}")
                    model_type = 'linear'
            
            if model_type == 'linear' or forecast is None:
                X = np.arange(len(prices)).reshape(-1, 1)
                y = prices
                model = LinearRegression()
                model.fit(X, y)
                future_X = np.arange(len(prices), len(prices) + forecast_days).reshape(-1, 1)
                forecast = model.predict(future_X)
                confidence = 'medium'
                logger.info(f"Linear regression forecast completed for stock {ticker}")
            
            # Validate forecast
            if forecast is None or len(forecast) == 0:
                logger.error(f"Stock forecast generation failed for {ticker}")
                return None, {'error': 'forecast_failed', 'pair': ticker}
            
            forecast_price = forecast[-1]
            
            if forecast_price <= 0 or np.isnan(forecast_price):
                logger.error(f"Invalid stock forecast price for {ticker}: {forecast_price}")
                return None, {'error': 'invalid_forecast', 'pair': ticker}
            
            # Calculate statistics
            price_change = forecast_price - current_price
            price_change_pct = (price_change / current_price) * 100
            trend = 'up' if forecast_price > current_price else 'down'
            
            stats = {
                'model': model_type.upper(),
                'current': round(current_price, 2),
                'predicted': round(forecast_price, 2),
                'change': round(price_change_pct, 2),
                'trend': '📈 Upward' if trend == 'up' else '📉 Downward',
                'confidence': confidence,
                'data_source': 'Yahoo Finance',
                'days_analyzed': len(df),
                'forecast_date': (datetime.now() + timedelta(days=forecast_days)).strftime('%Y-%m-%d'),
                'model_type': model_type,
                'forecast_days': forecast_days
            }
            
            # Create chart
            plt.figure(figsize=(12, 6))
            
            # Historical data
            dates = np.arange(len(prices))
            plt.plot(dates, prices, label='Historical Data', linewidth=2, color='#2196F3')
            
            # Forecast
            forecast_dates = np.arange(len(prices), len(prices) + forecast_days)
            plt.plot(forecast_dates, forecast, label='Forecast', linewidth=2, 
                    color='#FF5722', linestyle='--')
            
            # Trend line
            all_dates = np.concatenate([dates, forecast_dates])
            all_prices = np.concatenate([prices, forecast])
            z = np.polyfit(all_dates, all_prices, 1)
            p = np.poly1d(z)
            plt.plot(all_dates, p(all_dates), 'g--', alpha=0.5, label='Trend Line')
            
            plt.title(f'{ticker} - {forecast_days} Day Forecast ({model_type.upper()})', 
                     fontsize=16, fontweight='bold')
            plt.xlabel('Days', fontsize=12)
            plt.ylabel('Price ($)', fontsize=12)
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.axvline(x=len(prices)-1, color='red', linestyle=':', alpha=0.5)
            plt.tight_layout()
            
            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi)
            buf.seek(0)
            plt.close()
            
            logger.info(f"Stock prediction generated successfully for {ticker}")
            return buf.getvalue(), stats
        
        except Exception as e:
            logger.error(f"Stock prediction generation error for {ticker}: {e}", exc_info=True)
            return None, {'error': 'exception', 'pair': ticker, 'message': str(e)}
    
    async def generate_prediction_with_vision_analysis(self, symbol: str, asset_type: str = 'crypto',
                                                       model_type: str = 'arima', days: int = 90,
                                                       forecast_days: int = 7) -> Tuple[Optional[bytes], Dict, Optional[str]]:
        """
        Generate prediction with AI vision analysis of the chart.
        
        Args:
            symbol: Asset symbol (e.g., 'BTC-USD', 'AAPL', 'SBER.ME')
            asset_type: 'crypto', 'stock', or 'cbr'
            model_type: 'arima', 'linear', or 'prophet'
            days: Historical days to analyze
            forecast_days: Days to forecast ahead
        
        Returns:
            Tuple of (image bytes, statistics dict, vision analysis text)
        """
        try:
            # Generate standard prediction
            if asset_type == 'cbr':
                chart_bytes, stats = await self.generate_cbr_prediction(symbol, model_type, days, forecast_days)
            elif asset_type == 'stock':
                chart_bytes, stats = self.generate_stock_prediction(symbol, model_type, days, forecast_days)
            else:  # crypto
                chart_bytes, stats = self.generate_prediction(symbol, model_type, days, forecast_days)
            
            if not chart_bytes or 'error' in stats:
                logger.warning(f"Failed to generate base prediction for {symbol}")
                return chart_bytes, stats, None
            
            # If AI service is not available, return without vision analysis
            if not self.ai_service or not self.ai_service.vision_available:
                logger.info("Vision analysis not available, returning standard prediction")
                return chart_bytes, stats, None
            
            # Save chart to temporary file for vision analysis
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as tmp_file:
                tmp_file.write(chart_bytes)
                tmp_path = tmp_file.name
            
            try:
                # Prepare vision analysis prompt
                vision_prompt = f"""
Analyze this price forecast chart for {symbol}.

Key information:
- Current price: ${stats.get('current', 0):,.2f}
- Predicted price ({forecast_days} days): ${stats.get('predicted', 0):,.2f}
- Expected change: {stats.get('change', 0):+.2f}%
- Model used: {stats.get('model', 'Unknown')}
- Trend: {stats.get('trend', 'Unknown')}

Provide a brief analysis (3-4 sentences) covering:
1. What the chart pattern suggests about the trend
2. Key support/resistance levels visible
3. Overall outlook for the next {forecast_days} days
4. Important disclaimer about forecast reliability

Keep it concise and educational.
"""
                
                # Get vision analysis
                logger.info(f"Requesting vision analysis for {symbol}...")
                vision_analysis = await self.ai_service.get_vision_analysis(tmp_path, vision_prompt)
                
                logger.info(f"Vision analysis completed for {symbol}")
                return chart_bytes, stats, vision_analysis
            
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        
        except Exception as e:
            logger.error(f"Error in prediction with vision analysis for {symbol}: {e}", exc_info=True)
            return None, {'error': 'exception', 'pair': symbol, 'message': str(e)}, None
