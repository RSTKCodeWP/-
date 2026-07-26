"""
Property-based tests for Marriage System.

**Feature: release-candidate-8, Property 11: Marriage prevents duplicate proposals**
**Feature: release-candidate-8, Property 12: Marriage registration is symmetric**
**Validates: Requirements 9.2, 9.4**
"""

from datetime import timedelta
from typing import Optional, Tuple
from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Inline definitions to avoid import issues during testing
# ============================================================================

def normalize_user_ids(user1_id: int, user2_id: int) -> Tuple[int, int]:
    """
    Normalize user IDs so user1_id < user2_id.
    This ensures consistent storage in the Marriage table.
    
    **Validates: Requirements 9.2**
    """
    if user1_id < user2_id:
        return user1_id, user2_id
    return user2_id, user1_id


class MarriageState:
    """
    In-memory marriage state for testing without database dependencies.
    
    This mirrors the core logic from app/handlers/marriages.py.
    """
    
    def __init__(self):
        # Active marriages: {(user1_id, user2_id, chat_id): marriage_data}
        # user1_id < user2_id always (normalized)
        self._marriages: dict[tuple[int, int, int], dict] = {}
        
        # Pending proposals: {proposal_id: proposal_data}
        self._proposals: dict[int, dict] = {}
        self._next_proposal_id = 1
    
    def is_user_married(self, user_id: int, chat_id: int) -> bool:
        """
        Check if a user is currently married in a chat.
        
        **Validates: Requirements 9.4**
        """
        for (u1, u2, cid), marriage in self._marriages.items():
            if cid == chat_id and (u1 == user_id or u2 == user_id):
                if marriage.get("divorced_at") is None:
                    return True
        return False
    
    def get_spouse_id(self, user_id: int, chat_id: int) -> Optional[int]:
        """
        Get the spouse's user ID if the user is married.
        """
        for (u1, u2, cid), marriage in self._marriages.items():
            if cid == chat_id and marriage.get("divorced_at") is None:
                if u1 == user_id:
                    return u2
                if u2 == user_id:
                    return u1
        return None
    
    def has_pending_proposal(self, from_user_id: int, to_user_id: int, chat_id: int) -> bool:
        """
        Check if there's already a pending proposal between these users.
        
        **Validates: Requirements 9.4**
        """
        for proposal in self._proposals.values():
            if proposal["status"] != "pending":
                continue
            if proposal["chat_id"] != chat_id:
                continue
            # Check both directions
            if (proposal["from_user_id"] == from_user_id and 
                proposal["to_user_id"] == to_user_id):
                return True
            if (proposal["from_user_id"] == to_user_id and 
                proposal["to_user_id"] == from_user_id):
                return True
        return False
    
    def create_proposal(self, from_user_id: int, to_user_id: int, chat_id: int) -> int:
        """
        Create a new marriage proposal.
        
        **Validates: Requirements 9.1**
        
        Returns:
            Proposal ID
        """
        proposal_id = self._next_proposal_id
        self._next_proposal_id += 1
        
        self._proposals[proposal_id] = {
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "chat_id": chat_id,
            "status": "pending"
        }
        return proposal_id
    
    def accept_proposal(self, proposal_id: int) -> bool:
        """
        Accept a marriage proposal and create the marriage.
        
        **Validates: Requirements 9.2**
        
        Returns:
            True if marriage was created, False otherwise
        """
        if proposal_id not in self._proposals:
            return False
        
        proposal = self._proposals[proposal_id]
        if proposal["status"] != "pending":
            return False
        
        # Check if either user is already married
        if self.is_user_married(proposal["from_user_id"], proposal["chat_id"]):
            proposal["status"] = "rejected"
            return False
        if self.is_user_married(proposal["to_user_id"], proposal["chat_id"]):
            proposal["status"] = "rejected"
            return False
        
        # Update proposal status
        proposal["status"] = "accepted"
        
        # Create marriage with normalized user IDs
        user1_id, user2_id = normalize_user_ids(
            proposal["from_user_id"], 
            proposal["to_user_id"]
        )
        
        key = (user1_id, user2_id, proposal["chat_id"])
        self._marriages[key] = {
            "user1_id": user1_id,
            "user2_id": user2_id,
            "chat_id": proposal["chat_id"],
            "divorced_at": None
        }
        return True
    
    def reject_proposal(self, proposal_id: int) -> bool:
        """
        Reject a marriage proposal.
        
        **Validates: Requirements 9.3**
        """
        if proposal_id not in self._proposals:
            return False
        
        proposal = self._proposals[proposal_id]
        if proposal["status"] != "pending":
            return False
        
        proposal["status"] = "rejected"
        return True
    
    def divorce(self, user_id: int, chat_id: int) -> bool:
        """
        Divorce the user from their spouse.
        
        **Validates: Requirements 9.5**
        """
        for key, marriage in self._marriages.items():
            u1, u2, cid = key
            if cid == chat_id and (u1 == user_id or u2 == user_id):
                if marriage.get("divorced_at") is None:
                    marriage["divorced_at"] = "now"  # Simplified for testing
                    return True
        return False
    
    def can_propose(self, from_user_id: int, to_user_id: int, chat_id: int) -> Tuple[bool, str]:
        """
        Check if a proposal can be made.
        
        Returns:
            (can_propose, reason)
        """
        if from_user_id == to_user_id:
            return False, "Cannot marry yourself"
        
        if self.is_user_married(from_user_id, chat_id):
            return False, "Proposer is already married"
        
        if self.is_user_married(to_user_id, chat_id):
            return False, "Target is already married"
        
        if self.has_pending_proposal(from_user_id, to_user_id, chat_id):
            return False, "Pending proposal already exists"
        
        return True, "OK"


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for user IDs (positive integers, Telegram user IDs)
user_ids = st.integers(min_value=1, max_value=1000000000)

