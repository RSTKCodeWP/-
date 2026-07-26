"""
Property-based tests for Game State Serialization.

Tests correctness properties defined in the design document.
**Feature: grand-casino-dictator, Property 21: Game State Serialization Round-Trip**
**Validates: Requirements 16.3**
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings

# Import state_manager module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'state_manager.py')
_spec = importlib.util.spec_from_file_location("state_manager", _module_path)
_state_manager_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_state_manager_module)

SerializableGameState = _state_manager_module.SerializableGameState
GAME_TYPES = _state_manager_module.GAME_TYPES


# Strategies for generating test data
user_id_strategy = st.integers(min_value=1, max_value=10**12)
chat_id_strategy = st.integers(min_value=-10**12, max_value=10**12)
message_id_strategy = st.integers(min_value=1, max_value=10**9)
game_type_strategy = st.sampled_from(list(GAME_TYPES))

# Strategy for ISO format datetime strings
iso_datetime_strategy = st.datetimes().map(lambda dt: dt.isoformat())

# Strategy for game data - supports nested structures typical in games
json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-10**9, max_value=10**9),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=100)
)

# Recursive strategy for nested JSON-compatible data
game_data_strategy = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=10),
        st.dictionaries(
            st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N', 'Pd'))),
            children,
            max_size=10
        )
    ),
    max_leaves=50
)


class TestGameStateSerializationRoundTrip:
    """
    **Feature: grand-casino-dictator, Property 21: Game State Serialization Round-Trip**
    **Validates: Requirements 16.3**
    
    *For any* valid game state object, serializing to JSON and deserializing back 
    produces an equivalent game state object.
    """
    
    @settings(max_examples=100)
    @given(
        game_type=game_type_strategy,
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        message_id=message_id_strategy,
        data=game_data_strategy,
        created_at=iso_datetime_strategy
    )
    def test_json_round_trip_preserves_state(
        self,
        game_type: str,
        user_id: int,
        chat_id: int,
        message_id: int,
        data: dict,
        created_at: str
    ):
        """
        Property 21: Serialization round-trip produces equivalent object.
        
        For any valid SerializableGameState:
        - to_json() produces valid JSON
        - from_json(to_json(state)) == state
        """
        # Create original state
        original = SerializableGameState(
            game_type=game_type,
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            data=data if isinstance(data, dict) else {"value": data},
            created_at=created_at
        )
        
        # Serialize to JSON
        json_str = original.to_json()
        
        # Deserialize back
        restored = SerializableGameState.from_json(json_str)
        
        # Verify equality
        assert restored == original, (
            f"Round-trip failed:\n"
            f"Original: {original}\n"
            f"Restored: {restored}"
        )
    
    @settings(max_examples=100)
    @given(
        game_type=game_type_strategy,
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        message_id=message_id_strategy,
        data=game_data_strategy,
        created_at=iso_datetime_strategy
    )
    def test_dict_round_trip_preserves_state(
        self,
        game_type: str,
        user_id: int,
        chat_id: int,
        message_id: int,
        data: dict,
        created_at: str
    ):
        """
        Property 21b: Dictionary round-trip produces equivalent object.
        
        For any valid SerializableGameState:
        - to_dict() produces valid dict
        - from_dict(to_dict(state)) == state
        """
        # Create original state
        original = SerializableGameState(
            game_type=game_type,
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            data=data if isinstance(data, dict) else {"value": data},
            created_at=created_at
        )
        
        # Convert to dict
        state_dict = original.to_dict()
        
        # Restore from dict
        restored = SerializableGameState.from_dict(state_dict)
        
        # Verify equality
        assert restored == original, (
            f"Dict round-trip failed:\n"
            f"Original: {original}\n"
            f"Restored: {restored}"
        )
    
    @settings(max_examples=100)
    @given(
        game_type=game_type_strategy,
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        message_id=message_id_strategy,
        created_at=iso_datetime_strategy
    )
    def test_blackjack_state_round_trip(
        self,
        game_type: str,
        user_id: int,
        chat_id: int,
        message_id: int,
        created_at: str
    ):
        """
        Property 21c: Blackjack-specific state round-trips correctly.
        
        Tests with realistic blackjack game data structure.
        """
        # Realistic blackjack state
        blackjack_data = {
            "player_hand": [
                {"suit": "♠", "rank": "A"},
                {"suit": "♥", "rank": "K"}
            ],
            "dealer_hand": [
                {"suit": "♦", "rank": "7"},
                {"suit": "♣", "rank": "?"}  # Face down
            ],
            "bet": 100,
            "status": "playing"
        }
        
        original = SerializableGameState(
            game_type="blackjack",
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            data=blackjack_data,
            created_at=created_at
        )
        
        # Round-trip
        json_str = original.to_json()
        restored = SerializableGameState.from_json(json_str)
        
        assert restored == original
        assert restored.data["player_hand"] == blackjack_data["player_hand"]
        assert restored.data["bet"] == 100
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        message_id=message_id_strategy,
        created_at=iso_datetime_strategy,
        player1_hp=st.integers(min_value=0, max_value=100),
        player2_hp=st.integers(min_value=0, max_value=100)
    )
    def test_duel_state_round_trip(
        self,
        user_id: int,
        chat_id: int,
        message_id: int,
        created_at: str,
        player1_hp: int,
        player2_hp: int
    ):
        """
        Property 21d: Duel-specific state round-trips correctly.
        
        Tests with realistic duel game data structure.
        """
        # Realistic duel state
        duel_data = {
            "player1_id": user_id,
            "player2_id": 0,  # Oleg (PvE)
            "player1_hp": player1_hp,
            "player2_hp": player2_hp,
            "current_turn": 1,
            "bet": 50
        }
        
        original = SerializableGameState(
            game_type="duel",
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            data=duel_data,
            created_at=created_at
        )
        
        # Round-trip
        json_str = original.to_json()
        restored = SerializableGameState.from_json(json_str)
        
        assert restored == original
        assert restored.data["player1_hp"] == player1_hp
        assert restored.data["player2_hp"] == player2_hp
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        message_id=message_id_strategy,
        created_at=iso_datetime_strategy,
        chamber=st.integers(min_value=1, max_value=6),
        bullet_position=st.integers(min_value=1, max_value=6)
    )
    def test_roulette_state_round_trip(
        self,
        user_id: int,
        chat_id: int,
        message_id: int,
        created_at: str,
        chamber: int,
        bullet_position: int
    ):
        """
        Property 21e: Roulette-specific state round-trips correctly.
        
        Tests with realistic Russian roulette game data structure.
        """
        # Realistic roulette state
        roulette_data = {
            "chamber": chamber,
            "bullet_position": bullet_position,
            "bet": 100,
            "phase": "spinning"
        }
        
        original = SerializableGameState(
            game_type="roulette",
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            data=roulette_data,
            created_at=created_at
        )
        
        # Round-trip
        json_str = original.to_json()
        restored = SerializableGameState.from_json(json_str)
        
        assert restored == original
        assert restored.data["chamber"] == chamber
        assert restored.data["bullet_position"] == bullet_position
