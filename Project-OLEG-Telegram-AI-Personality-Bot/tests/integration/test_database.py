"""Integration tests for database operations."""

import pytest
from sqlalchemy import select
from app.database.session import get_session
from app.database.models import User, GameStat
from app.utils import utc_now


@pytest.mark.asyncio
async def test_create_user():
    """Test creating a user in database."""
    async_session = get_session()
    
    async with async_session() as session:
        # Create user
        user = User(
            tg_user_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User",
            created_at=utc_now(),
            status="active"
        )
        session.add(user)
        await session.commit()
        
        # Query user
        result = await session.execute(
            select(User).where(User.tg_user_id == 123456789)
        )
        fetched_user = result.scalar_one_or_none()
        
        assert fetched_user is not None
        assert fetched_user.username == "testuser"
        assert fetched_user.first_name == "Test"
        
        # Cleanup
        await session.delete(fetched_user)
        await session.commit()


@pytest.mark.asyncio
async def test_user_game_relationship():
    """Test relationship between User and GameStat."""
    async_session = get_session()
    
    async with async_session() as session:
        # Create user
        user = User(
            tg_user_id=987654321,
            username="gamer",
            created_at=utc_now()
        )
        session.add(user)
        await session.flush()
        
        # Create game stats
        game_stat = GameStat(
            user_id=user.id,
            tg_user_id=user.tg_user_id,
            username=user.username,
            size_cm=15,
            pvp_wins=5
        )
        session.add(game_stat)
        await session.commit()
        
        # Query with relationship
        result = await session.execute(
            select(User).where(User.tg_user_id == 987654321)
        )
        fetched_user = result.scalar_one_or_none()
        
        assert fetched_user is not None
        assert fetched_user.game is not None
        assert fetched_user.game.size_cm == 15
        assert fetched_user.game.pvp_wins == 5
        
        # Cleanup
        await session.delete(game_stat)
        await session.delete(fetched_user)
        await session.commit()
