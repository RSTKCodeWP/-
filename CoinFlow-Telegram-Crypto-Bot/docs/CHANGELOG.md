# Changelog

All notable changes to CoinFlow Bot will be documented in this file.

## [3.1.0] - 2025-10-21

### 🎨 UX Improvements
- **Localization Fixed:** Added missing Russian translations for `about_btn`, `stats_btn`, and `reports_btn`
- **AI Feedback:** Added typing indicators and loading messages when AI generates responses
  - Users now see "🤖 Thinking..." or "⏳ Generating AI response..." during processing
  - Improves perceived responsiveness and user experience
- **CS2 Interface Enhanced:** Improved navigation with categories, pagination (8 items per page), and hierarchical browsing
  - Categories: Knives, Gloves, Rifles, Snipers, Pistols, SMGs
  - Pagination buttons with "Previous" and "Next" navigation
  - Clean, organized item selection

### ⚡ Performance Enhancements
- **Faster Speech Recognition:** Replaced `openai-whisper` with `faster-whisper`
  - 4-5x faster transcription on CPU
  - Lower memory usage with int8 quantization
  - Automatic fallback to standard Whisper if faster-whisper unavailable
  - Configurable model size (tiny, base, small, medium, large)
  - **Note:** Requires Python 3.11-3.13 (not compatible with 3.14+)
  - Basic voice recognition (without faster-whisper) works on all Python 3.11+ versions

### 🛠️ Technical Changes
- Updated `pyproject.toml` dependencies:
  - Python version restricted to 3.11-3.13 for faster-whisper compatibility
  - Created `voice` extra (basic, no faster-whisper) and `voice-fast` extra (with faster-whisper)
  - Made faster-whisper truly optional to support Python 3.14+
- Enhanced `SpeechRecognitionService` with dual Whisper support
- Added typing action (`send_action('typing')`) to AI and voice handlers
- Localization keys added: `ai_generating`, `ai_thinking`

### 📝 Documentation
- Updated README with v3.1 features and Python version requirements
- Created comprehensive `VOICE_SETUP.md` guide with troubleshooting
- Updated `DOCKER_GUIDE.md` with faster-whisper setup and performance benchmarks
- Added performance notes for speech recognition
- Documented UX improvements

### 🐛 Known Issues
- **Python 3.14 Compatibility:** faster-whisper requires ctranslate2 and onnxruntime which don't have wheels for Python 3.14 yet
  - **Solution 1:** Use `poetry install -E voice` for basic voice recognition (Google Speech API)
  - **Solution 2:** Downgrade to Python 3.12: `poetry env use python3.12`
  - **Solution 3:** Wait for upstream library updates

## [2.7.0] - 2025-10-19

### 🎉 Personal Investment Consultant Features

#### Advanced Analytics 📊
- **AnalyticsService** (320 lines): Comprehensive financial metrics
- **Volatility Analysis**: Daily, annualized, rolling volatility
- **Sharpe Ratio**: Risk-adjusted return calculation
- **Correlation Analysis**: Compare two assets
- **Max Drawdown**: Track portfolio risk
- **Risk Metrics**: VaR (Value at Risk), CVaR calculations
- **AnalyticsHandler** (370 lines): Interactive analytics UI

#### Trading Signals 🎯
- **TradingSignalsService** (280 lines): Technical analysis engine
- **RSI (14)**: Relative Strength Index with overbought/oversold signals
- **MACD**: Moving Average Convergence Divergence with crossovers
- **Moving Averages**: SMA 20/50 with golden/death cross detection
- **Bollinger Bands**: Volatility-based price channels
- **Overall Signal**: Aggregated BUY/SELL/NEUTRAL with confidence score
- **TradingHandler** (280 lines): Signal display and explanations

#### Portfolio Rebalancing 🔄
- **RebalanceService** (290 lines): Portfolio optimization engine
- **5 Preset Strategies**: Conservative, Balanced, Aggressive, HODL, DeFi
- **Custom Allocation**: Set your own target percentages
- **Deviation Analysis**: Track portfolio drift from targets
- **Cost Estimation**: Calculate trading fees and total value
- **Recommendations**: Specific BUY/SELL suggestions per asset
- **Integration**: Seamless portfolio handler integration

