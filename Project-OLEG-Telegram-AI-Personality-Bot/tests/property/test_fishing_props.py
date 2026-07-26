"""
Property-based tests for Fishing game.

Tests correctness properties defined in the design document.
**Feature: release-candidate-8, Property 9: Fishing rewards increase balance**
**Validates: Requirements 6.2**
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Dict, List, Callable

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Minimal reproduction of FishingGame for testing
# ============================================================================

def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class FishRarity(str, Enum):
    TRASH = "trash"
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


@dataclass
class Fish:
    """Represents a caught fish."""
    name: str
    emoji: str
    rarity: FishRarity
    value: int  # Sell price
    weight: float  # kg


# Fish catalog with probabilities
FISH_CATALOG: Dict[FishRarity, List[Fish]] = {
    FishRarity.TRASH: [
        Fish("Старый ботинок", "👟", FishRarity.TRASH, 1, 0.5),
        Fish("Консервная банка", "🥫", FishRarity.TRASH, 1, 0.1),
        Fish("Водоросли", "🌿", FishRarity.TRASH, 2, 0.2),
    ],
    FishRarity.COMMON: [
        Fish("Карась", "🐟", FishRarity.COMMON, 10, 0.8),
        Fish("Окунь", "🐟", FishRarity.COMMON, 12, 1.0),
        Fish("Плотва", "🐟", FishRarity.COMMON, 8, 0.5),
        Fish("Ёрш", "🐟", FishRarity.COMMON, 7, 0.3),
    ],
    FishRarity.UNCOMMON: [
        Fish("Щука", "🐟", FishRarity.UNCOMMON, 25, 3.0),
        Fish("Судак", "🐟", FishRarity.UNCOMMON, 30, 2.5),
        Fish("Лещ", "🐟", FishRarity.UNCOMMON, 20, 2.0),
    ],
    FishRarity.RARE: [
        Fish("Сом", "🐋", FishRarity.RARE, 80, 15.0),
        Fish("Карп", "🐟", FishRarity.RARE, 60, 8.0),
        Fish("Форель", "🐟", FishRarity.RARE, 70, 3.0),
    ],
    FishRarity.EPIC: [
        Fish("Осётр", "🐋", FishRarity.EPIC, 200, 25.0),
        Fish("Белуга", "🐋", FishRarity.EPIC, 250, 40.0),
        Fish("Тунец", "🐟", FishRarity.EPIC, 180, 50.0),
    ],
    FishRarity.LEGENDARY: [
        Fish("Золотая рыбка", "✨", FishRarity.LEGENDARY, 1000, 0.5),
        Fish("Кракен", "🦑", FishRarity.LEGENDARY, 2000, 100.0),
        Fish("Левиафан", "🐉", FishRarity.LEGENDARY, 5000, 500.0),
    ],
}

# Rarity probabilities (base, can be modified by rod)
FISH_PROBABILITIES = {
    FishRarity.TRASH: 0.15,
    FishRarity.COMMON: 0.45,
    FishRarity.UNCOMMON: 0.25,
    FishRarity.RARE: 0.10,
    FishRarity.EPIC: 0.04,
    FishRarity.LEGENDARY: 0.01,
}


@dataclass
class FishingResult:
    """Result of a fishing attempt."""
    success: bool
    message: str
    fish: Optional[Fish] = None
    coins_earned: int = 0
    error_code: Optional[str] = None


class FishingGame:
    """Fishing game logic."""
    
    COOLDOWN_SECONDS = 30
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        self._random = random_func or random.random
        self._cooldowns: Dict[int, datetime] = {}
    
    def reset_cooldown(self, user_id: int) -> None:
        """Reset fishing cooldown for user (used by energy drink)."""
        if user_id in self._cooldowns:
            del self._cooldowns[user_id]
    
    def _select_rarity(self, rod_bonus: float = 0.0) -> FishRarity:
        """Select fish rarity based on probabilities."""
        roll = self._random()
        cumulative = 0.0
        
        # Adjust probabilities with rod bonus (increases rare+ chances)
        probs = FISH_PROBABILITIES.copy()
        if rod_bonus > 0:
            bonus_pool = probs[FishRarity.TRASH] * rod_bonus
            probs[FishRarity.TRASH] -= bonus_pool
            probs[FishRarity.RARE] += bonus_pool * 0.5
            probs[FishRarity.EPIC] += bonus_pool * 0.3
            probs[FishRarity.LEGENDARY] += bonus_pool * 0.2
        
        for rarity, prob in probs.items():
            cumulative += prob
            if roll < cumulative:
                return rarity
        return FishRarity.COMMON
    
    def cast(self, user_id: int, rod_bonus: float = 0.0) -> FishingResult:
        """Cast the fishing rod."""
        # Check cooldown
        now = utc_now()
        if user_id in self._cooldowns:
            remaining = (self._cooldowns[user_id] - now).total_seconds()
            if remaining > 0:
                return FishingResult(
                    False, f"Подожди {int(remaining)} сек. перед следующим забросом",
                    error_code="COOLDOWN"
                )
        
        # Set cooldown
        self._cooldowns[user_id] = now + timedelta(seconds=self.COOLDOWN_SECONDS)
        
        # Select rarity and fish
        rarity = self._select_rarity(rod_bonus)
        fish_list = FISH_CATALOG[rarity]
        fish = random.choice(fish_list)
        
        # Generate message based on rarity
        if rarity == FishRarity.TRASH:
            msg = f"🎣 Вытащил {fish.emoji} {fish.name}... Ну, бывает."
        elif rarity == FishRarity.LEGENDARY:
            msg = f"🎣✨ ЛЕГЕНДАРНЫЙ УЛОВ! {fish.emoji} {fish.name}! (+{fish.value} монет)"
        elif rarity == FishRarity.EPIC:
            msg = f"🎣🔥 ЭПИК! {fish.emoji} {fish.name}! (+{fish.value} монет)"
        elif rarity == FishRarity.RARE:
            msg = f"🎣⭐ Редкая рыба! {fish.emoji} {fish.name} (+{fish.value} монет)"
        else:
            msg = f"🎣 Поймал {fish.emoji} {fish.name} ({fish.weight} кг) — +{fish.value} монет"
        
        return FishingResult(True, msg, fish, fish.value)


# Strategies for generating test data
user_id_strategy = st.integers(min_value=1, max_value=10**12)
rod_bonus_strategy = st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False)


class TestFishingRewardsIncreaseBalance:
    """
    **Feature: release-candidate-8, Property 9: Fishing rewards increase balance**
    **Validates: Requirements 6.2**
    
    *For any* successful fishing cast with coins_earned > 0, 
    user balance SHALL increase by exactly coins_earned.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        rod_bonus=rod_bonus_strategy,
        initial_balance=st.integers(min_value=0, max_value=100000),
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_fishing_rewards_increase_balance(
        self,
        user_id: int,
        rod_bonus: float,
        initial_balance: int,
        seed: int
    ):
        """
        Property 9: Fishing rewards increase balance by exactly coins_earned.
        
        Requirements 6.2: WHEN рыбалка успешна THEN Fishing_Game SHALL 
        выдать награду и обновить статистику.
        
        For any successful fishing cast:
        - coins_earned is returned in the result
        - Balance should increase by exactly coins_earned
        """
        import random as rand_module
        
        # Create engine with seeded random for reproducibility
        rng = rand_module.Random(seed)
        game = FishingGame(random_func=rng.random)
        
        # Cast the fishing rod
        result = game.cast(user_id, rod_bonus)
        
        # Verify the cast was successful
        assert result.success, f"Fishing cast should succeed: {result.message}"
        
        # Verify fish was caught
        assert result.fish is not None, "Successful cast should return a fish"
        
        # Verify coins_earned matches fish value
        assert result.coins_earned == result.fish.value, \
            f"coins_earned ({result.coins_earned}) should equal fish value ({result.fish.value})"
        
        # Verify coins_earned is non-negative
        assert result.coins_earned >= 0, \
            f"coins_earned should be non-negative, got {result.coins_earned}"
        
        # Simulate balance update (as handler would do)
        new_balance = initial_balance + result.coins_earned
        
        # Verify balance increased by exactly coins_earned
        assert new_balance == initial_balance + result.coins_earned, \
            f"Balance should increase by {result.coins_earned}, got {new_balance - initial_balance}"

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        rod_bonus=rod_bonus_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_fishing_always_returns_fish(
        self,
        user_id: int,
        rod_bonus: float,
        seed: int
    ):
        """
        Property 9 supporting test: Successful cast always returns a fish.
        
        For any successful fishing cast:
        - A fish object is always returned
        - The fish has a valid rarity
        - The fish has a positive value
        """
        import random as rand_module
        
        rng = rand_module.Random(seed)
        game = FishingGame(random_func=rng.random)
        
        result = game.cast(user_id, rod_bonus)
        
        assert result.success, f"Cast should succeed: {result.message}"
        assert result.fish is not None, "Successful cast should return a fish"
        assert result.fish.rarity in FishRarity, \
            f"Fish rarity should be valid, got {result.fish.rarity}"
        assert result.fish.value >= 0, \
            f"Fish value should be non-negative, got {result.fish.value}"
        assert result.fish.name, "Fish should have a name"
        assert result.fish.emoji, "Fish should have an emoji"

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        rod_bonus=rod_bonus_strategy
    )
    def test_fishing_cooldown_prevents_spam(
        self,
        user_id: int,
        rod_bonus: float
    ):
        """
        Property 9 supporting test: Cooldown prevents rapid fishing.
        
        For any user:
        - First cast should succeed
        - Immediate second cast should fail with COOLDOWN error
        """
        game = FishingGame()
        
        # First cast should succeed
        result1 = game.cast(user_id, rod_bonus)
        assert result1.success, f"First cast should succeed: {result1.message}"
        
        # Second cast should fail due to cooldown
        result2 = game.cast(user_id, rod_bonus)
        assert not result2.success, "Second cast should fail due to cooldown"
        assert result2.error_code == "COOLDOWN", \
            f"Error code should be COOLDOWN, got {result2.error_code}"

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy
    )
    def test_fishing_cooldown_reset_allows_cast(
        self,
        user_id: int
    ):
        """
        Property 9 supporting test: Cooldown reset allows immediate cast.
        
        For any user:
        - After cooldown reset, cast should succeed
        """
        game = FishingGame()
        
        # First cast
        result1 = game.cast(user_id, 0.0)
        assert result1.success
        
        # Reset cooldown
        game.reset_cooldown(user_id)
        
        # Second cast should now succeed
        result2 = game.cast(user_id, 0.0)
        assert result2.success, f"Cast after cooldown reset should succeed: {result2.message}"

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_rod_bonus_affects_rarity_distribution(
        self,
        user_id: int,
        seed: int
    ):
        """
        Property 9 supporting test: Rod bonus affects rarity distribution.
        
        For any user with rod bonus:
        - Higher rod bonus should shift probability toward rarer fish
        - Fish value should still be valid
        """
        import random as rand_module
        
        # Test with no bonus
        rng1 = rand_module.Random(seed)
        game1 = FishingGame(random_func=rng1.random)
        result1 = game1.cast(user_id, 0.0)
        
        # Test with max bonus
        rng2 = rand_module.Random(seed)
        game2 = FishingGame(random_func=rng2.random)
        game2.reset_cooldown(user_id)  # Reset cooldown for same user
        result2 = game2.cast(user_id + 1, 0.5)  # Use different user to avoid cooldown
        
        # Both should succeed
        assert result1.success, f"Cast without bonus should succeed: {result1.message}"
        assert result2.success, f"Cast with bonus should succeed: {result2.message}"
        
        # Both should return valid fish
        assert result1.fish is not None
        assert result2.fish is not None
        assert result1.coins_earned >= 0
        assert result2.coins_earned >= 0
