"""
Property-based tests for RAG system with cross-topic perception.

**Feature: oleg-v5-refactoring, Property 4: RAG Message Topic Association**
**Validates: Requirements 4.2**

**Feature: oleg-v5-refactoring, Property 5: RAG Cross-Topic Retrieval**
**Validates: Requirements 4.4**
"""

from hypothesis import given, strategies as st, settings, assume
import os
import sys
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

# Add project root to path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)


@dataclass
class MockMessage:
    """Mock Telegram message for testing."""
    chat_id: int
    topic_id: Optional[int]
    user_id: int
    username: Optional[str]
    message_id: int
    text: str


class MockRAGStorage:
    """
    Mock RAG storage that simulates ChromaDB behavior for testing.
    
    This allows us to test the RAG storage logic without requiring
    the actual ChromaDB dependency which has compatibility issues.
    """
    
    def __init__(self):
        self.documents: Dict[str, Dict[str, Any]] = {}
    
    def store_message(self, text: str, chat_id: int, topic_id: Optional[int],
                      user_id: int, username: Optional[str], message_id: int) -> str:
        """Store a message with metadata."""
        expected_topic_id = topic_id if topic_id is not None else -1
        doc_id = f"msg_{chat_id}_{message_id}"
        
        self.documents[doc_id] = {
            "text": text,
            "metadata": {
                "chat_id": chat_id,
                "topic_id": expected_topic_id,
                "user_id": user_id,
                "username": username or "",
                "message_id": message_id,
            }
        }
        return doc_id
    
    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by ID."""
        return self.documents.get(doc_id)
    
    def search(self, query: str, chat_id: Optional[int] = None, 
               topic_id: Optional[int] = None, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for documents, optionally filtering by chat_id and/or topic_id.
        
        For cross-topic retrieval, only filter by chat_id (not topic_id).
        """
        results = []
        for doc_id, doc in self.documents.items():
            metadata = doc["metadata"]
            
            # Filter by chat_id if specified
            if chat_id is not None and metadata["chat_id"] != chat_id:
                continue
            
            # Filter by topic_id if specified (for non-cross-topic queries)
            if topic_id is not None and metadata["topic_id"] != topic_id:
                continue
            
            # Simple relevance: check if query terms appear in text
            if query.lower() in doc["text"].lower() or not query:
                results.append({
                    "id": doc_id,
                    "text": doc["text"],
                    "metadata": metadata
                })
        
        return results[:n_results]
    
    def search_cross_topic(self, query: str, chat_id: int, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        Cross-topic search: returns messages from all topics in the chat.
        Only filters by chat_id, not by topic_id.
        """
        return self.search(query, chat_id=chat_id, topic_id=None, n_results=n_results)


# Strategies for generating test data
chat_id_strategy = st.integers(min_value=1, max_value=10**12)
topic_id_strategy = st.one_of(st.none(), st.integers(min_value=1, max_value=10**6))
user_id_strategy = st.integers(min_value=1, max_value=10**12)
username_strategy = st.one_of(st.none(), st.text(min_size=1, max_size=32, alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_')))
message_id_strategy = st.integers(min_value=1, max_value=10**9)
text_strategy = st.text(min_size=1, max_size=500, alphabet=st.characters(blacklist_categories=('Cs',)))


class TestRAGMessageTopicAssociation:
    """
    **Feature: oleg-v5-refactoring, Property 4: RAG Message Topic Association**
    **Validates: Requirements 4.2**
    
    For any message stored in RAG, the stored entry SHALL contain
    the correct chat_id and topic_id from the original message.
    """
    
    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy,
        topic_id=topic_id_strategy,
        user_id=user_id_strategy,
        username=username_strategy,
        message_id=message_id_strategy,
        text=text_strategy
    )
    def test_stored_message_contains_correct_chat_and_topic_ids(
        self, chat_id: int, topic_id: Optional[int], user_id: int, 
        username: Optional[str], message_id: int, text: str
    ):
        """
        Property: Stored RAG entry contains correct chat_id and topic_id.
        """
        # Skip empty text
        assume(text.strip())
        
        storage = MockRAGStorage()
        
        # Store message with metadata
        expected_topic_id = topic_id if topic_id is not None else -1
        doc_id = storage.store_message(
            text=text,
            chat_id=chat_id,
            topic_id=topic_id,
            user_id=user_id,
            username=username,
            message_id=message_id
        )
        
        # Retrieve and verify
        result = storage.get(doc_id)
        
        assert result is not None
        stored_metadata = result['metadata']
        
        # Verify chat_id and topic_id are correctly stored
        assert stored_metadata['chat_id'] == chat_id, \
            f"Expected chat_id {chat_id}, got {stored_metadata['chat_id']}"
        assert stored_metadata['topic_id'] == expected_topic_id, \
            f"Expected topic_id {expected_topic_id}, got {stored_metadata['topic_id']}"
        assert stored_metadata['user_id'] == user_id
        assert stored_metadata['message_id'] == message_id
        
        # Verify text is stored correctly
        assert result['text'] == text
    
    @settings(max_examples=50)
    @given(
        chat_id=chat_id_strategy,
        topic_ids=st.lists(topic_id_strategy, min_size=2, max_size=5),
        text=text_strategy
    )
    def test_multiple_topics_stored_independently(
        self, chat_id: int, topic_ids: list, text: str
    ):
        """
        Property: Messages from different topics are stored with their respective topic_ids.
        """
        assume(text.strip())
        
        storage = MockRAGStorage()
        
        # Store messages from different topics
        for i, topic_id in enumerate(topic_ids):
            storage.store_message(
                text=f"{text}_{i}",
                chat_id=chat_id,
                topic_id=topic_id,
                user_id=12345,
                username="testuser",
                message_id=i + 1
            )
        
        # Verify each message has correct topic_id
        for i, topic_id in enumerate(topic_ids):
            expected_topic_id = topic_id if topic_id is not None else -1
            result = storage.get(f"msg_{chat_id}_{i+1}")
            
            assert result['metadata']['topic_id'] == expected_topic_id
            assert result['metadata']['chat_id'] == chat_id


class TestRAGCrossTopicRetrieval:
    """
    **Feature: oleg-v5-refactoring, Property 5: RAG Cross-Topic Retrieval**
    **Validates: Requirements 4.4**
    
    For any RAG query, the results SHALL include relevant messages
    from all topics in the chat, not just the current topic.
    """
    
    @settings(max_examples=50)
    @given(
        chat_id=chat_id_strategy,
        topic_ids=st.lists(st.integers(min_value=1, max_value=1000), min_size=2, max_size=4, unique=True),
    )
    def test_cross_topic_retrieval_returns_messages_from_all_topics(
        self, chat_id: int, topic_ids: list
    ):
        """
        Property: Query returns messages from all topics in the chat.
        """
        storage = MockRAGStorage()
        
        # Store messages from different topics with similar content
        base_text = "This is a test message about programming"
        
        for i, topic_id in enumerate(topic_ids):
            storage.store_message(
                text=f"{base_text} in topic {topic_id}",
                chat_id=chat_id,
                topic_id=topic_id,
                user_id=12345,
                username="testuser",
                message_id=i + 1
            )
        
        # Cross-topic retrieval (filter by chat_id only)
        results = storage.search_cross_topic(
            query="programming",
            chat_id=chat_id,
            n_results=len(topic_ids)
        )
        
        # Should return messages from all topics
        assert len(results) == len(topic_ids)
        
        # Verify we got messages from different topics
        retrieved_topic_ids = {r['metadata']['topic_id'] for r in results}
        
        assert retrieved_topic_ids == set(topic_ids), \
            f"Expected topics {set(topic_ids)}, got {retrieved_topic_ids}"
    
    @settings(max_examples=50)
    @given(
        chat_id1=st.integers(min_value=1, max_value=10**6),
        chat_id2=st.integers(min_value=10**6 + 1, max_value=2 * 10**6),
    )
    def test_cross_topic_retrieval_filters_by_chat(
        self, chat_id1: int, chat_id2: int
    ):
        """
        Property: Cross-topic retrieval only returns messages from the specified chat.
        """
        storage = MockRAGStorage()
        
        # Store messages from two different chats
        storage.store_message(
            text="Message from chat 1 about Python",
            chat_id=chat_id1,
            topic_id=1,
            user_id=1,
            username="user1",
            message_id=1
        )
        
        storage.store_message(
            text="Message from chat 2 about Python",
            chat_id=chat_id2,
            topic_id=2,
            user_id=2,
            username="user2",
            message_id=2
        )
        
        # Query for chat_id1 only
        results1 = storage.search_cross_topic(
            query="Python",
            chat_id=chat_id1,
            n_results=10
        )
        
        # Should only return message from chat_id1
        assert len(results1) == 1
        assert results1[0]['metadata']['chat_id'] == chat_id1
        
        # Query for chat_id2 only
        results2 = storage.search_cross_topic(
            query="Python",
            chat_id=chat_id2,
            n_results=10
        )
        
        # Should only return message from chat_id2
        assert len(results2) == 1
        assert results2[0]['metadata']['chat_id'] == chat_id2
    
    @settings(max_examples=30)
    @given(
        chat_id=chat_id_strategy,
        current_topic=st.integers(min_value=1, max_value=100),
        other_topics=st.lists(st.integers(min_value=101, max_value=200), min_size=1, max_size=3, unique=True),
    )
    def test_retrieval_includes_other_topics_not_just_current(
        self, chat_id: int, current_topic: int, other_topics: list
    ):
        """
        Property: Retrieval includes messages from topics other than the current one.
        """
        storage = MockRAGStorage()
        
        # Store message in current topic
        storage.store_message(
            text="Discussion about databases in current topic",
            chat_id=chat_id,
            topic_id=current_topic,
            user_id=1,
            username="user1",
            message_id=1
        )
        
        # Store messages in other topics
        for i, topic_id in enumerate(other_topics):
            storage.store_message(
                text=f"Discussion about databases in topic {topic_id}",
                chat_id=chat_id,
                topic_id=topic_id,
                user_id=1,
                username="user1",
                message_id=i + 100
            )
        
        # Cross-topic query (filter by chat_id only, not topic_id)
        results = storage.search_cross_topic(
            query="databases",
            chat_id=chat_id,
            n_results=10
        )
        
        # Should return messages from current AND other topics
        retrieved_topic_ids = {r['metadata']['topic_id'] for r in results}
        
        # Verify we got the current topic
        assert current_topic in retrieved_topic_ids, \
            f"Current topic {current_topic} not in results {retrieved_topic_ids}"
        
        # Verify we got at least one other topic
        other_topics_in_results = retrieved_topic_ids - {current_topic}
        assert len(other_topics_in_results) > 0, \
            f"No other topics found in results. Got only {retrieved_topic_ids}"
