"""Chart generation service."""

import io
import aiohttp
import xml.etree.ElementTree as ET
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
from ..utils.logger import setup_logger

logger = setup_logger('charts')


class ChartGenerator:
    """Генератор графиков курсов."""
    
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
    
    def __init__(self, dpi: int = 150):
        self.dpi = dpi
    
    async def fetch_cbr_historical_rates(self, currency: str, days: int = 30) -> List[Tuple[datetime, float]]:
        """
        Fetch historical exchange rates from CBR XML API.
        
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
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Format dates for CBR API (dd/mm/yyyy)
            date_from = start_date.strftime('%d/%m/%Y')
            date_to = end_date.strftime('%d/%m/%Y')
            
            # CBR API URL
            url = f"https://www.cbr.ru/scripts/XML_dynamic.asp?date_req1={date_from}&date_req2={date_to}&VAL_NM_RQ={currency_code}"
            
            logger.info(f"Fetching CBR historical rates for {currency} from {date_from} to {date_to}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"CBR API error: {response.status}")
                        return []
                    
                    xml_data = await response.text()
            
            # Parse XML
            root = ET.fromstring(xml_data)
            rates = []
            
            for record in root.findall('Record'):
                date_str = record.get('Date')  # Format: dd.mm.yyyy
                value_str = record.find('Value').text  # Format: XX,XXXX
                
                # Parse date
                date = datetime.strptime(date_str, '%d.%m.%Y')
                
                # Parse value (replace comma with dot)
                value = float(value_str.replace(',', '.'))
                
                rates.append((date, value))
            
            logger.info(f"Fetched {len(rates)} CBR rates for {currency}")
            return rates
        
        except Exception as e:
            logger.error(f"Error fetching CBR rates for {currency}: {e}")
            return []
    
    def generate_chart(self, pair: str, period: int = 30, theme: str = 'light') -> Tuple[Optional[bytes], Dict]:
        """
        Создать график для пары валют.
        
        Args:
            pair: Trading pair (e.g., "BTC-USD")
            period: Number of days to show
            theme: 'light' or 'dark'
        
        Returns:
            Tuple of (image bytes, statistics dict)
        """
        try:
            logger.info(f"Generating chart for {pair}, period: {period} days")
            
            # Загрузка данных
            ticker = yf.Ticker(pair)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period)
            df = ticker.history(start=start_date, end=end_date)
            
            if df.empty:
                logger.warning(f"No data available for {pair}")
                return None, {}
            
            # Статистика
            stats = {
                'current': round(df['Close'].iloc[-1], 2),
                'avg': round(df['Close'].mean(), 2),
                'high': round(df['High'].max(), 2),
                'low': round(df['Low'].min(), 2),
                'period': period
            }
            
            # Применение темы
            if theme == 'dark':
                plt.style.use('dark_background')
                line_color = '#00D9FF'
                fill_color = '#00D9FF'
            else:
                plt.style.use('default')
                line_color = '#2196F3'
                fill_color = '#2196F3'
            
            # Создание графика
            plt.figure(figsize=(12, 6))
            plt.plot(df.index, df['Close'], label='Close Price', linewidth=2, color=line_color)
            plt.fill_between(df.index, df['Low'], df['High'], alpha=0.2, color=fill_color)
            plt.title(f'{pair} - Last {period} Days', fontsize=16, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Price ($)', fontsize=12)
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # Сохранение в буфер
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi)
            buf.seek(0)
            plt.close()
            
            logger.info(f"Chart generated successfully for {pair}")
            return buf.getvalue(), stats
            
        except Exception as e:
            logger.error(f"Chart generation error for {pair}: {e}")
            return None, {}
    
    async def generate_cbr_chart(self, currency: str, period: int = 30, theme: str = 'light') -> Tuple[Optional[bytes], Dict]:
        """
        Generate chart for CBR exchange rates.
        
        Args:
            currency: Currency code (USD, EUR, etc.)
            period: Number of days to show
            theme: 'light' or 'dark'
        
        Returns:
            Tuple of (image bytes, statistics dict)
        """
        try:
            logger.info(f"Generating CBR chart for {currency}, period: {period} days")
            
            # Fetch historical data
            rates_data = await self.fetch_cbr_historical_rates(currency, period)
            
            if not rates_data:
                logger.warning(f"No CBR data available for {currency}")
                return None, {}
            
            # Extract dates and rates
            dates = [item[0] for item in rates_data]
            rates = [item[1] for item in rates_data]
            
            # Calculate statistics
            stats = {
                'current': round(rates[-1], 4),
                'avg': round(sum(rates) / len(rates), 4),
                'high': round(max(rates), 4),
                'low': round(min(rates), 4),
                'period': period
            }
            
            # Apply theme
            if theme == 'dark':
                plt.style.use('dark_background')
                line_color = '#00D9FF'
                fill_color = '#00D9FF'
            else:
                plt.style.use('default')
                line_color = '#2196F3'
                fill_color = '#2196F3'
            
            # Create chart
            plt.figure(figsize=(12, 6))
            plt.plot(dates, rates, label=f'{currency}/RUB', linewidth=2, color=line_color)
            plt.fill_between(dates, min(rates), rates, alpha=0.2, color=fill_color)
            plt.title(f'CBR Rate: {currency}/RUB - Last {period} Days', fontsize=16, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Rate (RUB)', fontsize=12)
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi)
            buf.seek(0)
            plt.close()
            
            logger.info(f"CBR chart generated successfully for {currency}")
            return buf.getvalue(), stats
        
        except Exception as e:
            logger.error(f"CBR chart generation error for {currency}: {e}")
            return None, {}
    
    def generate_stock_chart(self, ticker: str, period: int = 30, theme: str = 'light') -> Tuple[Optional[bytes], Dict]:
        """
        Generate chart for stock prices.
        
        Args:
            ticker: Stock ticker (e.g., 'AAPL', 'SBER.ME')
            period: Number of days to show
            theme: 'light' or 'dark'
        
        Returns:
            Tuple of (image bytes, statistics dict)
        """
        try:
            logger.info(f"Generating stock chart for {ticker}, period: {period} days")
            
            # Fetch stock data
            stock = yf.Ticker(ticker)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                logger.warning(f"No stock data available for {ticker}")
                return None, {}
            
            # Calculate statistics
            stats = {
                'current': round(df['Close'].iloc[-1], 2),
                'avg': round(df['Close'].mean(), 2),
                'high': round(df['High'].max(), 2),
                'low': round(df['Low'].min(), 2),
                'period': period
            }
            
            # Apply theme
            if theme == 'dark':
                plt.style.use('dark_background')
                line_color = '#00D9FF'
                fill_color = '#00D9FF'
            else:
                plt.style.use('default')
                line_color = '#2196F3'
                fill_color = '#2196F3'
            
            # Create chart
            plt.figure(figsize=(12, 6))
            plt.plot(df.index, df['Close'], label='Close Price', linewidth=2, color=line_color)
            plt.fill_between(df.index, df['Low'], df['High'], alpha=0.2, color=fill_color)
            plt.title(f'{ticker} - Last {period} Days', fontsize=16, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Price', fontsize=12)
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi)
            buf.seek(0)
            plt.close()
            
            logger.info(f"Stock chart generated successfully for {ticker}")
            return buf.getvalue(), stats
        
        except Exception as e:
            logger.error(f"Stock chart generation error for {ticker}: {e}")
            return None, {}
    
    def generate_portfolio_pie_chart(self, portfolio_summary: Dict, theme: str = 'light') -> Optional[bytes]:
        """
        Generate pie chart for portfolio distribution.
        
        Args:
            portfolio_summary: Portfolio summary with by_type distribution
            theme: 'light' or 'dark'
        
        Returns:
            Image bytes or None
        """
        try:
            by_type = portfolio_summary.get('by_type', {})
            
            if not by_type:
                logger.warning("No portfolio data for pie chart")
                return None
            
            # Prepare data
            labels = []
            sizes = []
            colors_map = {
                'crypto': '#F7931A',  # Bitcoin orange
                'stock': '#2196F3',   # Blue
                'fiat': '#4CAF50',    # Green
                'cs2': '#FF6B6B'      # Red
            }
            colors = []
            
            for asset_type, data in by_type.items():
                labels.append(f"{asset_type.title()} ({data['count']})")
                sizes.append(data['total_value_usd'])
                colors.append(colors_map.get(asset_type, '#9E9E9E'))
            
            # Apply theme
            if theme == 'dark':
                plt.style.use('dark_background')
                text_color = 'white'
            else:
                plt.style.use('default')
                text_color = 'black'
            
            # Create pie chart
            fig, ax = plt.subplots(figsize=(10, 8))
            
            wedges, texts, autotexts = ax.pie(
                sizes,
                labels=labels,
                colors=colors,
                autopct='%1.1f%%',
                startangle=90,
                textprops={'color': text_color, 'fontsize': 11}
            )
            
            # Make percentage text bold
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
            
            ax.set_title(
                f'Portfolio Distribution\nTotal: ${portfolio_summary["total_value_usd"]:.2f}',
                fontsize=14,
                fontweight='bold',
                color=text_color,
                pad=20
            )
            
            plt.tight_layout()
            
            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi, bbox_inches='tight')
            buf.seek(0)
            plt.close()
            
            logger.info("Portfolio pie chart generated successfully")
            return buf.getvalue()
        
        except Exception as e:
            logger.error(f"Error generating portfolio pie chart: {e}")
            return None
