"""
Property-based tests for League Manager.

Tests correctness properties defined in the design document.
Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings

# Import leagues module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'leagues.py')
_spec = importlib.util.spec_from_file_location("leagues", _module_path)
_leagues_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_leagues_module)

League = _leagues_module.League
LeagueManager = _leagues_module.LeagueManager
LeagueChange = _leagues_module.LeagueChange


# Strategies for generating test data
elo_strategy = st.integers(min_value=0, max_value=5000)


class TestLeagueAssignmentByELO:
    """
    **Feature: grand-casino-dictator, Property 16: League Assignment by ELO**
    **Validates: Requirements 11.1, 11.2, 11.3, 11.4**
    
    *For any* ELO value, the assigned league matches the correct range:
    Scrap (0-500), Silicon (500-1000), Quantum (1000-2000), Elite (2000+).
    """
    
    @settings(max_examples=100)
    @given(elo=elo_strategy)
    def test_league_assignment_by_elo(self, elo: int):
        """
        Property 16: League assignment matches ELO ranges.
        
        For any ELO value:
        - 0-499: Scrap
        - 500-999: Silicon
        - 1000-1999: Quantum
        - 2000+: Elite
        """
        manager = LeagueManager()
        league = manager.get_league(elo)
        
        if elo < 500:
            assert league == League.SCRAP, \
                f"ELO {elo} should be Scrap, got {league.display_name}"
        elif elo < 1000:
            assert league == League.SILICON, \
                f"ELO {elo} should be Silicon, got {league.display_name}"
        elif elo < 2000:
            assert league == League.QUANTUM, \
                f"ELO {elo} should be Quantum, got {league.display_name}"
        else:
            assert league == League.ELITE, \
                f"ELO {elo} should be Elite, got {league.display_name}"
    
    @settings(max_examples=100)
    @given(elo=elo_strategy)
    def test_elo_within_league_bounds(self, elo: int):
        """
        Property 16 extended: Assigned league's bounds contain the ELO.
        """
        manager = LeagueManager()
        league = manager.get_league(elo)
        
        assert league.min_elo <= elo, \
            f"ELO {elo} should be >= league min {league.min_elo}"
        
        # For Elite, max_elo is infinity
        if league != League.ELITE:
            assert elo < league.max_elo, \
                f"ELO {elo} should be < league max {league.max_elo}"
    
    @settings(max_examples=100)
    @given(elo=st.integers(min_value=-1000, max_value=-1))
    def test_negative_elo_defaults_to_scrap(self, elo: int):
        """
        Property 16 extended: Negative ELO values are treated as 0 (Scrap).
        """
        manager = LeagueManager()
        league = manager.get_league(elo)
        
        assert league == League.SCRAP, \
            f"Negative ELO {elo} should default to Scrap, got {league.display_name}"
    
    def test_boundary_values(self):
        """
        Property 16 extended: Exact boundary values are assigned correctly.
        """
        manager = LeagueManager()
        
        # Test exact boundaries
        assert manager.get_league(0) == League.SCRAP
        assert manager.get_league(499) == League.SCRAP
        assert manager.get_league(500) == League.SILICON
        assert manager.get_league(999) == League.SILICON
        assert manager.get_league(1000) == League.QUANTUM
        assert manager.get_league(1999) == League.QUANTUM
        assert manager.get_league(2000) == League.ELITE
        assert manager.get_league(10000) == League.ELITE
    
    @settings(max_examples=100)
    @given(elo=elo_strategy)
    def test_league_contains_elo_method(self, elo: int):
        """
        Property 16 extended: League.contains_elo() is consistent with get_league().
        """
        manager = LeagueManager()
        assigned_league = manager.get_league(elo)
        
        # The assigned league should contain the ELO
        assert assigned_league.contains_elo(max(0, elo)), \
            f"Assigned league {assigned_league.display_name} should contain ELO {elo}"
        
        # Other leagues should not contain the ELO (except for negative values)
        if elo >= 0:
            for league in League:
                if league != assigned_league:
                    assert not league.contains_elo(elo), \
                        f"League {league.display_name} should not contain ELO {elo}"



class TestLeagueBoundaryUpdate:
    """
    **Feature: grand-casino-dictator, Property 17: League Boundary Update**
    **Validates: Requirements 11.5**
    
    *For any* ELO change that crosses a league boundary, the player's league
    is automatically updated to the new correct league.
    """
    
    @settings(max_examples=100)
    @given(
        old_elo=elo_strategy,
        new_elo=elo_strategy
    )
    def test_league_boundary_update(self, old_elo: int, new_elo: int):
        """
        Property 17: League changes are detected when ELO crosses boundaries.
        
        For any ELO change:
        - If old and new ELO are in different leagues, changed=True
        - If old and new ELO are in same league, changed=False
        - The new_league always matches the new ELO
        """
        manager = LeagueManager()
        change = manager.check_league_change(old_elo, new_elo)
        
        expected_old_league = manager.get_league(old_elo)
        expected_new_league = manager.get_league(new_elo)
        
        # Old league should match
        assert change.old_league == expected_old_league, \
            f"Old league mismatch: {change.old_league} vs {expected_old_league}"
        
        # New league should match
        assert change.new_league == expected_new_league, \
            f"New league mismatch: {change.new_league} vs {expected_new_league}"
        
        # Changed flag should be correct
        expected_changed = expected_old_league != expected_new_league
        assert change.changed == expected_changed, \
            f"Changed flag mismatch: {change.changed} vs {expected_changed}"
    
    @settings(max_examples=100)
    @given(
        old_elo=st.integers(min_value=0, max_value=499),
        new_elo=st.integers(min_value=500, max_value=999)
    )
    def test_promotion_scrap_to_silicon(self, old_elo: int, new_elo: int):
        """
        Property 17: Promotion from Scrap to Silicon is detected.
        """
        manager = LeagueManager()
        change = manager.check_league_change(old_elo, new_elo)
        
        assert change.changed, "Should detect league change"
        assert change.old_league == League.SCRAP
        assert change.new_league == League.SILICON
        assert change.promoted, "Should be a promotion"
        assert not change.demoted, "Should not be a demotion"
    
    @settings(max_examples=100)
    @given(
        old_elo=st.integers(min_value=500, max_value=999),
        new_elo=st.integers(min_value=0, max_value=499)
    )
    def test_demotion_silicon_to_scrap(self, old_elo: int, new_elo: int):
        """
        Property 17: Demotion from Silicon to Scrap is detected.
        """
        manager = LeagueManager()
        change = manager.check_league_change(old_elo, new_elo)
        
        assert change.changed, "Should detect league change"
        assert change.old_league == League.SILICON
        assert change.new_league == League.SCRAP
        assert change.demoted, "Should be a demotion"
        assert not change.promoted, "Should not be a promotion"
    
    @settings(max_examples=100)
    @given(
        old_elo=st.integers(min_value=1000, max_value=1999),
        new_elo=st.integers(min_value=2000, max_value=5000)
    )
    def test_promotion_quantum_to_elite(self, old_elo: int, new_elo: int):
        """
        Property 17: Promotion from Quantum to Elite is detected.
        """
        manager = LeagueManager()
        change = manager.check_league_change(old_elo, new_elo)
        
        assert change.changed, "Should detect league change"
        assert change.old_league == League.QUANTUM
        assert change.new_league == League.ELITE
        assert change.promoted, "Should be a promotion"
    
    @settings(max_examples=100)
    @given(elo=elo_strategy)
    def test_no_change_within_same_league(self, elo: int):
        """
        Property 17: No league change when ELO stays within same league.
        """
        manager = LeagueManager()
        league = manager.get_league(elo)
        
        # Stay within the same league bounds
        min_elo = league.min_elo
        max_elo = int(league.max_elo) if league != League.ELITE else 5000
        
        # Test with same ELO
        change = manager.check_league_change(elo, elo)
        assert not change.changed, "Same ELO should not change league"
        assert not change.promoted
        assert not change.demoted
    
    def test_all_boundary_crossings(self):
        """
        Property 17: All boundary crossings are detected correctly.
        """
        manager = LeagueManager()
        
        # Test all upward boundary crossings
        boundaries = [
            (499, 500, League.SCRAP, League.SILICON),
            (999, 1000, League.SILICON, League.QUANTUM),
            (1999, 2000, League.QUANTUM, League.ELITE),
        ]
        
        for old_elo, new_elo, expected_old, expected_new in boundaries:
            change = manager.check_league_change(old_elo, new_elo)
            assert change.changed, f"Should detect change at {old_elo} -> {new_elo}"
            assert change.old_league == expected_old
            assert change.new_league == expected_new
            assert change.promoted
        
        # Test all downward boundary crossings
        for new_elo, old_elo, expected_new, expected_old in boundaries:
            change = manager.check_league_change(old_elo, new_elo)
            assert change.changed, f"Should detect change at {old_elo} -> {new_elo}"
            assert change.old_league == expected_old
            assert change.new_league == expected_new
            assert change.demoted
    
    @settings(max_examples=100)
    @given(
        old_elo=st.integers(min_value=0, max_value=499),
        new_elo=st.integers(min_value=2000, max_value=5000)
    )
    def test_multi_league_jump(self, old_elo: int, new_elo: int):
        """
        Property 17: Multi-league jumps are handled correctly.
        """
        manager = LeagueManager()
        change = manager.check_league_change(old_elo, new_elo)
        
        assert change.changed
        assert change.old_league == League.SCRAP
        assert change.new_league == League.ELITE
        assert change.promoted
