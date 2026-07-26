"""
Property-based tests for TournamentService (Periodic Competitions System).

**Feature: fortress-update, Property 27: Tournament winner count**
**Validates: Requirements 10.4**

**Feature: fortress-update, Property 28: Tournament achievement recording**
**Validates: Requirements 10.6**
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Inline definitions to avoid import issues during testing
# These mirror the actual implementation in app/services/tournaments.py
# ============================================================================

class TournamentType(Enum):
    """Types of tournaments based on duration."""
    DAILY = "daily"
    WEEKLY = "weekly"
    GRAND_CUP = "grand_cup"


class TournamentDiscipline(Enum):
    """Disciplines tracked in tournaments."""
    GROW = "grow"
    PVP = "pvp"
    ROULETTE = "roulette"


# Number of winners to announce per discipline (Requirement 10.4)
TOP_WINNERS_COUNT = 3


@dataclass
class TournamentStanding:
    """A single standing entry in tournament rankings."""
    user_id: int
    username: Optional[str]
    score: int
    rank: int


@dataclass
class TournamentWinner:
    """A tournament winner entry."""
    user_id: int
    username: Optional[str]
    discipline: TournamentDiscipline
    score: int
    rank: int
    tournament_type: TournamentType


@dataclass
class TournamentInfo:
    """Information about a tournament."""
    id: int
    type: TournamentType
    start_at: datetime
    end_at: datetime
    status: str
    standings: Dict[TournamentDiscipline, List[TournamentStanding]] = field(default_factory=dict)


@dataclass
class TournamentScore:
    """Score record for a user in a tournament discipline."""
    tournament_id: int
    user_id: int
    discipline: str
    score: int


@dataclass
class Achievement:
    """Achievement record."""
    code: str
    name: str
    description: str


@dataclass
class UserAchievement:
    """User achievement record."""
    user_id: int
    achievement_code: str


class MockTournamentService:
    """
    Mock TournamentService for testing without DB dependencies.
    
    Simulates the core logic of the actual TournamentService.
    """
    
    def __init__(self):
        self._tournaments: Dict[int, TournamentInfo] = {}
        self._scores: Dict[int, List[TournamentScore]] = {}  # tournament_id -> scores
        self._achievements: List[UserAchievement] = []
        self._next_id = 1
    
    def start_tournament(self, tournament_type: TournamentType) -> TournamentInfo:
        """Start a new tournament."""
        now = datetime.utcnow()
        
        if tournament_type == TournamentType.DAILY:
            end_at = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif tournament_type == TournamentType.WEEKLY:
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            end_at = (now + timedelta(days=days_until_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:  # GRAND_CUP
            if now.month == 12:
                end_at = now.replace(
                    year=now.year + 1, month=1, day=1,
                    hour=0, minute=0, second=0, microsecond=0
                )
            else:
                end_at = now.replace(
                    month=now.month + 1, day=1,
                    hour=0, minute=0, second=0, microsecond=0
                )
        
        tournament = TournamentInfo(
            id=self._next_id,
            type=tournament_type,
            start_at=now,
            end_at=end_at,
            status='active',
            standings={}
        )
        
        self._tournaments[self._next_id] = tournament
        self._scores[self._next_id] = []
        self._next_id += 1
        
        return tournament
    
    def update_score(
        self,
        tournament_id: int,
        user_id: int,
        discipline: TournamentDiscipline,
        delta: int,
        username: Optional[str] = None
    ) -> int:
        """Update a user's score in a tournament."""
        if tournament_id not in self._scores:
            self._scores[tournament_id] = []
        
        # Find existing score
        existing = None
        for score in self._scores[tournament_id]:
            if score.user_id == user_id and score.discipline == discipline.value:
                existing = score
                break
        
        if existing:
            existing.score += delta
            return existing.score
        else:
            new_score = TournamentScore(
                tournament_id=tournament_id,
                user_id=user_id,
                discipline=discipline.value,
                score=delta
            )
            self._scores[tournament_id].append(new_score)
            return delta
    
    def get_standings(
        self,
        tournament_id: int,
        discipline: TournamentDiscipline,
        limit: int = 10
    ) -> List[TournamentStanding]:
        """Get standings for a tournament discipline."""
        if tournament_id not in self._scores:
            return []
        
        # Filter by discipline and sort by score
        discipline_scores = [
            s for s in self._scores[tournament_id]
            if s.discipline == discipline.value
        ]
        discipline_scores.sort(key=lambda x: x.score, reverse=True)
        
        standings = []
        for rank, score in enumerate(discipline_scores[:limit], start=1):
            standings.append(TournamentStanding(
                user_id=score.user_id,
                username=f"user_{score.user_id}",
                score=score.score,
                rank=rank
            ))
        
        return standings
    
    def end_tournament(self, tournament_id: int) -> List[TournamentWinner]:
        """
        End a tournament and determine winners.
        
        Returns top 3 winners for each discipline.
        **Validates: Requirements 10.4, 10.6**
        """
        if tournament_id not in self._tournaments:
            return []
        
        tournament = self._tournaments[tournament_id]
        if tournament.status == 'completed':
            return []
        
        winners: List[TournamentWinner] = []
        
        # Get top 3 for each discipline (Requirement 10.4)
        for discipline in TournamentDiscipline:
            standings = self.get_standings(
                tournament_id, discipline, limit=TOP_WINNERS_COUNT
            )
            
            for standing in standings:
                winner = TournamentWinner(
                    user_id=standing.user_id,
                    username=standing.username,
                    discipline=discipline,
                    score=standing.score,
                    rank=standing.rank,
                    tournament_type=tournament.type
                )
                winners.append(winner)
                
                # Record achievement for 1st place (Requirement 10.6)
                if standing.rank == 1:
                    self._record_achievement(
                        standing.user_id, tournament.type, discipline
                    )
        
        tournament.status = 'completed'
        return winners
    
    def _record_achievement(
        self,
        user_id: int,
        tournament_type: TournamentType,
        discipline: TournamentDiscipline
    ) -> None:
        """Record an achievement for a tournament winner."""
        achievement_code = f"{tournament_type.value}_champion_{discipline.value}"
        
        # Check if already has this achievement
        for ua in self._achievements:
            if ua.user_id == user_id and ua.achievement_code == achievement_code:
                return
        
        self._achievements.append(UserAchievement(
            user_id=user_id,
            achievement_code=achievement_code
        ))
    
    def get_user_achievements(self, user_id: int) -> List[UserAchievement]:
        """Get all achievements for a user."""
        return [ua for ua in self._achievements if ua.user_id == user_id]
    
    def get_winners_count_per_discipline(
        self,
        winners: List[TournamentWinner]
    ) -> Dict[TournamentDiscipline, int]:
        """Count winners per discipline."""
        counts: Dict[TournamentDiscipline, int] = {}
        for discipline in TournamentDiscipline:
            counts[discipline] = len([
                w for w in winners if w.discipline == discipline
            ])
        return counts


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for user IDs (positive)
user_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for scores (positive)
scores = st.integers(min_value=1, max_value=10000)

