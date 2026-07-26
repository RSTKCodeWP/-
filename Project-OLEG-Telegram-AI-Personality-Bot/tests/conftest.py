"""Pytest configuration and fixtures."""

import pytest
import asyncio
from typing import AsyncGenerator

try:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.database.session import Base
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Base = None
    create_async_engine = None
    async_sessionmaker = None
    AsyncSession = None


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db() -> AsyncGenerator:
    """Create test database."""
    if not SQLALCHEMY_AVAILABLE:
        pytest.skip("SQLAlchemy not available")
        return
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    yield session_maker
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
def mock_telegram_user():
    """Mock Telegram user object."""
    class MockUser:
        id = 12345
        username = "testuser"
        first_name = "Test"
        last_name = "User"
        is_bot = False
    
    return MockUser()


@pytest.fixture
def mock_telegram_message(mock_telegram_user):
    """Mock Telegram message object."""
    class MockMessage:
        message_id = 1
        from_user = mock_telegram_user
        text = "Test message"
        
        class Chat:
            id = 67890
            type = "private"
        
        chat = Chat()
        
        async def reply(self, text, **kwargs):
            return text
        
        async def answer(self, text, **kwargs):
            return text
    
    return MockMessage()