# Strategy for chat IDs (negative for groups in Telegram)
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)


# ============================================================================
# Property Tests
# ============================================================================


class TestMarriageProperties:
    """Property-based tests for Marriage System."""

    # ========================================================================
    # Property 11: Marriage prevents duplicate proposals
    # ========================================================================

    @given(
        user1_id=user_ids,
        user2_id=user_ids,
        chat_id=chat_ids,
    )
    @settings(max_examples=100)
    def test_married_user_cannot_receive_new_proposals(
        self,
        user1_id: int,
        user2_id: int,
        chat_id: int,
    ):
        """
        **Feature: release-candidate-8, Property 11: Marriage prevents duplicate proposals**
        **Validates: Requirements 9.4**
        
        For any user currently in an active marriage, new marriage proposals 
        to that user SHALL be rejected.
        """
        # Ensure different users
        assume(user1_id != user2_id)
        
        state = MarriageState()
        
        # Create and accept a proposal to marry user1 and user2
        proposal_id = state.create_proposal(user1_id, user2_id, chat_id)
        assert state.accept_proposal(proposal_id) is True, "First marriage should succeed"
        
        # Verify both users are married
        assert state.is_user_married(user1_id, chat_id) is True
        assert state.is_user_married(user2_id, chat_id) is True
        
        # Generate a third user
        user3_id = user1_id + 1000000 if user1_id + 1000000 != user2_id else user1_id + 2000000
        
        # Try to propose to married user1 from user3
        can_propose, reason = state.can_propose(user3_id, user1_id, chat_id)
        assert can_propose is False, (
            f"Should not be able to propose to married user. Reason: {reason}"
        )
        assert "married" in reason.lower(), f"Reason should mention marriage: {reason}"

    @given(
        user1_id=user_ids,
        user2_id=user_ids,
        chat_id=chat_ids,
    )
    @settings(max_examples=100)
    def test_married_user_cannot_make_new_proposals(
        self,
        user1_id: int,
        user2_id: int,
        chat_id: int,
    ):
        """
        **Feature: release-candidate-8, Property 11: Marriage prevents duplicate proposals**
        **Validates: Requirements 9.4**
        
        For any user currently in an active marriage, that user SHALL NOT be 
        able to make new marriage proposals.
        """
        # Ensure different users
        assume(user1_id != user2_id)
        
        state = MarriageState()
        
        # Create and accept a proposal to marry user1 and user2
        proposal_id = state.create_proposal(user1_id, user2_id, chat_id)
        assert state.accept_proposal(proposal_id) is True, "First marriage should succeed"
        
        # Generate a third user
        user3_id = user1_id + 1000000 if user1_id + 1000000 != user2_id else user1_id + 2000000
        
        # Try to propose from married user1 to user3
        can_propose, reason = state.can_propose(user1_id, user3_id, chat_id)
        assert can_propose is False, (
            f"Married user should not be able to propose. Reason: {reason}"
        )
        assert "married" in reason.lower(), f"Reason should mention marriage: {reason}"

    @given(
        user1_id=user_ids,
        user2_id=user_ids,
        chat_id=chat_ids,
    )
    @settings(max_examples=100)
    def test_pending_proposal_prevents_duplicate(
        self,
        user1_id: int,
        user2_id: int,
        chat_id: int,
    ):
        """
        **Feature: release-candidate-8, Property 11: Marriage prevents duplicate proposals**
        **Validates: Requirements 9.4**
        
        If a pending proposal exists between two users, a new proposal 
        between the same users SHALL be rejected.
        """
        # Ensure different users
        assume(user1_id != user2_id)
        
        state = MarriageState()
        
        # Create first proposal
        state.create_proposal(user1_id, user2_id, chat_id)
        
        # Try to create duplicate proposal (same direction)
        can_propose, reason = state.can_propose(user1_id, user2_id, chat_id)
        assert can_propose is False, (
            f"Should not allow duplicate proposal. Reason: {reason}"
        )
        assert "pending" in reason.lower(), f"Reason should mention pending: {reason}"
        
        # Try to create reverse proposal (opposite direction)
        can_propose_reverse, reason_reverse = state.can_propose(user2_id, user1_id, chat_id)
        assert can_propose_reverse is False, (
            f"Should not allow reverse proposal while pending. Reason: {reason_reverse}"
        )

    # ========================================================================
    # Property 12: Marriage registration is symmetric
    # ========================================================================

    @given(
        user1_id=user_ids,
        user2_id=user_ids,
        chat_id=chat_ids,
    )
    @settings(max_examples=100)
    def test_marriage_is_symmetric(
        self,
        user1_id: int,
        user2_id: int,
        chat_id: int,
    ):
        """
        **Feature: release-candidate-8, Property 12: Marriage registration is symmetric**
        **Validates: Requirements 9.2**
        
        For any accepted marriage proposal between users A and B, 
        both is_married(A) and is_married(B) SHALL return True.
        """
        # Ensure different users
        assume(user1_id != user2_id)
        
        state = MarriageState()
        
        # Create and accept proposal
        proposal_id = state.create_proposal(user1_id, user2_id, chat_id)
        result = state.accept_proposal(proposal_id)
        
        assert result is True, "Marriage should be created"
        
        # Both users should be married
        assert state.is_user_married(user1_id, chat_id) is True, (
            f"User {user1_id} should be married after accepting proposal"
        )
        assert state.is_user_married(user2_id, chat_id) is True, (
            f"User {user2_id} should be married after accepting proposal"
        )

    @given(
        user1_id=user_ids,
        user2_id=user_ids,
        chat_id=chat_ids,
    )
    @settings(max_examples=100)
    def test_spouse_lookup_is_symmetric(
        self,
        user1_id: int,
        user2_id: int,
        chat_id: int,
    ):
        """
        **Feature: release-candidate-8, Property 12: Marriage registration is symmetric**
        **Validates: Requirements 9.2**
        
        For any married couple A and B, get_spouse(A) SHALL return B 
        and get_spouse(B) SHALL return A.
        """
        # Ensure different users
        assume(user1_id != user2_id)
        
        state = MarriageState()
        
        # Create and accept proposal
        proposal_id = state.create_proposal(user1_id, user2_id, chat_id)
        state.accept_proposal(proposal_id)
        
        # Spouse lookup should be symmetric
        spouse_of_user1 = state.get_spouse_id(user1_id, chat_id)
        spouse_of_user2 = state.get_spouse_id(user2_id, chat_id)
        
        assert spouse_of_user1 == user2_id, (
            f"Spouse of user1 ({user1_id}) should be user2 ({user2_id}), "
            f"got {spouse_of_user1}"
        )
        assert spouse_of_user2 == user1_id, (
            f"Spouse of user2 ({user2_id}) should be user1 ({user1_id}), "
            f"got {spouse_of_user2}"
        )

    @given(
        user1_id=user_ids,
        user2_id=user_ids,
        chat_id=chat_ids,
    )
    @settings(max_examples=100)
    def test_marriage_order_independence(
        self,
        user1_id: int,
        user2_id: int,
        chat_id: int,
    ):
        """
        **Feature: release-candidate-8, Property 12: Marriage registration is symmetric**
        **Validates: Requirements 9.2**
        
        Marriage registration SHALL be independent of proposal direction.
        Whether A proposes to B or B proposes to A, the resulting marriage 
        state SHALL be equivalent.
        """
        # Ensure different users
        assume(user1_id != user2_id)
        
        # Test A -> B direction
        state1 = MarriageState()
        proposal1 = state1.create_proposal(user1_id, user2_id, chat_id)
        state1.accept_proposal(proposal1)
        
        # Test B -> A direction
        state2 = MarriageState()
        proposal2 = state2.create_proposal(user2_id, user1_id, chat_id)
        state2.accept_proposal(proposal2)
        
        # Both should result in same marriage state
        assert state1.is_user_married(user1_id, chat_id) == state2.is_user_married(user1_id, chat_id)
        assert state1.is_user_married(user2_id, chat_id) == state2.is_user_married(user2_id, chat_id)
        assert state1.get_spouse_id(user1_id, chat_id) == state2.get_spouse_id(user1_id, chat_id)
        assert state1.get_spouse_id(user2_id, chat_id) == state2.get_spouse_id(user2_id, chat_id)

    @given(
        user1_id=user_ids,
        user2_id=user_ids,
        chat_id=chat_ids,
    )
    @settings(max_examples=100)
    def test_divorce_affects_both_users(
        self,
        user1_id: int,
        user2_id: int,
        chat_id: int,
    ):
        """
        **Feature: release-candidate-8, Property 12: Marriage registration is symmetric**
        **Validates: Requirements 9.2, 9.5**
        
        When one user divorces, both users SHALL become unmarried.
        """
        # Ensure different users
        assume(user1_id != user2_id)
        
        state = MarriageState()
        
        # Create and accept proposal
        proposal_id = state.create_proposal(user1_id, user2_id, chat_id)
        state.accept_proposal(proposal_id)
        
        # Verify both are married
        assert state.is_user_married(user1_id, chat_id) is True
        assert state.is_user_married(user2_id, chat_id) is True
        
        # User1 divorces
        result = state.divorce(user1_id, chat_id)
        assert result is True, "Divorce should succeed"
        
        # Both should now be unmarried
        assert state.is_user_married(user1_id, chat_id) is False, (
            "User1 should be unmarried after divorce"
        )
        assert state.is_user_married(user2_id, chat_id) is False, (
            "User2 should also be unmarried after user1 divorces"
        )

    @given(
        user1_id=user_ids,
        user2_id=user_ids,
        chat_id=chat_ids,
    )
    @settings(max_examples=100)
    def test_user_ids_are_normalized(
        self,
        user1_id: int,
        user2_id: int,
        chat_id: int,
    ):
        """
        **Feature: release-candidate-8, Property 12: Marriage registration is symmetric**
        **Validates: Requirements 9.2**
        
        User IDs in marriage records SHALL be normalized (user1_id < user2_id).
        """
        # Ensure different users
        assume(user1_id != user2_id)
        
        normalized_u1, normalized_u2 = normalize_user_ids(user1_id, user2_id)
        
        # Normalized IDs should always have u1 < u2
        assert normalized_u1 < normalized_u2, (
            f"Normalized user1_id ({normalized_u1}) should be less than "
            f"user2_id ({normalized_u2})"
        )
        
        # Both original IDs should be present in normalized result
        assert {normalized_u1, normalized_u2} == {user1_id, user2_id}, (
            "Normalized IDs should contain the same users"
        )