#### Smart Alerts 🔔
- **SmartAlertsService** (310 lines): ML-based alert engine
- **High Volatility Detection**: Statistical anomaly detection (2σ threshold)
- **Momentum Shifts**: Bullish/bearish crossover detection
- **Volume Spike Detection**: Unusual trading activity alerts
- **Short-term Predictions**: 2-6 hour movement forecasts
- **Confidence Scores**: Reliability indicators for all predictions
- **Multi-factor Analysis**: Voting system across indicators

### ✨ Enhancements

#### User Interface
- 2 new main menu buttons: "Analytics" and "Trading Signals"
- Portfolio rebalancing menu with preset strategies
- Interactive asset selection for analytics
- Correlation analysis workflow (2-step selection)
- Signal confidence indicators with emojis
- Comprehensive alert messages

#### Technical Implementation
- 4 new services (~1,200 lines)
- 2 new handlers (~650 lines)
- 30+ callback handlers
- Async processing throughout
- Integration with existing portfolio system
- Numpy/Pandas for calculations

### 📊 Analytics Features
- Asset-specific analytics (stocks, crypto)
- 30-60 day historical analysis
- Multiple risk metrics in single view
- Export-ready data format

### 🎯 Trading Features
- 4 technical indicators
- Majority voting for overall signal
- Indicator-specific explanations
- Refresh capability
- Cross-reference with analytics

### 🔄 Rebalancing Features
- Target allocation management
- Real-time deviation tracking
- Trade value calculation
- Fee estimation (0.1% default)
- Strategy comparison

### 🔔 Alert Features
- Statistical anomaly detection
- Pattern recognition
- Multi-timeframe analysis
- Configurable thresholds
- Predictive analytics

### 🛠 Technical Details
- **Total Added**: ~1,850 lines of code
- **Services**: AnalyticsService, TradingSignalsService, RebalanceService, SmartAlertsService
- **Handlers**: AnalyticsHandler, TradingHandler (rebalancing in PortfolioHandler)
- **Dependencies**: Existing numpy, pandas, matplotlib
- **Architecture**: Modular, async, cached

---

## [2.6.0] - 2025-10-19

### 🎉 AI Assistant with Local LLM

**Llama 3.2 3B Integration:**
- Privacy-first local AI via Ollama
- Question answering about crypto/stocks/markets
- Market analysis with AI insights
- Portfolio analysis and recommendations
- Smart feature suggestions
- Fast responses from 3B parameter model

**Implementation:**
- AIService (340 lines) - Ollama API integration
- AIHandler (450 lines) - Bot UI and conversation flow
- Async processing with timeouts
- Context management for conversations
- Optional feature (graceful degradation)

**Setup:**
```bash
ollama pull llama3.2:3b
```

---

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.5.0] - 2025-10-19

### 🎉 Major Features

#### Web Dashboard 🌐
- **FastAPI Application**: Modern async web framework
- **Telegram Web App**: Native integration with Telegram
- **Authentication**: Secure verification via Telegram init data
- **Real-time Data**: Live crypto prices with auto-refresh
- **Portfolio View**: Interactive portfolio display
- **Analytics**: Conversion history and statistics
- **Responsive Design**: Mobile-first adaptive UI
- **Theme Support**: Telegram theme integration

### ✨ Enhancements

#### Web Application
- **FastAPI Backend** (280 lines): RESTful API with authentication
- **Dashboard UI** (350 lines): Modern HTML/CSS/JS interface
- **API Endpoints**: 10 REST endpoints for data access
- **Real-time Updates**: Auto-refresh every 30 seconds

#### Dashboard Features
- 📊 **Live Crypto Prices**: 10+ cryptocurrencies
- 💼 **Portfolio Management**: View all assets
- 📜 **Conversion History**: Last 100 conversions
- 📊 **Statistics**: Conversions, alerts, favorites count
- 🔔 **Alerts Display**: View active price alerts
- ⭐ **Favorites**: Quick access to favorite currencies

