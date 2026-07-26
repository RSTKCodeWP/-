"""
Property-based tests for StateManager.

Tests correctness properties defined in the design document.
**Feature: grand-casino-dictator, Property 1: State Manager Game Lifecycle Invariant**
**Validates: Requirements 2.1, 2.2, 2.4**
"""

import os
import importlib.util
import asyncio
from hypothesis import given, strategies as st, settings, assume

# Import state_manager module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'state_manager.py')
_spec = importlib.util.spec_from_file_location("state_manager", _module_path)
_state_manager_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_state_manager_module)

GameSession = _state_manager_module.GameSession
StateManager = _state_manager_module.StateManager


# Strategies for generating test data
user_id_strategy = st.integers(min_value=1, max_value=10**12)
chat_id_strategy = st.integers(min_value=-10**12, max_value=10**12)
message_id_strategy = st.integers(min_value=1, max_value=10**9)
game_type_strategy = st.sampled_from(["blackjack", "duel", "roulette", "coinflip", "grow"])


def run_async(coro):
    """Helper to run async code in sync tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestStateManagerGameLifecycleInvariant:
    """
    **Feature: grand-casino-dictator, Property 1: State Manager Game Lifecycle Invariant**
    **Validates: Requirements 2.1, 2.2, 2.4**
    
    *For any* user and game, the user is registered as playing if and only if 
    they have an active game session that has not ended.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        message_id=message_id_strategy,
        game_type=game_type_strategy
    )
    def test_register_game_sets_playing_status(
        self,
        user_id: int,
        chat_id: int,
        message_id: int,
        game_type: str
    ):
        """
        Property 1a: After registering a game, user is marked as playing.
        
        For any valid user/chat/game combination:
        - Before registration: is_playing returns False
        - After registration: is_playing returns True
        """
        async def _test():
            manager = StateManager()
            
            # Before registration, user should not be playing
            assert not await manager.is_playing(user_id, chat_id), \
                "User should not be playing before registration"
            
            # Register game
            success = await manager.register_game(
                user_id=user_id,
                chat_id=chat_id,
                game_type=game_type,
                message_id=message_id
            )
            
            assert success, "Registration should succeed for new user"
            
            # After registration, user should be playing
            assert await manager.is_playing(user_id, chat_id), \
                "User should be playing after registration"
        
        run_async(_test())
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        message_id=message_id_strategy,
        game_type=game_type_strategy
    )
    def test_end_game_clears_playing_status(
        self,
        user_id: int,
        chat_id: int,
        message_id: int,
        game_type: str
    ):
        """
        Property 1b: After ending a game, user is no longer marked as playing.
        
        For any registered game:
        - After end_game: is_playing returns False
        - Session is removed
        """
        async def _test():
            manager = StateManager()
            
            # Register game first
            await manager.register_game(
                user_id=user_id,
                chat_id=chat_id,
                game_type=game_type,
                message_id=message_id
            )
            
            # Verify playing
            assert await manager.is_playing(user_id, chat_id)
            
            # End game
            ended = await manager.end_game(user_id, chat_id)
            assert ended, "end_game should return True for active session"
            
            # After ending, user should not be playing
            assert not await manager.is_playing(user_id, chat_id), \
                "User should not be playing after game ends"
            
            # Session should be None
            session = await manager.get_session(user_id, chat_id)
            assert session is None, "Session should be removed after game ends"
        
        run_async(_test())
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        message_id1=message_id_strategy,
        message_id2=message_id_strategy,
        game_type1=game_type_strategy,
        game_type2=game_type_strategy
    )
    def test_cannot_register_while_playing(
        self,
        user_id: int,
        chat_id: int,
        message_id1: int,
        message_id2: int,
        game_type1: str,
        game_type2: str
    ):
        """
        Property 1c: User cannot start a new game while already playing.
        
        For any user with an active game:
        - Attempting to register a second game returns False
        - Original session remains unchanged
        """
        async def _test():
            manager = StateManager()
            
            # Register first game
            success1 = await manager.register_game(
                user_id=user_id,
                chat_id=chat_id,
                game_type=game_type1,
                message_id=message_id1
            )
            assert success1, "First registration should succeed"
            
            # Get original session
            original_session = await manager.get_session(user_id, chat_id)
            
            # Try to register second game
            success2 = await manager.register_game(
                user_id=user_id,
                chat_id=chat_id,
                game_type=game_type2,
                message_id=message_id2
            )
            
            assert not success2, "Second registration should fail while playing"
            
            # Original session should be unchanged
            current_session = await manager.get_session(user_id, chat_id)
            assert current_session.game_type == original_session.game_type, \
                "Original game type should be preserved"
            assert current_session.message_id == original_session.message_id, \
                "Original message_id should be preserved"
        
        run_async(_test())
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        message_id=message_id_strategy,
        game_type=game_type_strategy
    )
    def test_session_exists_iff_playing(
        self,
        user_id: int,
        chat_id: int,
        message_id: int,
        game_type: str
    ):
        """
        Property 1d: Session exists if and only if user is playing.
        
        The invariant: is_playing(u, c) == (get_session(u, c) is not None)
        """
        async def _test():
            manager = StateManager()
            
            # Initially: not playing AND no session
            is_playing = await manager.is_playing(user_id, chat_id)
            session = await manager.get_session(user_id, chat_id)
            assert is_playing == (session is not None), \
                "Invariant violated: is_playing should match session existence (initial)"
            
            # After registration: playing AND session exists
            await manager.register_game(
                user_id=user_id,
                chat_id=chat_id,
                game_type=game_type,
                message_id=message_id
            )
            
            is_playing = await manager.is_playing(user_id, chat_id)
            session = await manager.get_session(user_id, chat_id)
            assert is_playing == (session is not None), \
                "Invariant violated: is_playing should match session existence (after register)"
            
            # After ending: not playing AND no session
            await manager.end_game(user_id, chat_id)
            
            is_playing = await manager.is_playing(user_id, chat_id)
            session = await manager.get_session(user_id, chat_id)
            assert is_playing == (session is not None), \
                "Invariant violated: is_playing should match session existence (after end)"
        
        run_async(_test())
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        message_id=message_id_strategy,
        game_type=game_type_strategy,
        state_key=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        state_value=st.integers(min_value=0, max_value=1000)
    )
    def test_update_state_preserves_session(
        self,
        user_id: int,
        chat_id: int,
        message_id: int,
        game_type: str,
        state_key: str,
        state_value: int
    ):
        """
        Property 1e: Updating state preserves session and playing status.
        
        For any active session:
        - update_state succeeds
        - is_playing remains True
        - Session still exists with updated state
        """
        async def _test():
            manager = StateManager()
            
            # Register game
            await manager.register_game(
                user_id=user_id,
                chat_id=chat_id,
                game_type=game_type,
                message_id=message_id
            )
            
            # Update state
            new_state = {state_key: state_value}
            success = await manager.update_state(user_id, chat_id, new_state)
            
            assert success, "update_state should succeed for active session"
            
            # Still playing
            assert await manager.is_playing(user_id, chat_id), \
                "User should still be playing after state update"
            
            # Session exists with updated state
            session = await manager.get_session(user_id, chat_id)
            assert session is not None, "Session should exist after state update"
            assert session.state.get(state_key) == state_value, \
                "State should be updated"
        
        run_async(_test())
