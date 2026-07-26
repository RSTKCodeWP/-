"""Currency converter service with multi-exchange aggregation."""

import requests
import aiohttp
import asyncio
from typing import Optional, List, Tuple
from bestchange_api import BestChange
from ..utils.cache import CurrencyCache
from ..utils.logger import setup_logger

logger = setup_logger('converter')


class CurrencyConverter:
    """Агрегатор курсов валют с разных площадок."""
    
    def __init__(self, cache_ttl: int = 60):
        self.exchange_rate_api = "https://api.exchangerate-api.com/v4/latest"
        self.cbr_api_url = "https://www.cbr-xml-daily.ru/daily_json.js"
        self.crypto_symbols = [
            # Top crypto
            'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'XRP', 'ADA', 'AVAX', 'DOT', 'MATIC',
            # Meme coins
            'DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF',
            # Popular altcoins
            'TON', 'NOT', 'TRX', 'LINK', 'UNI', 'ATOM', 'LTC', 'XLM', 'BCH', 'ALGO',
            'VET', 'FIL', 'HBAR', 'APE', 'NEAR', 'QNT', 'AAVE', 'GRT', 'XTZ', 'SAND',
            # DeFi & Layer 2
            'ARB', 'OP', 'IMX', 'LDO', 'MKR', 'CRV'
        ]
        self.crypto_providers = [
            {'name': 'BestChange', 'method': self.get_bestchange_rate},
            {'name': 'Binance', 'method': self.get_binance_ticker},
            {'name': 'Bybit', 'method': self.get_bybit_ticker},
            {'name': 'HTX', 'method': self.get_htx_ticker},
            {'name': 'KuCoin', 'method': self.get_kucoin_ticker},
            {'name': 'Gate.io', 'method': self.get_gateio_ticker},
        ]
        self.bestchange = BestChange()
        self.bestchange_ids = {
            'BTC': 93,
            'USDT': 115,
            'ETH': 139,
            'RUB': 643,
            'CNY': 155,
        }
        
        # Cache system
        self.cache = CurrencyCache(ttl_seconds=cache_ttl)
        
        # Bot reference (set later)
        self.bot = None
    
    def get_binance_ticker(self, from_symbol: str, to_symbol: str) -> Optional[float]:
        """Получить курс с Binance"""
        try:
            pair = f"{from_symbol}{to_symbol}"
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return float(data['price'])
        except Exception as e:
            logger.debug(f"Binance error for {from_symbol}/{to_symbol}: {e}")
        return None
    
    def get_bybit_ticker(self, from_symbol: str, to_symbol: str) -> Optional[float]:
        """Получить курс с Bybit"""
        try:
            pair = f"{from_symbol}{to_symbol}"
            url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={pair}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['retCode'] == 0 and data['result']['list']:
                    return float(data['result']['list'][0]['lastPrice'])
        except Exception as e:
            logger.debug(f"Bybit error for {from_symbol}/{to_symbol}: {e}")
        return None
    
    def get_htx_ticker(self, from_symbol: str, to_symbol: str) -> Optional[float]:
        """Получить курс с HTX (Huobi)"""
        try:
            pair = f"{from_symbol.lower()}{to_symbol.lower()}"
            url = f"https://api.huobi.pro/market/detail/merged?symbol={pair}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'ok':
                    return float(data['tick']['close'])
        except Exception as e:
            logger.debug(f"HTX error for {from_symbol}/{to_symbol}: {e}")
        return None
    
    def get_kucoin_ticker(self, from_symbol: str, to_symbol: str) -> Optional[float]:
        """Получить курс с KuCoin"""
        try:
            pair = f"{from_symbol}-{to_symbol}"
            url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={pair}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['code'] == '200000':
                    return float(data['data']['price'])
        except Exception as e:
            logger.debug(f"KuCoin error for {from_symbol}/{to_symbol}: {e}")
        return None
    
    def get_gateio_ticker(self, from_symbol: str, to_symbol: str) -> Optional[float]:
        """Получить курс с Gate.io"""
        try:
            pair = f"{from_symbol}_{to_symbol}"
            url = f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={pair}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data:
                    return float(data[0]['last'])
        except Exception as e:
            logger.debug(f"Gate.io error for {from_symbol}/{to_symbol}: {e}")
        return None
    
    def get_bestchange_rate(self, from_symbol: str, to_symbol: str) -> Optional[float]:
        """Получить курс с BestChange"""
        try:
            if from_symbol in self.bestchange_ids and to_symbol in self.bestchange_ids:
                from_id = self.bestchange_ids[from_symbol]
                to_id = self.bestchange_ids[to_symbol]
                rate = self.bestchange.get_rate(from_id, to_id)
                if rate:
                    return float(rate)
        except Exception as e:
            logger.debug(f"BestChange error for {from_symbol}/{to_symbol}: {e}")
        return None
    
    def get_fiat_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Получить курс фиатных валют"""
        try:
            url = f"{self.exchange_rate_api}/{from_currency}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if to_currency in data['rates']:
                    return float(data['rates'][to_currency])
        except Exception as e:
            logger.debug(f"Fiat rate error for {from_currency}/{to_currency}: {e}")
        return None

    def get_active_providers(self, user_id: int) -> List[dict]:
        """Get active providers for user."""
        if not self.bot:
            return self.crypto_providers
        
        user = self.bot.db.get_user(user_id)
        if not user or not user.providers:
            return self.crypto_providers
        
        return [p for p in self.crypto_providers if user.providers.get(p['name'], True)]

    def get_cbrf_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Получить официальный курс ЦБ РФ"""
        try:
            response = requests.get(self.cbr_api_url, timeout=10).json()
            rates = response.get('Valute', {})
            
            if from_currency == 'RUB':
                if to_currency in rates:
                    return 1 / (rates[to_currency]['Value'] / rates[to_currency]['Nominal'])
            elif to_currency == 'RUB':
                if from_currency in rates:
                    return rates[from_currency]['Value'] / rates[from_currency]['Nominal']
            return None
        except Exception as e:
            logger.debug(f"CBRF rate error: {e}")
            return None

    def get_crypto_rate_aggregated(self, from_symbol: str, to_symbol: str, user_id: int) -> Optional[float]:
        """Get crypto rate from first available provider."""
        # Check cache first
        cache_key = f"{from_symbol}_{to_symbol}"
        cached_rate = self.cache.get(cache_key)
        if cached_rate is not None:
            return cached_rate
        
        for provider in self.get_active_providers(user_id):
            rate = provider['method'](from_symbol, to_symbol)
            if rate is not None:
                self.cache.set(cache_key, rate)
                logger.info(f"Rate {from_symbol}/{to_symbol} = {rate} from {provider['name']}")
                return rate
        return None

    def get_all_crypto_rates(self, from_symbol: str, to_symbol: str, user_id: int) -> List[Tuple[str, float]]:
        """Get rates from all available providers."""
        rates = []
        for provider in self.get_active_providers(user_id):
            rate = provider['method'](from_symbol, to_symbol)
            if rate is not None:
                rates.append((provider['name'], rate))
        return rates
    
    async def get_all_crypto_rates_async(self, from_symbol: str, to_symbol: str, user_id: int) -> List[Tuple[str, float]]:
        """Get rates from all providers asynchronously."""
        async def fetch_rate(session, provider):
            try:
                # Since the methods are sync, run them in executor
                loop = asyncio.get_event_loop()
                rate = await loop.run_in_executor(None, provider['method'], from_symbol, to_symbol)
                if rate is not None:
                    return (provider['name'], rate)
            except Exception as e:
                logger.debug(f"Async fetch error for {provider['name']}: {e}")
            return None
        
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_rate(session, p) for p in self.get_active_providers(user_id)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            rates = []
            for result in results:
                if result and not isinstance(result, Exception):
                    rates.append(result)
            return rates

    def get_rate(self, from_currency: str, to_currency: str, user_id: int = None) -> Optional[float]:
        """Get exchange rate between two currencies."""
        from_currency, to_currency = from_currency.upper(), to_currency.upper()
        if from_currency == to_currency:
            return 1.0

        # Check cache first
        cache_key = f"{from_currency}_{to_currency}"
        cached_rate = self.cache.get(cache_key)
        if cached_rate is not None:
            return cached_rate

        # Check user preferences for RUB source
        if user_id and self.bot:
            user = self.bot.db.get_user(user_id)
            if user and user.rub_source == 'cbrf' and ('RUB' in [from_currency, to_currency]):
                rate = self.get_cbrf_rate(from_currency, to_currency)
                if rate:
                    self.cache.set(cache_key, rate)
                    return rate

        is_from_crypto = from_currency in self.crypto_symbols
        is_to_crypto = to_currency in self.crypto_symbols

        rate = None
        if is_from_crypto and not is_to_crypto:
            # Crypto → Fiat (e.g. BTC → USD)
            rate_crypto_usd = self.get_crypto_rate_aggregated(from_currency, 'USDT', user_id)
            rate_usd_fiat = self.get_fiat_rate('USD', to_currency)
            rate = rate_crypto_usd * rate_usd_fiat if rate_crypto_usd and rate_usd_fiat else None
        elif not is_from_crypto and is_to_crypto:
            # Fiat → Crypto (e.g. USD → BTC)
            rate_fiat_usd = self.get_fiat_rate(from_currency, 'USD')
            rate_crypto_usd = self.get_crypto_rate_aggregated(to_currency, 'USDT', user_id)
            rate = (rate_fiat_usd / rate_crypto_usd) if rate_fiat_usd and rate_crypto_usd else None
        elif is_from_crypto and is_to_crypto:
            # Crypto → Crypto (e.g. BTC → ETH)
            rate = self.get_crypto_rate_aggregated(from_currency, to_currency, user_id)
        else:
            # Fiat → Fiat - try direct first, then via USDT
            rate = self.get_fiat_rate(from_currency, to_currency)
            
            # If direct conversion failed, try via USDT (e.g. RUB → USDT → CNY)
            if not rate and from_currency != 'USD' and to_currency != 'USD':
                rate_from_usd = self.get_fiat_rate(from_currency, 'USD')
                rate_from_usdt = self.get_crypto_rate_aggregated('USDT', 'USDT', user_id) or 1.0  # USDT ≈ USD
                rate_usd_to = self.get_fiat_rate('USD', to_currency)
                
                if rate_from_usd and rate_usd_to:
                    rate = rate_from_usd * rate_usd_to
                    logger.info(f"Converted {from_currency} → {to_currency} via USD: {rate}")
        
        if rate:
            self.cache.set(cache_key, rate)
        
        return rate

    def convert(self, amount: float, from_currency: str, to_currency: str, user_id: int = None) -> Optional[float]:
        """Convert amount from one currency to another."""
        rate = self.get_rate(from_currency, to_currency, user_id)
        return amount * rate if rate else None