#### Bot Integration
- **DashboardHandler** (100 lines): Bot-side integration
- Dashboard button in main menu
- Telegram Web App button
- Feature descriptions
- Setup instructions

### 🔧 Technical Improvements
- FastAPI async architecture
- CORS middleware for cross-origin requests
- Jinja2 templating engine
- HMAC authentication verification
- Static file serving
- Health check endpoint
- Error handling and logging

### 📦 Dependencies
- Added `fastapi ^0.104` (optional)
- Added `uvicorn ^0.24` (optional)
- Added `jinja2 ^3.1` (optional)
- Added `python-multipart ^0.0.6` (optional)

**Install extras:**
- Web dashboard: `poetry install -E webapp`
- All features: `poetry install -E all`

**Running the dashboard:**
```bash
cd webapp
python main.py
# Or with uvicorn:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 📝 Documentation
- Dashboard setup guide
- API endpoint documentation
- Telegram Web App integration
- Authentication flow explanation

---

## [2.4.0] - 2025-10-19

### 🎉 Major Features

#### Voice Input Integration 🎤
- **Speech Recognition**: Automatic voice message transcription
- **Google Speech API**: Free speech-to-text using Google's service
- **Command Parsing**: Intelligent parsing of conversion commands
- **Multi-language**: Support for English and Russian voice commands
- **Natural Language**: Understands various command formats
- **Auto-Conversion**: Executes conversions directly from voice
- **Feedback**: Shows recognized text and conversion results

### ✨ Enhancements

#### Services
- **VoiceService** (280 lines): Speech recognition, audio processing, command parsing

#### Voice Message Handler
- Automatic voice message detection
- Audio format conversion (OGG to WAV)
- Real-time processing feedback
- Error handling for unclear audio
- Command pattern recognition

#### Supported Voice Commands
- "100 USD to EUR"
- "Convert 50 dollars to euros"
- "How much is 1000 rubles in dollars"
- "100 bitcoin" (defaults to USD)
- Natural language variations

### 🔧 Technical Improvements
- Optional dependencies for speech recognition
- Audio format conversion with pydub
- Regex-based command parsing
- Async voice processing
- Graceful degradation without libraries

### 📦 Dependencies
- Added `SpeechRecognition ^3.10` (optional)
- Added `pydub ^0.25` (optional)
- Requires `ffmpeg` for audio processing

**Install extras:**
- Voice input: `poetry install -E voice`
- All features: `poetry install -E all`

### 📝 Documentation
- Voice command examples
- Setup instructions for ffmpeg
- Troubleshooting guide

---

## [2.3.0] - 2025-10-19

### 🎉 Major Features

#### Google Sheets Integration 📊
- **OAuth2 Support**: Secure authorization flow for Google account access
- **Direct Export**: Export portfolio and history directly to Google Sheets
- **Auto-Creation**: Automatically creates new spreadsheets with formatted data
- **Live Links**: Get shareable links to your exported data
- **Update Support**: Update existing spreadsheets with new data

#### Notion Integration 📝
- **Database Creation**: Automatically creates Notion databases
- **Portfolio Export**: Export portfolio items with rich properties
- **History Export**: Export conversion history with full details
- **Custom Properties**: Configurable database schemas
- **API Integration**: Uses official Notion API client

### ✨ Enhancements

#### Services
- **GoogleSheetsService** (280 lines): OAuth, spreadsheet creation, data export
- **NotionService** (320 lines): Database creation, page management, data export

#### Export Menu
- New "Google Sheets" export option
- New "Notion" export option
- Authorization/setup instructions
- Availability checks for optional dependencies

### 🔧 Technical Improvements
- Optional dependencies for Google/Notion APIs
- Poetry extras for selective installation
- Graceful degradation when libraries not installed
- Enhanced export handler with new menu options
- Callback routing for Sheets/Notion flows

### 📦 Dependencies
- Added `google-auth ^2.23` (optional)
- Added `google-auth-oauthlib ^1.1` (optional)
- Added `google-api-python-client ^2.100` (optional)
- Added `notion-client ^2.2` (optional)

**Install extras:**
- Google Sheets: `poetry install -E sheets`
- Notion: `poetry install -E notion`
- All integrations: `poetry install -E all`

### 📝 Documentation
- Setup instructions for Google Sheets OAuth
- Setup instructions for Notion API
- Updated export documentation

---

## [2.2.0] - 2025-10-19

### 🎉 Major Features

#### Crypto News Notifications 📰
- **RSS Feed Integration**: Automatic news aggregation from 5 major sources (CoinDesk, Cointelegraph, CryptoSlate, Decrypt, Bitcoinist)
- **Smart Asset Detection**: Automatically identifies mentioned cryptocurrencies in news articles
- **Category Filtering**: News categorized into Hacks, Listings, Updates, Regulations, and General
- **Subscription Management**: Subscribe to specific assets and categories
- **Real-time Notifications**: Automatic news delivery every 15 minutes
- **Multi-language Support**: Full English and Russian localization

#### Analytics Reports 📊
- **Weekly Market Digest**: Automated weekly performance summaries
- **Portfolio Reports**: Detailed portfolio analysis with distribution charts
- **Performance Tracking**: Best/worst performers visualization
- **Report Subscriptions**: Schedule automated weekly or monthly reports
- **Visual Analytics**: Generated charts with performance metrics

#### Forecast Model Comparison 🎯
- **Prediction Tracking**: Automatic saving of all price forecasts
- **Accuracy Metrics**: MAE (Mean Absolute Error) and MAPE (Mean Absolute Percentage Error)
- **Model Comparison**: ARIMA vs Linear Regression performance stats
- **Auto-Validation**: Scheduled validation every 6 hours
- **Stats Display**: Model accuracy shown in Statistics menu
- **Historical Analysis**: 30-day rolling accuracy calculation

### ✨ Enhancements

#### Database
- Added `NewsSubscription` model with user preferences
- Added `ReportSubscription` model for automated reports
- Added `PredictionHistory` model for forecast tracking
- 6 new repository methods for news management
- 5 new repository methods for report subscriptions
- 6 new repository methods for prediction history

#### Services
- **NewsService** (273 lines): RSS parsing, filtering, caching
- **ReportService** (230 lines): Report generation, visualization
- **PredictionGenerator** (enhanced): Added prediction tracking and accuracy comparison

#### Handlers
- **NewsHandler** (300 lines): Complete news UI flow
- **ReportHandler** (200 lines): Report generation and subscription UI

#### UI/UX
- New "📰 News" button in main menu
- New "📊 Reports" button in main menu
- Interactive subscription management
- Category selection interface
- Report type selection

#### Localization
- 17 new English strings for news
- 17 new Russian strings for news
- 10 new English strings for reports
- 10 new Russian strings for reports

### 🔧 Technical Improvements
- APScheduler jobs: news checking (15 min), prediction validation (6 hours)
- RSS feed caching with TTL
- Async news fetching and delivery
- Prediction tracking on every forecast generation
- Automatic accuracy calculation (MAE/MAPE)
- Enhanced callback routing system
- Improved error handling and logging

### 📦 Dependencies
- Added `feedparser ^6.0` for RSS parsing

### 🐛 Bug Fixes
- None (new features)

### 📝 Documentation
- Updated `DEVELOPMENT_PLAN.md` with v2.2-v2.5 roadmap
- Updated `ROADMAP.md` with completed milestones
- Updated version to 2.2.0 in `pyproject.toml`

---

## [2.1.0] - 2025-10-19

### 🎉 Major Features

#### Portfolio Management System 💼
- Multi-asset portfolio tracking (crypto, stocks, fiat, CS2 items)
- Real-time portfolio valuation
- Profit/Loss tracking with purchase price
- Asset distribution analysis
- Interactive pie chart visualization
- Full CRUD operations (Add, View, Update, Delete)

#### Data Export Functionality 📤
- CSV export for portfolio, alerts, and history
- ZIP archive with complete user data backup
- Structured data format for Excel/Sheets analysis
- Privacy-first approach

#### Dark/Light Theme System 🎨
- Theme switching (Light/Dark/Auto)
- Visual consistency across all charts
- Settings menu integration
- Persistent theme preference
- Enhanced readability for day/night use

### ✨ Enhancements

#### Database
- New `PortfolioItem` model with full schema support
- `chart_theme` field added to User model
- Extended repository with portfolio methods

#### Services
- **PortfolioService** (350 lines): Portfolio management and valuation
- **ExportService** (200 lines): Data export to CSV/ZIP

#### Handlers
- **PortfolioHandler** (448 lines): Complete portfolio UI
- **ExportHandler** (200 lines): Export functionality UI

#### UI/UX
- New "💼 Portfolio" button in main menu
- New "📤 Export" button in main menu
- Theme selector in Settings
- Portfolio visualization with charts

#### Localization
- 40+ new English strings for portfolio
- 40+ new Russian strings for portfolio
- Theme-related strings

### 📝 Documentation
- Updated README.md to v2.1
- Updated PROJECT_STATUS.md
- Updated IMPLEMENTATION_SUMMARY.md

---

## [2.0.0] - 2025-01-15

### 🎉 Major Features

#### Stock Market Integration 📈
- **Global Stocks**: 20+ popular stocks (AAPL, TSLA, NVDA, etc.)
- **Russian Stocks**: 15+ MOEX stocks (SBER, GAZP, LKOH, etc.)
- **CBR Exchange Rates**: Official rates from Central Bank of Russia
- Real-time price data with charts
- 24-hour change tracking

#### CS2 Market Integration 🎮
- 30+ CS2 items across 6 categories
- Multi-marketplace comparison (Steam, Skinport)
- Price tracking and best deal identification
- Categories: Knives, Gloves, Rifles, Snipers, Pistols, SMGs

### ✨ Enhancements

#### Database Migration
- Migrated to SQLAlchemy ORM
- Persistent data storage
- User management system
- History tracking
- Favorites system

#### Services
- **StockService**: Yahoo Finance + MOEX integration
- **CS2MarketService**: Steam + Skinport APIs
- Enhanced caching system

#### Handlers
- **StocksHandler** (350 lines): Stock market UI
- **CS2Handler** (400 lines): CS2 market UI

#### UI/UX
- New "📈 Stocks" button
- New "🎮 CS2 Skins" button
- Interactive market selection
- Chart visualization for stocks

### 📝 Documentation
- Complete README.md rewrite
- Added ROADMAP.md
- Added DEVELOPMENT_PLAN.md

---

## [1.5.0] - 2024-12-20

### ✨ Enhancements
- SQLAlchemy migration
- Database schema improvements
- Code refactoring

---

## [1.0.0] - 2024-11-15

### 🎉 Initial Production Release

#### Core Features
- Currency conversion (60+ currencies)
- Cryptocurrency analysis (5+ exchanges)
- Historical charts (7/30/90/365 days)
- AI-powered price forecasting (ARIMA + Linear Regression)
- Price alerts system
- Calculator with currency support
- Inline query mode
- Multi-language support (EN/RU)

#### Architecture
- Modular service-based design
- Async/await throughout
- Professional error handling
- Comprehensive logging
- Docker support

---

## [0.5.0] - 2024-10-01

### 🧪 Beta Release
- Initial bot implementation
- Basic conversion features
- Testing phase

---

[2.2.0]: https://github.com/bobberdolle1/CoinFlow/releases/tag/v2.2.0
[2.1.0]: https://github.com/bobberdolle1/CoinFlow/releases/tag/v2.1.0
[2.0.0]: https://github.com/bobberdolle1/CoinFlow/releases/tag/v2.0.0
[1.5.0]: https://github.com/bobberdolle1/CoinFlow/releases/tag/v1.5.0
[1.0.0]: https://github.com/bobberdolle1/CoinFlow/releases/tag/v1.0.0
[0.5.0]: https://github.com/bobberdolle1/CoinFlow/releases/tag/v0.5.0
