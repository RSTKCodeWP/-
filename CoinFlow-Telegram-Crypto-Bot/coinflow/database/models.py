"""Database models for CoinFlow bot."""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class User(Base):
    """User model for storing user preferences and settings."""
    
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    lang = Column(String(5), default='en')
    prediction_model = Column(String(20), default='arima')
    rub_source = Column(String(20), default='aggregator')
    chart_theme = Column(String(10), default='light')  # 'light', 'dark', 'auto'
    providers = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, lang={self.lang})>"


class Alert(Base):
    """Alert model for price notifications."""
    
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    pair = Column(String(20), nullable=False)
    condition = Column(String(10), nullable=False)  # 'above' or 'below'
    target = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Alert(pair={self.pair}, condition={self.condition}, target={self.target})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'pair': self.pair,
            'condition': self.condition,
            'target': self.target,
            'created': self.created_at.isoformat()
        }


class ConversionHistory(Base):
    """Conversion history model for tracking user conversions."""
    
    __tablename__ = 'conversion_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    from_currency = Column(String(10), nullable=False)
    to_currency = Column(String(10), nullable=False)
    amount = Column(Float, nullable=False)
    result = Column(Float, nullable=False)
    rate = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<ConversionHistory({self.amount} {self.from_currency} -> {self.result} {self.to_currency})>"


class Favorite(Base):
    """Favorite currencies model."""
    
    __tablename__ = 'favorites'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    currency = Column(String(10), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Favorite(user_id={self.user_id}, currency={self.currency})>"


class PortfolioItem(Base):
    """Portfolio item model for tracking user assets."""
    
    __tablename__ = 'portfolio_items'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    asset_type = Column(String(20), nullable=False)  # 'crypto', 'stock', 'fiat', 'cs2'
    asset_symbol = Column(String(20), nullable=False)  # e.g., 'BTC', 'AAPL', 'USD', 'knife_karambit_doppler'
    asset_name = Column(String(100), nullable=False)  # Full name for display
    quantity = Column(Float, nullable=False)
    purchase_price = Column(Float, nullable=True)  # Optional: price when purchased (in USD)
    purchase_date = Column(DateTime, nullable=True)  # Optional: when purchased
    notes = Column(String(500), nullable=True)  # Optional user notes
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<PortfolioItem(user_id={self.user_id}, asset={self.asset_symbol}, qty={self.quantity})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'asset_type': self.asset_type,
            'asset_symbol': self.asset_symbol,
            'asset_name': self.asset_name,
            'quantity': self.quantity,
            'purchase_price': self.purchase_price,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Announcement(Base):
    """Announcement model for admin broadcasts."""
    
    __tablename__ = 'announcements'
    
    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, nullable=False)
    text = Column(String, nullable=False)
    media_type = Column(String, nullable=True)  # 'photo', 'video', 'document', None
    media_file_id = Column(String, nullable=True)  # Telegram file_id
    sent_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Announcement(id={self.id}, admin={self.admin_id}, sent={self.sent_count})>"


class NewsSubscription(Base):
    """News subscription model for crypto news alerts."""
    
    __tablename__ = 'news_subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    asset_symbol = Column(String(10), nullable=False)  # BTC, ETH, etc.
    categories = Column(JSON, default=[])  # ['hack', 'listing', 'update', 'regulation'] or [] for all
    frequency = Column(String(20), default='realtime')  # 'realtime', 'hourly', 'daily'
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_notified = Column(DateTime, nullable=True)
    
    # Relationship
    user = relationship('User', backref='news_subscriptions')
    
    def __repr__(self):
        return f"<NewsSubscription(user_id={self.user_id}, asset={self.asset_symbol}, freq={self.frequency})>"


class ReportSubscription(Base):
    """Report subscription model for automated reports."""
    
    __tablename__ = 'report_subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    report_type = Column(String(20), default='weekly')  # 'weekly', 'monthly'
    frequency = Column(String(20), default='weekly')  # 'weekly', 'monthly'
    delivery_day = Column(Integer, default=1)  # 1-7 for weekly, 1-31 for monthly
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_sent = Column(DateTime, nullable=True)
    
    # Relationship
    user = relationship('User', backref='report_subscriptions')
    
    def __repr__(self):
        return f"<ReportSubscription(user_id={self.user_id}, type={self.report_type}, freq={self.frequency})>"


class PredictionHistory(Base):
    """Prediction history model for tracking forecast accuracy."""
    
    __tablename__ = 'prediction_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    asset_symbol = Column(String(10), nullable=False)  # BTC, ETH, etc.
    model_type = Column(String(20), nullable=False)  # 'arima', 'linreg'
    predicted_price = Column(Float, nullable=False)
    actual_price = Column(Float, nullable=True)  # Filled later when actual price is known
    prediction_date = Column(DateTime, default=datetime.utcnow)
    target_date = Column(DateTime, nullable=False)  # Date for which prediction was made
    mae = Column(Float, nullable=True)  # Mean Absolute Error
    mape = Column(Float, nullable=True)  # Mean Absolute Percentage Error
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship('User', backref='predictions')
    
    def __repr__(self):
        return f"<PredictionHistory(user_id={self.user_id}, asset={self.asset_symbol}, model={self.model_type})>"