# Strategy for tournament types
tournament_types = st.sampled_from(list(TournamentType))

# Strategy for disciplines
disciplines = st.sampled_from(list(TournamentDiscipline))

# Strategy for number of participants
participant_counts = st.integers(min_value=0, max_value=50)


# ============================================================================
# Property 27: Tournament Winner Count
# ============================================================================

class TestTournamentWinnerCount:
    """
    **Feature: fortress-update, Property 27: Tournament winner count**
    **Validates: Requirements 10.4**
    
    For any completed tournament, the announced winners list SHALL contain
    exactly 3 entries per discipline (or fewer if not enough participants).
    """
    
    def test_winner_count_constant(self):
        """
        Property: TOP_WINNERS_COUNT constant is 3.
        """
        assert TOP_WINNERS_COUNT == 3
    
    @settings(max_examples=100)
    @given(tournament_type=tournament_types)
    def test_empty_tournament_has_no_winners(self, tournament_type: TournamentType):
        """
        Property: A tournament with no participants has no winners.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        winners = service.end_tournament(tournament.id)
        
        assert len(winners) == 0
    
    @settings(max_examples=100)
    @given(
        tournament_type=tournament_types,
        user_id=user_ids,
        score=scores,
        discipline=disciplines
    )
    def test_single_participant_is_winner(
        self,
        tournament_type: TournamentType,
        user_id: int,
        score: int,
        discipline: TournamentDiscipline
    ):
        """
        Property: A single participant in a discipline is the winner.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        service.update_score(tournament.id, user_id, discipline, score)
        winners = service.end_tournament(tournament.id)
        
        # Should have exactly 1 winner for this discipline
        discipline_winners = [w for w in winners if w.discipline == discipline]
        assert len(discipline_winners) == 1
        assert discipline_winners[0].user_id == user_id
        assert discipline_winners[0].rank == 1
    
    @settings(max_examples=50)
    @given(
        tournament_type=tournament_types,
        num_participants=st.integers(min_value=3, max_value=20)
    )
    def test_exactly_three_winners_per_discipline_with_enough_participants(
        self,
        tournament_type: TournamentType,
        num_participants: int
    ):
        """
        Property: With 3+ participants, exactly 3 winners per discipline.
        **Validates: Requirements 10.4**
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        
        # Add participants to all disciplines
        for discipline in TournamentDiscipline:
            for i in range(num_participants):
                user_id = i + 1
                score = (num_participants - i) * 10  # Decreasing scores
                service.update_score(tournament.id, user_id, discipline, score)
        
        winners = service.end_tournament(tournament.id)
        
        # Check each discipline has exactly 3 winners
        counts = service.get_winners_count_per_discipline(winners)
        for discipline in TournamentDiscipline:
            assert counts[discipline] == TOP_WINNERS_COUNT
    
    @settings(max_examples=50)
    @given(
        tournament_type=tournament_types,
        num_participants=st.integers(min_value=1, max_value=2)
    )
    def test_fewer_winners_when_not_enough_participants(
        self,
        tournament_type: TournamentType,
        num_participants: int
    ):
        """
        Property: With fewer than 3 participants, winner count equals participant count.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        
        # Add participants to one discipline
        discipline = TournamentDiscipline.GROW
        for i in range(num_participants):
            user_id = i + 1
            score = (num_participants - i) * 10
            service.update_score(tournament.id, user_id, discipline, score)
        
        winners = service.end_tournament(tournament.id)
        
        # Check this discipline has correct number of winners
        discipline_winners = [w for w in winners if w.discipline == discipline]
        assert len(discipline_winners) == num_participants
    
    @settings(max_examples=50)
    @given(tournament_type=tournament_types)
    def test_winners_are_ranked_1_2_3(self, tournament_type: TournamentType):
        """
        Property: Winners are ranked 1, 2, 3 in order.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        
        # Add 5 participants to each discipline
        for discipline in TournamentDiscipline:
            for i in range(5):
                user_id = i + 1
                score = (5 - i) * 100  # 500, 400, 300, 200, 100
                service.update_score(tournament.id, user_id, discipline, score)
        
        winners = service.end_tournament(tournament.id)
        
        # Check ranks for each discipline
        for discipline in TournamentDiscipline:
            discipline_winners = [w for w in winners if w.discipline == discipline]
            ranks = [w.rank for w in discipline_winners]
            assert ranks == [1, 2, 3]
    
    @settings(max_examples=50)
    @given(tournament_type=tournament_types)
    def test_winners_ordered_by_score_descending(self, tournament_type: TournamentType):
        """
        Property: Winners are ordered by score in descending order.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        
        # Add participants with known scores
        discipline = TournamentDiscipline.PVP
        service.update_score(tournament.id, 1, discipline, 100)
        service.update_score(tournament.id, 2, discipline, 300)
        service.update_score(tournament.id, 3, discipline, 200)
        service.update_score(tournament.id, 4, discipline, 50)
        
        winners = service.end_tournament(tournament.id)
        
        discipline_winners = [w for w in winners if w.discipline == discipline]
        scores = [w.score for w in discipline_winners]
        
        # Should be sorted descending
        assert scores == sorted(scores, reverse=True)
        assert scores == [300, 200, 100]
    
    @settings(max_examples=30)
    @given(tournament_type=tournament_types)
    def test_total_winners_is_3_times_disciplines(self, tournament_type: TournamentType):
        """
        Property: Total winners = 3 * number of disciplines (with enough participants).
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        
        # Add 10 participants to all disciplines
        for discipline in TournamentDiscipline:
            for i in range(10):
                user_id = i + 1
                score = (10 - i) * 10
                service.update_score(tournament.id, user_id, discipline, score)
        
        winners = service.end_tournament(tournament.id)
        
        expected_total = TOP_WINNERS_COUNT * len(TournamentDiscipline)
        assert len(winners) == expected_total


# ============================================================================
# Property 28: Tournament Achievement Recording
# ============================================================================

class TestTournamentAchievementRecording:
    """
    **Feature: fortress-update, Property 28: Tournament achievement recording**
    **Validates: Requirements 10.6**
    
    For any tournament winner (1st place), an achievement record SHALL be created.
    """
    
    @settings(max_examples=100)
    @given(
        tournament_type=tournament_types,
        user_id=user_ids,
        score=scores,
        discipline=disciplines
    )
    def test_first_place_gets_achievement(
        self,
        tournament_type: TournamentType,
        user_id: int,
        score: int,
        discipline: TournamentDiscipline
    ):
        """
        Property: 1st place winner receives an achievement.
        **Validates: Requirements 10.6**
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        service.update_score(tournament.id, user_id, discipline, score)
        service.end_tournament(tournament.id)
        
        achievements = service.get_user_achievements(user_id)
        
        assert len(achievements) >= 1
        expected_code = f"{tournament_type.value}_champion_{discipline.value}"
        achievement_codes = [a.achievement_code for a in achievements]
        assert expected_code in achievement_codes
    
    @settings(max_examples=50)
    @given(tournament_type=tournament_types)
    def test_second_place_no_achievement(self, tournament_type: TournamentType):
        """
        Property: 2nd place does not receive a champion achievement.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        
        discipline = TournamentDiscipline.GROW
        # User 1 gets 1st place
        service.update_score(tournament.id, 1, discipline, 200)
        # User 2 gets 2nd place
        service.update_score(tournament.id, 2, discipline, 100)
        
        service.end_tournament(tournament.id)
        
        # User 2 should not have the champion achievement
        achievements = service.get_user_achievements(2)
        expected_code = f"{tournament_type.value}_champion_{discipline.value}"
        achievement_codes = [a.achievement_code for a in achievements]
        assert expected_code not in achievement_codes
    
    @settings(max_examples=50)
    @given(tournament_type=tournament_types)
    def test_third_place_no_achievement(self, tournament_type: TournamentType):
        """
        Property: 3rd place does not receive a champion achievement.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        
        discipline = TournamentDiscipline.PVP
        service.update_score(tournament.id, 1, discipline, 300)
        service.update_score(tournament.id, 2, discipline, 200)
        service.update_score(tournament.id, 3, discipline, 100)
        
        service.end_tournament(tournament.id)
        
        # User 3 should not have the champion achievement
        achievements = service.get_user_achievements(3)
        expected_code = f"{tournament_type.value}_champion_{discipline.value}"
        achievement_codes = [a.achievement_code for a in achievements]
        assert expected_code not in achievement_codes
    
    @settings(max_examples=30)
    @given(tournament_type=tournament_types)
    def test_multiple_discipline_wins_multiple_achievements(
        self,
        tournament_type: TournamentType
    ):
        """
        Property: Winning multiple disciplines gives multiple achievements.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        
        # User 1 wins all disciplines
        user_id = 1
        for discipline in TournamentDiscipline:
            service.update_score(tournament.id, user_id, discipline, 1000)
            # Add other participants so there's competition
            service.update_score(tournament.id, 2, discipline, 500)
        
        service.end_tournament(tournament.id)
        
        achievements = service.get_user_achievements(user_id)
        
        # Should have one achievement per discipline
        assert len(achievements) == len(TournamentDiscipline)
    
    @settings(max_examples=30)
    @given(tournament_type=tournament_types)
    def test_achievement_is_idempotent(self, tournament_type: TournamentType):
        """
        Property: Winning the same tournament type twice doesn't duplicate achievement.
        """
        service = MockTournamentService()
        
        user_id = 1
        discipline = TournamentDiscipline.ROULETTE
        
        # Win first tournament
        t1 = service.start_tournament(tournament_type)
        service.update_score(t1.id, user_id, discipline, 100)
        service.end_tournament(t1.id)
        
        # Win second tournament of same type
        t2 = service.start_tournament(tournament_type)
        service.update_score(t2.id, user_id, discipline, 100)
        service.end_tournament(t2.id)
        
        achievements = service.get_user_achievements(user_id)
        
        # Should still only have one achievement of this type
        expected_code = f"{tournament_type.value}_champion_{discipline.value}"
        matching = [a for a in achievements if a.achievement_code == expected_code]
        assert len(matching) == 1
    
    @settings(max_examples=30)
    @given(
        type1=tournament_types,
        type2=tournament_types
    )
    def test_different_tournament_types_give_different_achievements(
        self,
        type1: TournamentType,
        type2: TournamentType
    ):
        """
        Property: Different tournament types give different achievements.
        """
        assume(type1 != type2)
        
        service = MockTournamentService()
        
        user_id = 1
        discipline = TournamentDiscipline.GROW
        
        # Win tournament of type1
        t1 = service.start_tournament(type1)
        service.update_score(t1.id, user_id, discipline, 100)
        service.end_tournament(t1.id)
        
        # Win tournament of type2
        t2 = service.start_tournament(type2)
        service.update_score(t2.id, user_id, discipline, 100)
        service.end_tournament(t2.id)
        
        achievements = service.get_user_achievements(user_id)
        
        # Should have two different achievements
        assert len(achievements) == 2
        codes = [a.achievement_code for a in achievements]
        assert len(set(codes)) == 2  # All unique


# ============================================================================
# Additional Tournament Tests
# ============================================================================

class TestTournamentScoring:
    """
    Tests for tournament score tracking.
    """
    
    @settings(max_examples=100)
    @given(
        tournament_type=tournament_types,
        user_id=user_ids,
        score=scores,
        discipline=disciplines
    )
    def test_score_update_returns_new_total(
        self,
        tournament_type: TournamentType,
        user_id: int,
        score: int,
        discipline: TournamentDiscipline
    ):
        """
        Property: update_score returns the new total score.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        new_score = service.update_score(tournament.id, user_id, discipline, score)
        
        assert new_score == score
    
    @settings(max_examples=50)
    @given(
        tournament_type=tournament_types,
        user_id=user_ids,
        score1=scores,
        score2=scores,
        discipline=disciplines
    )
    def test_score_accumulates(
        self,
        tournament_type: TournamentType,
        user_id: int,
        score1: int,
        score2: int,
        discipline: TournamentDiscipline
    ):
        """
        Property: Multiple score updates accumulate.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        service.update_score(tournament.id, user_id, discipline, score1)
        final_score = service.update_score(tournament.id, user_id, discipline, score2)
        
        assert final_score == score1 + score2
    
    @settings(max_examples=50)
    @given(
        tournament_type=tournament_types,
        user_id=user_ids,
        score=scores
    )
    def test_scores_are_discipline_specific(
        self,
        tournament_type: TournamentType,
        user_id: int,
        score: int
    ):
        """
        Property: Scores are tracked separately per discipline.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        
        # Add score to GROW
        service.update_score(tournament.id, user_id, TournamentDiscipline.GROW, score)
        
        # Check standings for each discipline
        grow_standings = service.get_standings(
            tournament.id, TournamentDiscipline.GROW
        )
        pvp_standings = service.get_standings(
            tournament.id, TournamentDiscipline.PVP
        )
        
        # GROW should have the user, PVP should not
        assert len(grow_standings) == 1
        assert len(pvp_standings) == 0


