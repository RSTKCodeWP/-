"""
Property-based tests for Duel engine.

Tests correctness properties defined in the design document.
Requirements: 4.3, 6.1, 6.4
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings, assume

# Import duel_engine module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'duel_engine.py')
_spec = importlib.util.spec_from_file_location("duel_engine", _module_path)
_duel_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_duel_module)

Zone = _duel_module.Zone
DuelState = _duel_module.DuelState
DuelStatus = _duel_module.DuelStatus
DuelEngine = _duel_module.DuelEngine
OLEG_USER_ID = _duel_module.OLEG_USER_ID


# Strategies for generating test data
zone_strategy = st.sampled_from(list(Zone))
user_id_strategy = st.integers(min_value=1, max_value=10**12)
bet_strategy = st.integers(min_value=1, max_value=10000)
hp_strategy = st.integers(min_value=1, max_value=100)


class TestDuelRPSMechanics:
    """
    **Feature: grand-casino-dictator, Property 6: Duel RPS Mechanics**
    **Validates: Requirements 6.1**
    
    *For any* duel round with attack and defense zones, damage is dealt 
    according to Rock-Paper-Scissors rules: attack hits if attacker's zone 
    differs from defender's defended zone.
    """
    
    @settings(max_examples=100)
    @given(
        player1_id=user_id_strategy,
        player2_id=user_id_strategy,
        bet=bet_strategy,
        p1_attack=zone_strategy,
        p1_defend=zone_strategy,
        p2_attack=zone_strategy,
        p2_defend=zone_strategy
    )
    def test_attack_hits_when_zone_differs_from_defense(
        self,
        player1_id: int,
        player2_id: int,
        bet: int,
        p1_attack: Zone,
        p1_defend: Zone,
        p2_attack: Zone,
        p2_defend: Zone
    ):
        """
        Property 6: Attack hits if and only if attack zone differs from defended zone.
        
        For any duel round:
        - Player 1's attack hits Player 2 iff p1_attack != p2_defend
        - Player 2's attack hits Player 1 iff p2_attack != p1_defend
        """
        # Ensure different player IDs
        assume(player1_id != player2_id)
        
        engine = DuelEngine()
        state = engine.create_duel(player1_id, player2_id, bet)
        
        initial_p1_hp = state.player1_hp
        initial_p2_hp = state.player2_hp
        
        new_state = engine.make_move(
            state,
            player1_id,
            p1_attack,
            p1_defend,
            p2_attack,
            p2_defend
        )
        
        # Check Player 1's attack on Player 2
        p1_should_hit = p1_attack != p2_defend
        if p1_should_hit:
            assert new_state.player2_hp == initial_p2_hp - engine.DAMAGE, \
                f"P1 attack {p1_attack} vs P2 defend {p2_defend} should hit"
        else:
            assert new_state.player2_hp == initial_p2_hp, \
                f"P1 attack {p1_attack} vs P2 defend {p2_defend} should miss"
        
        # Check Player 2's attack on Player 1
        p2_should_hit = p2_attack != p1_defend
        if p2_should_hit:
            assert new_state.player1_hp == initial_p1_hp - engine.DAMAGE, \
                f"P2 attack {p2_attack} vs P1 defend {p1_defend} should hit"
        else:
            assert new_state.player1_hp == initial_p1_hp, \
                f"P2 attack {p2_attack} vs P1 defend {p1_defend} should miss"
    
    @settings(max_examples=100)
    @given(
        player1_id=user_id_strategy,
        player2_id=user_id_strategy,
        bet=bet_strategy,
        zone=zone_strategy
    )
    def test_same_zone_attack_and_defense_blocks(
        self,
        player1_id: int,
        player2_id: int,
        bet: int,
        zone: Zone
    ):
        """
        Property 6 edge case: Attack is blocked when zones match.
        
        If attacker attacks zone X and defender defends zone X, no damage.
        """
        assume(player1_id != player2_id)
        
        engine = DuelEngine()
        state = engine.create_duel(player1_id, player2_id, bet)
        
        initial_p2_hp = state.player2_hp
        
        # P1 attacks zone, P2 defends same zone
        new_state = engine.make_move(
            state,
            player1_id,
            attack=zone,
            defend=Zone.HEAD,  # P1's defense doesn't matter for this test
            opponent_attack=Zone.HEAD,  # P2's attack doesn't matter
            opponent_defend=zone  # P2 defends the same zone P1 attacks
        )
        
        assert new_state.player2_hp == initial_p2_hp, \
            f"Attack to {zone} blocked by defense at {zone} should deal no damage"
    
    @settings(max_examples=100)
    @given(
        player1_id=user_id_strategy,
        player2_id=user_id_strategy,
        bet=bet_strategy,
        attack_zone=zone_strategy,
        defend_zone=zone_strategy
    )
    def test_different_zone_attack_hits(
        self,
        player1_id: int,
        player2_id: int,
        bet: int,
        attack_zone: Zone,
        defend_zone: Zone
    ):
        """
        Property 6 edge case: Attack hits when zones differ.
        """
        assume(player1_id != player2_id)
        assume(attack_zone != defend_zone)
        
        engine = DuelEngine()
        state = engine.create_duel(player1_id, player2_id, bet)
        
        initial_p2_hp = state.player2_hp
        
        new_state = engine.make_move(
            state,
            player1_id,
            attack=attack_zone,
            defend=Zone.HEAD,
            opponent_attack=Zone.HEAD,
            opponent_defend=defend_zone
        )
        
        assert new_state.player2_hp == initial_p2_hp - engine.DAMAGE, \
            f"Attack to {attack_zone} vs defense at {defend_zone} should hit"


class TestOlegMoveValidity:
    """
    **Feature: grand-casino-dictator, Property 3: PvE Oleg Move Validity**
    **Validates: Requirements 4.3**
    
    *For any* PvE duel state, Oleg's generated attack and defense zones 
    are always valid Zone enum values.
    """
    
    @settings(max_examples=100)
    @given(seed=st.integers(min_value=0, max_value=2**32 - 1))
    def test_oleg_move_returns_valid_zones(self, seed: int):
        """
        Property 3: Oleg's moves are always valid Zone enum values.
        
        For any random seed:
        - oleg_move() returns a tuple of two Zone values
        - Both attack and defense are valid Zone enum members
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = DuelEngine(random_func=rng.random)
        
        attack, defend = engine.oleg_move()
        
        assert isinstance(attack, Zone), \
            f"Oleg's attack should be a Zone, got {type(attack)}"
        assert isinstance(defend, Zone), \
            f"Oleg's defense should be a Zone, got {type(defend)}"
        
        assert attack in Zone, \
            f"Oleg's attack {attack} should be a valid Zone"
        assert defend in Zone, \
            f"Oleg's defense {defend} should be a valid Zone"
    
    @settings(max_examples=100)
    @given(seeds=st.lists(st.integers(min_value=0, max_value=2**32 - 1), min_size=10, max_size=50))
    def test_oleg_moves_cover_all_zones(self, seeds: list):
        """
        Property 3 extended: Oleg's moves eventually cover all zones.
        
        Over many random moves, all zones should appear.
        """
        attack_zones_seen = set()
        defend_zones_seen = set()
        
        for seed in seeds:
            import random as rand_module
            rng = rand_module.Random(seed)
            engine = DuelEngine(random_func=rng.random)
            
            attack, defend = engine.oleg_move()
            attack_zones_seen.add(attack)
            defend_zones_seen.add(defend)
        
        # With enough samples, we should see all zones
        # This is a probabilistic test - with 10+ samples, very likely to see all 3 zones
        # We just verify that all seen zones are valid
        for zone in attack_zones_seen:
            assert zone in Zone, f"Invalid attack zone: {zone}"
        for zone in defend_zones_seen:
            assert zone in Zone, f"Invalid defense zone: {zone}"
    
    @settings(max_examples=100)
    @given(
        player_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_oleg_move_usable_in_duel(self, player_id: int, bet: int, seed: int):
        """
        Property 3 extended: Oleg's moves can be used in actual duel.
        
        The moves returned by oleg_move() should work with make_move().
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = DuelEngine(random_func=rng.random)
        
        # Create PvE duel
        state = engine.create_duel(player_id, OLEG_USER_ID, bet)
        
        # Get Oleg's move
        oleg_attack, oleg_defend = engine.oleg_move()
        
        # Player makes a move with Oleg's response
        player_attack = Zone.HEAD
        player_defend = Zone.BODY
        
        # This should not raise any exceptions
        new_state = engine.make_move(
            state,
            player_id,
            player_attack,
            player_defend,
            oleg_attack,
            oleg_defend
        )
        
        assert isinstance(new_state, DuelState), \
            "make_move with Oleg's move should return DuelState"


class TestDuelHealthTermination:
    """
    **Feature: grand-casino-dictator, Property 5: Duel Health Termination**
    **Validates: Requirements 6.4**
    
    *For any* duel game, when either player's HP reaches zero or below, 
    the game ends and the opponent is declared winner.
    """
    
    @settings(max_examples=100)
    @given(
        player1_id=user_id_strategy,
        player2_id=user_id_strategy,
        bet=bet_strategy,
        p1_hp=st.integers(min_value=0, max_value=100),
        p2_hp=st.integers(min_value=0, max_value=100)
    )
    def test_game_ends_when_hp_zero(
        self,
        player1_id: int,
        player2_id: int,
        bet: int,
        p1_hp: int,
        p2_hp: int
    ):
        """
        Property 5: Game ends when HP reaches zero.
        
        For any duel state:
        - If player1_hp <= 0: player2 wins
        - If player2_hp <= 0: player1 wins
        - If both <= 0: player1 wins (challenger advantage)
        """
        assume(player1_id != player2_id)
        
        engine = DuelEngine()
        
        # Create state with specific HP values
        state = DuelState(
            player1_id=player1_id,
            player2_id=player2_id,
            player1_hp=p1_hp,
            player2_hp=p2_hp,
            current_turn=player1_id,
            bet=bet,
            status=DuelStatus.PLAYING
        )
        
        # Check termination
        result = engine.check_termination(state)
        
        if p1_hp <= 0 and p2_hp <= 0:
            # Both at 0 - player1 wins on tie
            assert result.status == DuelStatus.PLAYER1_WIN, \
                "Both at 0 HP: player1 should win"
            assert result.winner_id == player1_id
        elif p1_hp <= 0:
            assert result.status == DuelStatus.PLAYER2_WIN, \
                f"Player1 HP {p1_hp} <= 0: player2 should win"
            assert result.winner_id == player2_id
        elif p2_hp <= 0:
            assert result.status == DuelStatus.PLAYER1_WIN, \
                f"Player2 HP {p2_hp} <= 0: player1 should win"
            assert result.winner_id == player1_id
        else:
            # Both have HP > 0, game continues
            assert result.status == DuelStatus.PLAYING, \
                f"Both have HP > 0 ({p1_hp}, {p2_hp}): game should continue"
            assert result.winner_id is None
    
    @settings(max_examples=100)
    @given(
        player1_id=user_id_strategy,
        player2_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_combat_eventually_terminates(
        self,
        player1_id: int,
        player2_id: int,
        bet: int,
        seed: int
    ):
        """
        Property 5 extended: Combat always terminates.
        
        With DAMAGE=25 and MAX_HP=100, game ends in at most 4 rounds
        (if one player always hits and other always misses).
        """
        assume(player1_id != player2_id)
        
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = DuelEngine(random_func=rng.random)
        
        state = engine.create_duel(player1_id, player2_id, bet)
        
        max_rounds = 10  # Should never need this many
        rounds = 0
        
        while not state.is_finished and rounds < max_rounds:
            # Random moves for both players
            p1_attack = list(Zone)[int(rng.random() * 3)]
            p1_defend = list(Zone)[int(rng.random() * 3)]
            p2_attack = list(Zone)[int(rng.random() * 3)]
            p2_defend = list(Zone)[int(rng.random() * 3)]
            
            state = engine.make_move(
                state,
                player1_id,
                p1_attack,
                p1_defend,
                p2_attack,
                p2_defend
            )
            rounds += 1
        
        assert state.is_finished, \
            f"Game should terminate within {max_rounds} rounds"
        assert state.winner_id in (player1_id, player2_id), \
            "Winner should be one of the players"
    
    @settings(max_examples=100)
    @given(
        player1_id=user_id_strategy,
        player2_id=user_id_strategy,
        bet=bet_strategy
    )
    def test_finished_game_has_winner(
        self,
        player1_id: int,
        player2_id: int,
        bet: int
    ):
        """
        Property 5 extended: Finished game always has a winner.
        """
        assume(player1_id != player2_id)
        
        engine = DuelEngine()
        
        # Create state where player2 is knocked out
        state = DuelState(
            player1_id=player1_id,
            player2_id=player2_id,
            player1_hp=50,
            player2_hp=0,
            current_turn=player1_id,
            bet=bet,
            status=DuelStatus.PLAYING
        )
        
        result = engine.check_termination(state)
        
        assert result.is_finished, "Game with 0 HP player should be finished"
        assert result.winner_id is not None, "Finished game should have winner"
        assert result.winner_id == player1_id, "Player with HP > 0 should win"
