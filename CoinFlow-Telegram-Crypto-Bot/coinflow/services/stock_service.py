"""Stock market data service for global and Russian stocks."""

import yfinance as yf
import requests
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from ..utils.logger import setup_logger
from ..utils.cache import Cache

logger = setup_logger('stock_service')


class StockService:
    """Service for fetching stock market data."""
    
    # Popular global stocks (20+ tickers)
    GLOBAL_STOCKS = {
        'AAPL': 'Apple Inc.',
        'MSFT': 'Microsoft',
        'GOOGL': 'Alphabet (Google)',
        'AMZN': 'Amazon',
        'NVDA': 'NVIDIA',
        'TSLA': 'Tesla',
        'META': 'Meta (Facebook)',
        'BRK-B': 'Berkshire Hathaway',
        'V': 'Visa',
        'JPM': 'JPMorgan Chase',
        'JNJ': 'Johnson & Johnson',
        'WMT': 'Walmart',
        'PG': 'Procter & Gamble',
        'MA': 'Mastercard',
        'HD': 'Home Depot',
        'BAC': 'Bank of America',
        'XOM': 'ExxonMobil',
        'DIS': 'Disney',
        'NFLX': 'Netflix',
        'INTC': 'Intel',
        'AMD': 'AMD',
        'PYPL': 'PayPal',
        'ADBE': 'Adobe',
        'CRM': 'Salesforce'
    }
    
    # Popular Russian stocks (15+ tickers)
    RUSSIAN_STOCKS = {
        'SBER': 'Сбербанк',
        'GAZP': 'Газпром',
        'LKOH': 'Лукойл',
        'GMKN': 'Норникель',
        'YNDX': 'Яндекс',
        'ROSN': 'Роснефть',
        'NVTK': 'Новатэк',
        'TATN': 'Татнефть',
        'MGNT': 'Магнит',
        'MTSS': 'МТС',
        'SNGS': 'Сургутнефтегаз',
        'ALRS': 'Алроса',
        'PLZL': 'Полюс Золото',
        'VTBR': 'ВТБ',
        'CHMF': 'Северсталь',
        'PHOR': 'ФосАгро'
    }
    
    # CBR currencies
    CBR_CURRENCIES = {
        'USD': 'Доллар США',
        'EUR': 'Евро',
        'CNY': 'Китайский юань',
        'GBP': 'Фунт стерлингов',
        'JPY': 'Японская иена',
        'TRY': 'Турецкая лира',
        'KZT': 'Казахстанский тенге',
        'BYN': 'Белорусский рубль'
    }
    
    def __init__(self, cache_ttl: int = 300):
        """
        Initialize stock service.
        
        Args:
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        self.cache = Cache(ttl_seconds=cache_ttl)
        logger.info("StockService initialized")
    
    def get_global_stock(self, ticker: str) -> Optional[Dict]:
        """
        Get global stock data from Yahoo Finance.
        
        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
        
        Returns:
            Dict with stock data or None if error
        """
        cache_key = f'global_stock_{ticker}'
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for {ticker}")
            return cached
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get current price and change
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            previous_close = info.get('previousClose')
            
            if not current_price or not previous_close:
                logger.warning(f"No price data for {ticker}")
                return None
            
            change_usd = current_price - previous_close
            change_pct = (change_usd / previous_close) * 100
            
            data = {
                'ticker': ticker,
                'name': self.GLOBAL_STOCKS.get(ticker, info.get('longName', ticker)),
                'price': current_price,
                'currency': info.get('currency', 'USD'),
                'change_usd': change_usd,
                'change_pct': change_pct,
                'volume': info.get('volume', 0),
                'market_cap': info.get('marketCap', 0),
                'timestamp': datetime.now().isoformat()
            }
            
            self.cache.set(cache_key, data)
            logger.info(f"Fetched {ticker}: ${current_price:.2f}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            return None
    
    def get_global_stock_history(self, ticker: str, days: int = 30) -> Optional[List[Tuple[str, float]]]:
        """
        Get historical data for global stock.
        
        Args:
            ticker: Stock ticker
            days: Number of days of history
        
        Returns:
            List of (date, price) tuples or None
        """
        try:
            stock = yf.Ticker(ticker)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                return None
            
            # Extract dates and closing prices
            history = [(date.strftime('%Y-%m-%d'), float(row['Close'])) 
                      for date, row in hist.iterrows()]
            
            logger.info(f"Fetched {len(history)} days of history for {ticker}")
            return history
            
        except Exception as e:
            logger.error(f"Error fetching history for {ticker}: {e}")
            return None
    
    def get_russian_stock(self, ticker: str) -> Optional[Dict]:
        """
        Get Russian stock data from MOEX API.
        
        Args:
            ticker: Stock ticker (e.g., 'SBER')
        
        Returns:
            Dict with stock data or None if error
        """
        cache_key = f'russian_stock_{ticker}'
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for Russian stock {ticker}")
            return cached
        
        try:
            # MOEX API endpoint for stock data
            url = f'https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json'
            params = {'iss.meta': 'off', 'iss.only': 'securities,marketdata'}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data_json = response.json()
            
            # Parse securities data
            securities = data_json.get('securities', {})
            sec_data = securities.get('data', [[]])[0] if securities.get('data') else []
            sec_cols = securities.get('columns', [])
            
            # Parse market data
            marketdata = data_json.get('marketdata', {})
            market_data = marketdata.get('data', [[]])[0] if marketdata.get('data') else []
            market_cols = marketdata.get('columns', [])
            
            if not sec_data or not market_data:
                logger.warning(f"No data for Russian stock {ticker}")
                return None
            
            # Create dicts from data
            sec_dict = dict(zip(sec_cols, sec_data))
            market_dict = dict(zip(market_cols, market_data))
            
            current_price = market_dict.get('LAST')
            previous_price = sec_dict.get('PREVPRICE')
            
            if not current_price or not previous_price:
                return None
            
            change_rub = current_price - previous_price
            change_pct = (change_rub / previous_price) * 100 if previous_price else 0
            
            data = {
                'ticker': ticker,
                'name': self.RUSSIAN_STOCKS.get(ticker, sec_dict.get('SHORTNAME', ticker)),
                'price': current_price,
                'currency': 'RUB',
                'change_rub': change_rub,
                'change_pct': change_pct,
                'volume': market_dict.get('VOLTODAY', 0),
                'timestamp': datetime.now().isoformat()
            }
            
            self.cache.set(cache_key, data)
            logger.info(f"Fetched Russian stock {ticker}: {current_price:.2f} RUB")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching Russian stock {ticker}: {e}")
            return None
    
    def get_cbr_rate(self, currency: str = 'USD') -> Optional[Dict]:
        """
        Get official CBR (Central Bank of Russia) exchange rate.
        
        Args:
            currency: Currency code (e.g., 'USD', 'EUR')
        
        Returns:
            Dict with rate data or None if error
        """
        cache_key = f'cbr_rate_{currency}'
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for CBR {currency}")
            return cached
        
        try:
            # CBR daily JSON API
            url = 'https://www.cbr-xml-daily.ru/daily_json.js'
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data_json = response.json()
            valute = data_json.get('Valute', {})
            
            if currency not in valute:
                logger.warning(f"Currency {currency} not found in CBR data")
                return None
            
            curr_data = valute[currency]
            
            current_rate = curr_data.get('Value')
            previous_rate = curr_data.get('Previous')
            
            if not current_rate or not previous_rate:
                return None
            
            change = current_rate - previous_rate
            change_pct = (change / previous_rate) * 100
            
            data = {
                'currency': currency,
                'name': self.CBR_CURRENCIES.get(currency, curr_data.get('Name', currency)),
                'rate': current_rate,
                'nominal': curr_data.get('Nominal', 1),  # Some currencies like JPY have nominal > 1
                'change': change,
                'change_pct': change_pct,
                'date': data_json.get('Date', datetime.now().isoformat()),
                'timestamp': datetime.now().isoformat()
            }
            
            self.cache.set(cache_key, data)
            logger.info(f"Fetched CBR rate {currency}: {current_rate:.2f} RUB")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching CBR rate for {currency}: {e}")
            return None
    
    def get_all_cbr_rates(self) -> Dict[str, Dict]:
        """
        Get all CBR exchange rates at once.
        
        Returns:
            Dict mapping currency codes to rate data
        """
        try:
            url = 'https://www.cbr-xml-daily.ru/daily_json.js'
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data_json = response.json()
            valute = data_json.get('Valute', {})
            
            rates = {}
            for currency in self.CBR_CURRENCIES.keys():
                if currency in valute:
                    curr_data = valute[currency]
                    current_rate = curr_data.get('Value')
                    previous_rate = curr_data.get('Previous')
                    
                    if current_rate and previous_rate:
                        change = current_rate - previous_rate
                        change_pct = (change / previous_rate) * 100
                        
                        rates[currency] = {
                            'currency': currency,
                            'name': self.CBR_CURRENCIES.get(currency, curr_data.get('Name', currency)),
                            'rate': current_rate,
                            'nominal': curr_data.get('Nominal', 1),
                            'change': change,
                            'change_pct': change_pct,
                            'date': data_json.get('Date', datetime.now().isoformat())
                        }
            
            logger.info(f"Fetched {len(rates)} CBR rates")
            return rates
            
        except Exception as e:
            logger.error(f"Error fetching all CBR rates: {e}")
            return {}