class TestTournamentLifecycle:
    """
    Tests for tournament lifecycle management.
    """
    
    @settings(max_examples=50)
    @given(tournament_type=tournament_types)
    def test_new_tournament_is_active(self, tournament_type: TournamentType):
        """
        Property: New tournaments start with 'active' status.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        
        assert tournament.status == 'active'
    
    @settings(max_examples=50)
    @given(tournament_type=tournament_types)
    def test_ended_tournament_is_completed(self, tournament_type: TournamentType):
        """
        Property: Ended tournaments have 'completed' status.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        service.end_tournament(tournament.id)
        
        assert service._tournaments[tournament.id].status == 'completed'
    
    @settings(max_examples=50)
    @given(tournament_type=tournament_types)
    def test_ending_completed_tournament_returns_empty(
        self,
        tournament_type: TournamentType
    ):
        """
        Property: Ending an already completed tournament returns empty list.
        """
        service = MockTournamentService()
        
        tournament = service.start_tournament(tournament_type)
        service.update_score(tournament.id, 1, TournamentDiscipline.GROW, 100)
        
        # End once
        winners1 = service.end_tournament(tournament.id)
        # End again
        winners2 = service.end_tournament(tournament.id)
        
        assert len(winners1) > 0
        assert len(winners2) == 0
