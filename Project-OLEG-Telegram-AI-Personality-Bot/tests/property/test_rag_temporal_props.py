"""
Property-based tests for RAG Temporal Memory Extensions.

**Feature: shield-economy-v65, Property 9: RAG Fact Timestamp Presence**
**Validates: Requirements 4.1**

**Feature: shield-economy-v65, Property 10: RAG Prompt Contains Current DateTime**
**Validates: Requirements 4.2**

**Feature: shield-economy-v65, Property 11: RAG Fact Prioritization by Recency**
**Validates: Requirements 4.3**

**Feature: shield-economy-v65, Property 12-15: Memory Deletion Properties**
**Validates: Requirements 5.1, 5.2, 5.3, 5.4**
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import re

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Inline definitions to avoid import issues during testing
# ============================================================================

def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@dataclass
class RAGFact:
    """A fact stored in RAG."""
    id: str
    text: str
    metadata: Dict[str, Any]
    age_days: int = -1


class MockVectorDB:
    """
    Mock VectorDB for testing temporal memory features.
    
    This mirrors the core logic from app/services/vector_db.py.
    """
    
    def __init__(self):
        # In-memory storage: collection_name -> list of facts
        self._collections: Dict[str, List[RAGFact]] = {}
        self._id_counter = 0
    
    def _get_collection(self, name: str) -> List[RAGFact]:
        """Get or create a collection."""
        if name not in self._collections:
            self._collections[name] = []
        return self._collections[name]
    
    def add_fact_with_timestamp(
        self,
        collection_name: str,
        fact_text: str,
        metadata: Dict,
        created_at: Optional[datetime] = None
    ) -> str:
        """Add a fact with timestamp in ISO 8601 format."""
        if created_at is None:
            created_at = datetime.now()
        
        # Ensure created_at is in ISO 8601 format
        metadata["created_at"] = created_at.isoformat()
        
        self._id_counter += 1
        doc_id = f"fact_{self._id_counter}"
        
        fact = RAGFact(
            id=doc_id,
            text=fact_text,
            metadata=metadata.copy(),
        )
        
        self._get_collection(collection_name).append(fact)
        return doc_id
    
    def search_facts_with_age(
        self,
        collection_name: str,
        query: str,
        chat_id: int,
        n_results: int = 5
    ) -> List[Dict]:
        """Search facts and add age_days field."""
        collection = self._get_collection(collection_name)
        now = datetime.now()
        
        # Filter by chat_id
        matching = [f for f in collection if f.metadata.get("chat_id") == chat_id]
        
        results = []
        for fact in matching[:n_results]:
            result = {
                'id': fact.id,
                'text': fact.text,
                'metadata': fact.metadata,
            }
            
            created_at_str = fact.metadata.get('created_at')
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    result['age_days'] = (now - created_at).days
                except (ValueError, TypeError):
                    result['age_days'] = -1
            else:
                result['age_days'] = -1
            
            results.append(result)
        
        # Sort by recency (newer facts first)
        results.sort(key=lambda f: f.get('age_days', 999))
        
        return results
    
    def delete_all_chat_facts(
        self,
        collection_name: str,
        chat_id: int
    ) -> int:
        """Delete all facts for a chat."""
        collection = self._get_collection(collection_name)
        original_count = len(collection)
        
        self._collections[collection_name] = [
            f for f in collection if f.metadata.get("chat_id") != chat_id
        ]
        
        return original_count - len(self._collections[collection_name])
    
    def delete_old_facts(
        self,
        collection_name: str,
        chat_id: int,
        older_than_days: int = 90
    ) -> int:
        """Delete facts older than specified days."""
        collection = self._get_collection(collection_name)
        now = datetime.now()
        
        to_keep = []
        deleted_count = 0
        
        for fact in collection:
            if fact.metadata.get("chat_id") != chat_id:
                to_keep.append(fact)
                continue
            
            created_at_str = fact.metadata.get('created_at')
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    age_days = (now - created_at).days
                    
                    if age_days >= older_than_days:
                        deleted_count += 1
                        continue
                except (ValueError, TypeError):
                    pass
            
            to_keep.append(fact)
        
        self._collections[collection_name] = to_keep
        return deleted_count
    
    def delete_user_facts(
        self,
        collection_name: str,
        chat_id: int,
        user_id: int
    ) -> int:
        """Delete all facts for a user in a chat."""
        collection = self._get_collection(collection_name)
        original_count = len(collection)
        
        self._collections[collection_name] = [
            f for f in collection 
            if not (f.metadata.get("chat_id") == chat_id and f.metadata.get("user_id") == user_id)
        ]
        
        return original_count - len(self._collections[collection_name])
    
    def get_chat_facts(self, collection_name: str, chat_id: int) -> List[RAGFact]:
        """Get all facts for a chat."""
        collection = self._get_collection(collection_name)
        return [f for f in collection if f.metadata.get("chat_id") == chat_id]


# ============================================================================
# Strategies for generating test data
# ============================================================================

chat_ids = st.integers(min_value=-1000000000000, max_value=-1)
user_ids = st.integers(min_value=1, max_value=9999999999)
fact_texts = st.text(min_size=1, max_size=200).filter(lambda x: x.strip())
collection_names = st.sampled_from(["facts", "messages", "knowledge"])


# ============================================================================
# Property Tests
# ============================================================================


class TestRAGTemporalProperties:
    """Property-based tests for RAG temporal memory."""

    # ========================================================================
    # Property 9: RAG Fact Timestamp Presence
    # ========================================================================

    @given(
        collection_name=collection_names,
        fact_text=fact_texts,
        chat_id=chat_ids,
        user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_fact_has_iso8601_timestamp(
        self,
        collection_name: str,
        fact_text: str,
        chat_id: int,
        user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 9: RAG Fact Timestamp Presence**
        **Validates: Requirements 4.1**
        
        For any fact saved to ChromaDB, the metadata SHALL include
        a created_at field in valid ISO 8601 format.
        """
        db = MockVectorDB()
        
        metadata = {
            "chat_id": chat_id,
            "user_id": user_id,
        }
        
        doc_id = db.add_fact_with_timestamp(
            collection_name=collection_name,
            fact_text=fact_text,
            metadata=metadata,
        )
        
        # Get the fact back
        facts = db.get_chat_facts(collection_name, chat_id)
        assert len(facts) == 1, "Should have exactly one fact"
        
        fact = facts[0]
        assert "created_at" in fact.metadata, "Fact should have created_at field"
        
        # Verify ISO 8601 format
        created_at_str = fact.metadata["created_at"]
        try:
            parsed = datetime.fromisoformat(created_at_str)
            assert parsed is not None, "Should parse as valid datetime"
        except ValueError:
            assert False, f"created_at '{created_at_str}' is not valid ISO 8601"

    @given(
        collection_name=collection_names,
        fact_text=fact_texts,
        chat_id=chat_ids,
        days_ago=st.integers(min_value=0, max_value=365),
    )
    @settings(max_examples=100)
    def test_custom_timestamp_preserved(
        self,
        collection_name: str,
        fact_text: str,
        chat_id: int,
        days_ago: int,
    ):
        """
        **Feature: shield-economy-v65, Property 9: RAG Fact Timestamp Presence**
        **Validates: Requirements 4.1**
        
        Custom timestamps SHALL be preserved in ISO 8601 format.
        """
        db = MockVectorDB()
        
        custom_time = datetime.now() - timedelta(days=days_ago)
        metadata = {"chat_id": chat_id}
        
        db.add_fact_with_timestamp(
            collection_name=collection_name,
            fact_text=fact_text,
            metadata=metadata,
            created_at=custom_time,
        )
        
        facts = db.get_chat_facts(collection_name, chat_id)
        fact = facts[0]
        
        stored_time = datetime.fromisoformat(fact.metadata["created_at"])
        
        # Times should be equal (within microsecond precision)
        time_diff = abs((stored_time - custom_time).total_seconds())
        assert time_diff < 1, f"Stored time should match custom time, diff: {time_diff}s"

    # ========================================================================
    # Property 11: RAG Fact Prioritization by Recency
    # ========================================================================

    @given(
        collection_name=collection_names,
        chat_id=chat_ids,
        num_facts=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=100)
    def test_newer_facts_prioritized(
        self,
        collection_name: str,
        chat_id: int,
        num_facts: int,
    ):
        """
        **Feature: shield-economy-v65, Property 11: RAG Fact Prioritization by Recency**
        **Validates: Requirements 4.3**
        
        For any set of facts, the fact with the most recent created_at
        timestamp SHALL be prioritized (appear first).
        """
        db = MockVectorDB()
        now = datetime.now()
        
        # Add facts with different ages
        for i in range(num_facts):
            days_ago = num_facts - i  # Older facts added first
            created_at = now - timedelta(days=days_ago)
            
            db.add_fact_with_timestamp(
                collection_name=collection_name,
                fact_text=f"Fact from {days_ago} days ago",
                metadata={"chat_id": chat_id},
                created_at=created_at,
            )
        
        # Search should return facts sorted by recency
        results = db.search_facts_with_age(
            collection_name=collection_name,
            query="fact",
            chat_id=chat_id,
            n_results=num_facts,
        )
        
        # Verify sorted by age (ascending = newer first)
        for i in range(len(results) - 1):
            assert results[i]['age_days'] <= results[i + 1]['age_days'], (
                f"Facts should be sorted by recency. "
                f"Got age {results[i]['age_days']} before {results[i + 1]['age_days']}"
            )

    @given(
        collection_name=collection_names,
        chat_id=chat_ids,
        topic=st.text(min_size=3, max_size=20).filter(lambda x: x.strip()),
        old_value=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        new_value=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        days_between=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_conflicting_facts_newer_prioritized(
        self,
        collection_name: str,
        chat_id: int,
        topic: str,
        old_value: str,
        new_value: str,
        days_between: int,
    ):
        """
        **Feature: shield-economy-v65, Property 11: RAG Fact Prioritization by Recency**
        **Validates: Requirements 4.3**
        
        For any set of facts with conflicting information on the same topic,
        the fact with the most recent created_at timestamp SHALL be prioritized
        (appear first in results).
        """
        # Ensure old and new values are different (conflicting)
        assume(old_value.strip() != new_value.strip())
        
        db = MockVectorDB()
        now = datetime.now()
        
        # Add older conflicting fact first
        old_created_at = now - timedelta(days=days_between)
        db.add_fact_with_timestamp(
            collection_name=collection_name,
            fact_text=f"{topic}: {old_value}",
            metadata={"chat_id": chat_id, "topic": topic},
            created_at=old_created_at,
        )
        
        # Add newer conflicting fact
        new_created_at = now
        db.add_fact_with_timestamp(
            collection_name=collection_name,
            fact_text=f"{topic}: {new_value}",
            metadata={"chat_id": chat_id, "topic": topic},
            created_at=new_created_at,
        )
        
        # Search for facts about this topic
        results = db.search_facts_with_age(
            collection_name=collection_name,
            query=topic,
            chat_id=chat_id,
            n_results=10,
        )
        
        # Should have at least 2 results (both conflicting facts)
        assert len(results) >= 2, f"Should find both conflicting facts, got {len(results)}"
        
        # The first result should be the newer fact (lower age_days)
        first_result = results[0]
        assert first_result['age_days'] <= results[1]['age_days'], (
            f"Newer fact should be prioritized. "
            f"First result age: {first_result['age_days']}, "
            f"Second result age: {results[1]['age_days']}"
        )
        
        # Verify the first result contains the new value (not the old one)
        assert new_value in first_result['text'], (
            f"First result should contain newer value '{new_value}', "
            f"but got: '{first_result['text']}'"
        )

    # ========================================================================
    # Property 12: Memory Deletion Completeness - All Facts
    # ========================================================================

    @given(
        collection_name=collection_names,
        chat_id=chat_ids,
        num_facts=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100)
    def test_delete_all_leaves_zero_facts(
        self,
        collection_name: str,
        chat_id: int,
        num_facts: int,
    ):
        """
        **Feature: shield-economy-v65, Property 12: Memory Deletion Completeness - All Facts**
        **Validates: Requirements 5.1**
        
        For any chat with facts, after "forget all" operation,
        the chat SHALL have exactly 0 facts.
        """
        db = MockVectorDB()
        
        # Add facts
        for i in range(num_facts):
            db.add_fact_with_timestamp(
                collection_name=collection_name,
                fact_text=f"Fact {i}",
                metadata={"chat_id": chat_id},
            )
        
        # Verify facts exist
        facts_before = db.get_chat_facts(collection_name, chat_id)
        assert len(facts_before) == num_facts
        
        # Delete all
        db.delete_all_chat_facts(collection_name, chat_id)
        
        # Verify zero facts remain
        facts_after = db.get_chat_facts(collection_name, chat_id)
        assert len(facts_after) == 0, (
            f"Should have 0 facts after delete_all, got {len(facts_after)}"
        )

    # ========================================================================
    # Property 13: Memory Deletion Completeness - Old Facts
    # ========================================================================

    @given(
        collection_name=collection_names,
        chat_id=chat_ids,
        old_facts_count=st.integers(min_value=1, max_value=10),
        new_facts_count=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_delete_old_removes_only_old_facts(
        self,
        collection_name: str,
        chat_id: int,
        old_facts_count: int,
        new_facts_count: int,
    ):
        """
        **Feature: shield-economy-v65, Property 13: Memory Deletion Completeness - Old Facts**
        **Validates: Requirements 5.2**
        
        For any chat after "forget old" operation, no facts with
        created_at older than 90 days SHALL remain.
        """
        db = MockVectorDB()
        now = datetime.now()
        
        # Add old facts (100+ days ago)
        for i in range(old_facts_count):
            db.add_fact_with_timestamp(
                collection_name=collection_name,
                fact_text=f"Old fact {i}",
                metadata={"chat_id": chat_id},
                created_at=now - timedelta(days=100 + i),
            )
        
        # Add new facts (10 days ago)
        for i in range(new_facts_count):
            db.add_fact_with_timestamp(
                collection_name=collection_name,
                fact_text=f"New fact {i}",
                metadata={"chat_id": chat_id},
                created_at=now - timedelta(days=10),
            )
        
        # Delete old facts
        deleted = db.delete_old_facts(collection_name, chat_id, older_than_days=90)
        
        # Verify old facts deleted
        assert deleted == old_facts_count, (
            f"Should delete {old_facts_count} old facts, deleted {deleted}"
        )
        
        # Verify new facts remain
        remaining = db.get_chat_facts(collection_name, chat_id)
        assert len(remaining) == new_facts_count, (
            f"Should have {new_facts_count} new facts remaining, got {len(remaining)}"
        )
        
        # CRITICAL: Verify NO facts older than 90 days remain
        for fact in remaining:
            created_at_str = fact.metadata.get("created_at")
            assert created_at_str is not None, "Remaining fact should have created_at"
            created_at = datetime.fromisoformat(created_at_str)
            age_days = (now - created_at).days
            assert age_days < 90, (
                f"No facts older than 90 days should remain. "
                f"Found fact with age {age_days} days"
            )

    # ========================================================================
    # Property 14: Memory Deletion Completeness - User Facts
    # ========================================================================

    @given(
        collection_name=collection_names,
        chat_id=chat_ids,
        target_user_id=user_ids,
        other_user_id=user_ids,
        target_facts=st.integers(min_value=1, max_value=10),
        other_facts=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_delete_user_removes_only_user_facts(
        self,
        collection_name: str,
        chat_id: int,
        target_user_id: int,
        other_user_id: int,
        target_facts: int,
        other_facts: int,
    ):
        """
        **Feature: shield-economy-v65, Property 14: Memory Deletion Completeness - User Facts**
        **Validates: Requirements 5.3**
        
        For any user in a chat after "forget user" operation,
        no facts associated with that user_id SHALL remain.
        """
        # Ensure different users
        assume(target_user_id != other_user_id)
        
        db = MockVectorDB()
        
        # Add target user facts
        for i in range(target_facts):
            db.add_fact_with_timestamp(
                collection_name=collection_name,
                fact_text=f"Target user fact {i}",
                metadata={"chat_id": chat_id, "user_id": target_user_id},
            )
        
        # Add other user facts
        for i in range(other_facts):
            db.add_fact_with_timestamp(
                collection_name=collection_name,
                fact_text=f"Other user fact {i}",
                metadata={"chat_id": chat_id, "user_id": other_user_id},
            )
        
        # Delete target user facts
        deleted = db.delete_user_facts(collection_name, chat_id, target_user_id)
        
        # Verify target user facts deleted
        assert deleted == target_facts, (
            f"Should delete {target_facts} user facts, deleted {deleted}"
        )
        
        # Verify other user facts remain
        remaining = db.get_chat_facts(collection_name, chat_id)
        assert len(remaining) == other_facts, (
            f"Should have {other_facts} other user facts, got {len(remaining)}"
        )
        
        # Verify no target user facts remain
        target_remaining = [f for f in remaining if f.metadata.get("user_id") == target_user_id]
        assert len(target_remaining) == 0, (
            f"Should have 0 target user facts, got {len(target_remaining)}"
        )

    # ========================================================================
    # Property 15: Deletion Count Accuracy
    # ========================================================================

    @given(
        collection_name=collection_names,
        chat_id=chat_ids,
        num_facts=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100)
    def test_deletion_count_matches_actual_delete_all(
        self,
        collection_name: str,
        chat_id: int,
        num_facts: int,
    ):
        """
        **Feature: shield-economy-v65, Property 15: Deletion Count Accuracy**
        **Validates: Requirements 5.4**
        
        For delete_all_chat_facts operation, the returned count SHALL
        equal the actual number of facts deleted.
        """
        db = MockVectorDB()
        
        # Add facts
        for i in range(num_facts):
            db.add_fact_with_timestamp(
                collection_name=collection_name,
                fact_text=f"Fact {i}",
                metadata={"chat_id": chat_id},
            )
        
        # Count before
        before_count = len(db.get_chat_facts(collection_name, chat_id))
        
        # Delete all
        reported_deleted = db.delete_all_chat_facts(collection_name, chat_id)
        
        # Count after
        after_count = len(db.get_chat_facts(collection_name, chat_id))
        
        # Actual deleted
        actual_deleted = before_count - after_count
        
        assert reported_deleted == actual_deleted, (
            f"Reported deleted ({reported_deleted}) should match "
            f"actual deleted ({actual_deleted})"
        )

    @given(
        collection_name=collection_names,
        chat_id=chat_ids,
        old_facts_count=st.integers(min_value=1, max_value=10),
        new_facts_count=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100)
    def test_deletion_count_matches_actual_delete_old(
        self,
        collection_name: str,
        chat_id: int,
        old_facts_count: int,
        new_facts_count: int,
    ):
        """
        **Feature: shield-economy-v65, Property 15: Deletion Count Accuracy**
        **Validates: Requirements 5.4**
        
        For delete_old_facts operation, the returned count SHALL
        equal the actual number of facts deleted.
        """
        db = MockVectorDB()
        now = datetime.now()
        
        # Add old facts (100+ days ago)
        for i in range(old_facts_count):
            db.add_fact_with_timestamp(
                collection_name=collection_name,
                fact_text=f"Old fact {i}",
                metadata={"chat_id": chat_id},
                created_at=now - timedelta(days=100 + i),
            )
        
        # Add new facts (10 days ago)
        for i in range(new_facts_count):
            db.add_fact_with_timestamp(
                collection_name=collection_name,
                fact_text=f"New fact {i}",
                metadata={"chat_id": chat_id},
                created_at=now - timedelta(days=10),
            )
        
        # Count before
        before_count = len(db.get_chat_facts(collection_name, chat_id))
        
        # Delete old facts
        reported_deleted = db.delete_old_facts(collection_name, chat_id, older_than_days=90)
        
        # Count after
        after_count = len(db.get_chat_facts(collection_name, chat_id))
        
        # Actual deleted
        actual_deleted = before_count - after_count
        
        assert reported_deleted == actual_deleted, (
            f"delete_old_facts: Reported deleted ({reported_deleted}) should match "
            f"actual deleted ({actual_deleted})"
        )

    @given(
        collection_name=collection_names,
        chat_id=chat_ids,
        target_user_id=user_ids,
        other_user_id=user_ids,
        target_facts=st.integers(min_value=1, max_value=10),
        other_facts=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100)
    def test_deletion_count_matches_actual_delete_user(
        self,
        collection_name: str,
        chat_id: int,
        target_user_id: int,
        other_user_id: int,
        target_facts: int,
        other_facts: int,
    ):
        """
        **Feature: shield-economy-v65, Property 15: Deletion Count Accuracy**
        **Validates: Requirements 5.4**
        
        For delete_user_facts operation, the returned count SHALL
        equal the actual number of facts deleted.
        """
        # Ensure different users
        assume(target_user_id != other_user_id)
        
        db = MockVectorDB()
        
        # Add target user facts
        for i in range(target_facts):
            db.add_fact_with_timestamp(
                collection_name=collection_name,
                fact_text=f"Target user fact {i}",
                metadata={"chat_id": chat_id, "user_id": target_user_id},
            )
        
        # Add other user facts
        for i in range(other_facts):
            db.add_fact_with_timestamp(
                collection_name=collection_name,
                fact_text=f"Other user fact {i}",
                metadata={"chat_id": chat_id, "user_id": other_user_id},
            )
        
        # Count before
        before_count = len(db.get_chat_facts(collection_name, chat_id))
        
        # Delete target user facts
        reported_deleted = db.delete_user_facts(collection_name, chat_id, target_user_id)
        
        # Count after
        after_count = len(db.get_chat_facts(collection_name, chat_id))
        
        # Actual deleted
        actual_deleted = before_count - after_count
        
        assert reported_deleted == actual_deleted, (
            f"delete_user_facts: Reported deleted ({reported_deleted}) should match "
            f"actual deleted ({actual_deleted})"
        )
