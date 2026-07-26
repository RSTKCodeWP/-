"""
Property-based tests for AntiClickMiddleware.

Tests correctness properties defined in the design document.
**Feature: grand-casino-dictator, Property 2: Anti-Click Owner Verification**
**Validates: Requirements 3.1, 3.3, 3.4**
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock, MagicMock, patch

# Import anti_click module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'middleware', 'anti_click.py')
_spec = importlib.util.spec_from_file_location("anti_click", _module_path)
_anti_click_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_anti_click_module)

AntiClickMiddleware = _anti_click_module.AntiClickMiddleware
verify_owner = _anti_click_module.verify_owner


# Strategies for generating test data
user_id_strategy = st.integers(min_value=1, max_value=10**12)
game_prefix_strategy = st.sampled_from(["game:", "bj:", "duel:", "roulette:", "coinflip:", "grow:"])
action_strategy = st.sampled_from(["hit", "stand", "double", "attack", "defend", "spin"])


class TestAntiClickOwnerVerification:
    """
    **Feature: grand-casino-dictator, Property 2: Anti-Click Owner Verification**
    **Validates: Requirements 3.1, 3.3, 3.4**
    
    *For any* game button callback, game state changes occur if and only if 
    the callback sender's ID matches the game owner's ID stored in the session.
    """
    
    @settings(max_examples=100)
    @given(
        owner_id=user_id_strategy,
        prefix=game_prefix_strategy,
        action=action_strategy
    )
    def test_owner_click_is_allowed(
        self,
        owner_id: int,
        prefix: str,
        action: str
    ):
        """
        Property 2a: Owner clicking their own button is allowed.
        
        For any game callback where clicker_id == owner_id:
        - The handler should be called
        - No alert should be shown
        """
        import asyncio
        
        async def _test():
            middleware = AntiClickMiddleware()
            
            # Create mock callback with owner as clicker
            callback = MagicMock()
            callback.data = f"{prefix}{owner_id}:{action}"
            callback.from_user = MagicMock()
            callback.from_user.id = owner_id  # Same as owner
            callback.answer = AsyncMock()
            
            # Create mock handler
            handler = AsyncMock(return_value="handler_result")
            
            # Call middleware
            result = await middleware(handler, callback, {})
            
            # Handler should be called
            handler.assert_called_once_with(callback, {})
            
            # No alert should be shown
            callback.answer.assert_not_called()
            
            # Result should be from handler
            assert result == "handler_result"
        
        asyncio.get_event_loop().run_until_complete(_test())
    
    @settings(max_examples=100)
    @given(
        owner_id=user_id_strategy,
        clicker_id=user_id_strategy,
        prefix=game_prefix_strategy,
        action=action_strategy
    )
    def test_non_owner_click_is_blocked(
        self,
        owner_id: int,
        clicker_id: int,
        prefix: str,
        action: str
    ):
        """
        Property 2b: Non-owner clicking a game button is blocked.
        
        For any game callback where clicker_id != owner_id:
        - The handler should NOT be called
        - An alert should be shown
        - Result should be None
        """
        # Ensure different users
        assume(owner_id != clicker_id)
        
        import asyncio
        
        async def _test():
            middleware = AntiClickMiddleware()
            
            # Create mock callback with different clicker
            callback = MagicMock()
            callback.data = f"{prefix}{owner_id}:{action}"
            callback.from_user = MagicMock()
            callback.from_user.id = clicker_id  # Different from owner
            callback.answer = AsyncMock()
            
            # Create mock handler
            handler = AsyncMock(return_value="handler_result")
            
            # Call middleware
            result = await middleware(handler, callback, {})
            
            # Handler should NOT be called
            handler.assert_not_called()
            
            # Alert should be shown
            callback.answer.assert_called_once()
            call_args = callback.answer.call_args
            assert call_args[1].get('show_alert') is True, \
                "Alert should be shown with show_alert=True"
            
            # Result should be None (blocked)
            assert result is None
        
        asyncio.get_event_loop().run_until_complete(_test())
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        non_game_data=st.text(min_size=1, max_size=50).filter(
            lambda x: not any(x.startswith(p) for p in ["game:", "bj:", "duel:", "roulette:", "coinflip:", "grow:"])
        )
    )
    def test_non_game_callbacks_pass_through(
        self,
        user_id: int,
        non_game_data: str
    ):
        """
        Property 2c: Non-game callbacks are not affected by anti-click.
        
        For any callback that doesn't match game prefixes:
        - The handler should always be called
        - No ownership check is performed
        """
        import asyncio
        
        async def _test():
            middleware = AntiClickMiddleware()
            
            # Create mock callback with non-game data
            callback = MagicMock()
            callback.data = non_game_data
            callback.from_user = MagicMock()
            callback.from_user.id = user_id
            callback.answer = AsyncMock()
            
            # Create mock handler
            handler = AsyncMock(return_value="handler_result")
            
            # Call middleware
            result = await middleware(handler, callback, {})
            
            # Handler should be called
            handler.assert_called_once_with(callback, {})
            
            # No alert should be shown
            callback.answer.assert_not_called()
            
            # Result should be from handler
            assert result == "handler_result"
        
        asyncio.get_event_loop().run_until_complete(_test())
    
    @settings(max_examples=100)
    @given(
        owner_id=user_id_strategy,
        clicker_id=user_id_strategy
    )
    def test_verify_owner_function(
        self,
        owner_id: int,
        clicker_id: int
    ):
        """
        Property 2d: verify_owner utility returns correct result.
        
        For any owner_id and clicker_id:
        - Returns True if and only if they match
        """
        callback = MagicMock()
        callback.from_user = MagicMock()
        callback.from_user.id = clicker_id
        
        result = verify_owner(callback, owner_id)
        
        expected = (clicker_id == owner_id)
        assert result == expected, \
            f"verify_owner({clicker_id}, {owner_id}) should be {expected}, got {result}"
    
    @settings(max_examples=100)
    @given(
        owner_id=user_id_strategy,
        prefix=game_prefix_strategy
    )
    def test_owner_id_extraction(
        self,
        owner_id: int,
        prefix: str
    ):
        """
        Property 2e: Owner ID is correctly extracted from callback data.
        
        For any callback data in format prefix:owner_id:action:
        - The extracted owner_id matches the embedded one
        """
        middleware = AntiClickMiddleware()
        
        callback_data = f"{prefix}{owner_id}:action"
        extracted = middleware._extract_owner_id(callback_data)
        
        assert extracted == owner_id, \
            f"Extracted owner_id {extracted} should match {owner_id}"
    
    @settings(max_examples=100)
    @given(prefix=game_prefix_strategy)
    def test_game_callback_detection(self, prefix: str):
        """
        Property 2f: Game callbacks are correctly identified.
        
        For any known game prefix:
        - _is_game_callback returns True
        """
        middleware = AntiClickMiddleware()
        
        callback_data = f"{prefix}123:action"
        is_game = middleware._is_game_callback(callback_data)
        
        assert is_game is True, \
            f"Callback with prefix {prefix} should be detected as game callback"
    
    @settings(max_examples=100)
    @given(
        owner_id=user_id_strategy,
        clicker_id=user_id_strategy,
        prefix=game_prefix_strategy,
        action=action_strategy
    )
    def test_state_changes_iff_owner(
        self,
        owner_id: int,
        clicker_id: int,
        prefix: str,
        action: str
    ):
        """
        Property 2 (main): State changes occur iff clicker is owner.
        
        This is the core property: game state changes (handler called)
        if and only if the clicker is the owner.
        """
        import asyncio
        
        async def _test():
            middleware = AntiClickMiddleware()
            
            # Create mock callback
            callback = MagicMock()
            callback.data = f"{prefix}{owner_id}:{action}"
            callback.from_user = MagicMock()
            callback.from_user.id = clicker_id
            callback.answer = AsyncMock()
            
            # Track if handler was called (state change would occur)
            handler_called = False
            
            async def mock_handler(event, data):
                nonlocal handler_called
                handler_called = True
                return "result"
            
            # Call middleware
            await middleware(mock_handler, callback, {})
            
            # Core property: handler called iff clicker == owner
            is_owner = (clicker_id == owner_id)
            assert handler_called == is_owner, \
                f"Handler called: {handler_called}, is_owner: {is_owner}. " \
                f"State changes should occur iff clicker is owner."
        
        asyncio.get_event_loop().run_until_complete(_test())
