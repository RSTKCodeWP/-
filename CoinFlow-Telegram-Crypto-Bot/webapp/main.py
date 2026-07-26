"""FastAPI web application for CoinFlow dashboard."""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import hmac
import hashlib
import json
from urllib.parse import parse_qs
from typing import Optional
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coinflow.database import DatabaseRepository
from coinflow.services import CurrencyConverter, PortfolioService
from coinflow.config import config

app = FastAPI(title="CoinFlow Dashboard", version="2.5.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Initialize services
db = DatabaseRepository(config.DATABASE_URL)
converter = CurrencyConverter()


def verify_telegram_auth(init_data: str, bot_token: str) -> dict:
    """
    Verify Telegram Web App authentication.
    
    Args:
        init_data: Init data from Telegram Web App
        bot_token: Bot token
    
    Returns:
        Parsed user data
    """
    try:
        # Parse init data
        parsed = parse_qs(init_data)
        
        # Extract hash
        received_hash = parsed.get('hash', [''])[0]
        
        # Remove hash from data
        data_check_string_parts = []
        for key in sorted(parsed.keys()):
            if key != 'hash':
                values = parsed[key]
                for value in values:
                    data_check_string_parts.append(f"{key}={value}")
        
        data_check_string = '\n'.join(data_check_string_parts)
        
        # Create secret key
        secret_key = hmac.new(
            "WebAppData".encode(),
            bot_token.encode(),
            hashlib.sha256
        ).digest()
        
        # Calculate hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Verify hash
        if calculated_hash != received_hash:
            raise ValueError("Invalid hash")
        
        # Parse user data
        user_data = json.loads(parsed.get('user', ['{}'])[0])
        
        return user_data
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


async def get_current_user(request: Request) -> Optional[int]:
    """Get current user from Telegram Web App data."""
    init_data = request.headers.get("X-Telegram-Init-Data")
    
    if not init_data:
        # Try from query params (for testing)
        init_data = request.query_params.get("_tgWebAppData")
    
    if not init_data:
        raise HTTPException(status_code=401, detail="No authentication data")
    
    try:
        user_data = verify_telegram_auth(init_data, config.BOT_TOKEN)
        return user_data.get('id')
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/user/info")
async def get_user_info(user_id: int = Depends(get_current_user)):
    """Get user information."""
    try:
        user = db.get_user(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": user.telegram_id,
            "language": user.lang,
            "theme": user.chart_theme,
            "created_at": user.created_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/user/stats")
async def get_user_stats(user_id: int = Depends(get_current_user)):
    """Get user statistics."""
    try:
        stats = db.get_user_stats(user_id)
        
        return {
            "total_conversions": stats['total_conversions'],
            "total_alerts": stats['total_alerts'],
            "favorites_count": stats['favorites_count']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio")
async def get_portfolio(user_id: int = Depends(get_current_user)):
    """Get user's portfolio."""
    try:
        portfolio_items = db.get_portfolio_items(user_id)
        
        result = []
        for item in portfolio_items:
            result.append({
                "id": item.id,
                "asset_type": item.asset_type,
                "asset_symbol": item.asset_symbol,
                "asset_name": item.asset_name,
                "quantity": float(item.quantity),
                "purchase_price": float(item.purchase_price) if item.purchase_price else None,
                "purchase_date": item.purchase_date.isoformat() if item.purchase_date else None,
                "notes": item.notes,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat()
            })
        
        return {"items": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
async def get_history(
    user_id: int = Depends(get_current_user),
    days: int = 30,
    limit: int = 100
):
    """Get conversion history."""
    try:
        history = db.get_user_history(user_id, days=days)
        
        # Limit results
        history = history[:limit]
        
        result = []
        for item in history:
            result.append({
                "from_currency": item.from_currency,
                "to_currency": item.to_currency,
                "amount": float(item.amount),
                "result": float(item.result),
                "rate": float(item.rate),
                "created_at": item.created_at.isoformat()
            })
        
        return {"history": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts")
async def get_alerts(user_id: int = Depends(get_current_user)):
    """Get user's alerts."""
    try:
        alerts = db.get_user_alerts(user_id)
        
        result = []
        for alert in alerts:
            result.append({
                "id": alert.id,
                "currency_pair": alert.currency_pair,
                "target_rate": float(alert.target_rate),
                "condition": alert.condition,
                "enabled": alert.enabled,
                "created_at": alert.created_at.isoformat()
            })
        
        return {"alerts": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/favorites")
async def get_favorites(user_id: int = Depends(get_current_user)):
    """Get user's favorite currencies."""
    try:
        favorites = db.get_user_favorites(user_id)
        
        result = [fav.currency for fav in favorites]
        
        return {"favorites": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/crypto/prices")
async def get_crypto_prices():
    """Get current crypto prices."""
    try:
        cryptos = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'MATIC', 'LTC']
        
        prices = {}
        for crypto in cryptos:
            try:
                price = converter.get_crypto_rate_aggregated(crypto, 'USDT')
                if price and price > 0:
                    prices[crypto] = round(price, 2)
            except:
                pass
        
        return {"prices": prices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.5.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
