# 🔌 CoinFlow Bot - API Reference

Complete API documentation for CoinFlow Bot v3.0.

---

## 📋 Bot Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Start the bot and show main menu | `/start` |
| `/admin` | Admin panel (hidden, admin only) | `/admin` |

**Note:** Most features are accessible via buttons or AI chat, not commands.

---

## 🤖 AI Features

### Natural Language Commands

The bot understands natural language through Qwen3-8B AI:

**Currency Conversion:**
- "100 USD to EUR"
- "Сколько стоит биткойн в рублях?"
- "Convert 50 BTC to USDT"

**Market Analysis:**
- "Show me Bitcoin chart"
- "Predict Ethereum price"
- "Compare BTC rates"

**Information:**
- "What's the current BTC price?"
- "Show crypto news"
- "Hello" / "Help"

### Voice Messages

Send voice messages with any command - AI will understand and execute.

---

## 📱 Main Menu Features

### 💱 Quick Convert
Fast currency conversion with preset amounts.

### 📊 Charts & Analytics
- **Rate Charts** - Price history graphs
- **Rate Prediction** - AI-powered forecasts  
- **Compare Rates** - Multi-exchange comparison

### 📈 Markets
- **Stocks** - Global and Russian stocks
- **CS2 Skins** - Counter-Strike 2 item prices

### 💼 Portfolio
Track your crypto/fiat holdings with:
- Portfolio overview
- Profit/loss tracking
- Rebalancing suggestions

### 📰 News & Reports
- Crypto news feed
- Custom reports
- Market alerts

### 🔔 Notifications
- Price alerts
- Smart alerts (AI-driven)
- Custom notifications

### ⭐ Favorites
Save frequently used currency pairs.

### 📜 History
View conversion history and statistics.

### ⚙️ Settings
- Language (EN/RU)
- Prediction model (ARIMA/LSTM/Prophet)
- Theme
- Preferences

---

## 🔧 Services API

### Currency Converter
```python
from coinflow.services import CurrencyConverter

converter = CurrencyConverter(bot)
rate = converter.get_rate('BTC', 'USDT', user_id)
result = converter.convert(100, 'USD', 'EUR', user_id)
```

### AI Service
```python
from coinflow.services import AIService

ai = AIService(ollama_url, model_name)
response = await ai.interpret_user_message(text, lang)
```

### Chart Generator
```python
from coinflow.services import ChartGenerator

charts = ChartGenerator()
chart_data = charts.generate_chart('BTC-USD', days=30)
```

### Prediction Generator
```python
from coinflow.services import PredictionGenerator

predictor = PredictionGenerator()
pred_data, stats = predictor.generate_prediction('BTC-USD', 'arima', 90)
```

---

## 📊 Database Schema

### Users Table
```sql
CREATE TABLE users (
    telegram_id INTEGER PRIMARY KEY,
    lang TEXT DEFAULT 'en',
    prediction_model TEXT DEFAULT 'arima',
    theme TEXT DEFAULT 'light',
    rub_source TEXT DEFAULT 'cbrf'
)
```

### Conversions Table
```sql
CREATE TABLE conversions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    from_currency TEXT,
    to_currency TEXT,
    amount REAL,
    result REAL,
    rate REAL,
    timestamp DATETIME
)
```

### Alerts Table
```sql
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    asset TEXT,
    condition TEXT,
    target_price REAL,
    active BOOLEAN
)
```

---

## 🔌 External APIs

### Crypto Exchanges
- **Binance** - `api.binance.com`
- **Bybit** - `api.bybit.com`
- **HTX** - `api.huobi.pro`
- **KuCoin** - `api.kucoin.com`

### Stock Data
- **Yahoo Finance** - via `yfinance` library

### News
- **CoinDesk** - RSS feed
- **CoinTelegraph** - RSS feed

### AI
- **Ollama** - Local Qwen3-8B model

---

## 🌐 Environment Variables

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321

# Optional
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
DATABASE_URL=sqlite:///data/coinflow.db
LOG_FILE=logs/coinflow.log
```

---

## 📝 Example Usage

### Simple Conversion
```python
# User sends: "100 USD to EUR"
# AI interprets as: CONVERT command
# Bot executes conversion and shows result
```

### Voice Command
```python
# User sends voice: "Сколько стоит биткойн?"
# Bot transcribes and sends to AI
# AI interprets and executes
# Bot responds with current BTC price
```

### Portfolio Management
```python
# User clicks Portfolio button
# Selects "Add Position"
# Enters: BTC, 0.5, 40000
# Bot saves and shows updated portfolio
```

---

**Version:** 3.0.0  
**Last Updated:** 2025-10-20
