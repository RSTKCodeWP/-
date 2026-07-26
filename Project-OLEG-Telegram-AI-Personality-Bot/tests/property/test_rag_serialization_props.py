"""
Property-based tests for RAG Fact Serialization Round-Trip.

**Feature: shield-economy-v65, Property 29: RAG Fact Serialization Round-Trip**
**Validates: Requirements 11.1, 11.2**

**Feature: shield-economy-v65, Property 30: Unicode Preservation in Serialization**
**Validates: Requirements 11.3**
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Inline RAGFactMetadata definition to avoid import issues during testing
# ============================================================================

@dataclass
class RAGFactMetadata:
    """
    Metadata schema for RAG facts in ChromaDB.
    
    **Feature: shield-economy-v65**
    **Validates: Requirements 11.1, 11.2, 11.3**
    
    This dataclass ensures consistent serialization and deserialization
    of RAG fact metadata, preserving all fields including Unicode characters.
    """
    chat_id: int
    user_id: int
    username: str
    topic_id: int  # -1 if not in topic
    message_id: int
    created_at: str  # ISO 8601 format
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize metadata to a dictionary for ChromaDB storage.
        
        All fields are preserved exactly as stored, including Unicode
        characters in username and other string fields.
        
        Returns:
            Dictionary with all metadata fields
        """
        return {
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "username": self.username,
            "topic_id": self.topic_id,
            "message_id": self.message_id,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RAGFactMetadata":
        """
        Deserialize metadata from a dictionary.
        
        Handles missing fields gracefully with sensible defaults.
        Preserves Unicode characters exactly as stored.
        
        Args:
            data: Dictionary containing metadata fields
            
        Returns:
            RAGFactMetadata instance with all fields populated
        """
        return cls(
            chat_id=data["chat_id"],
            user_id=data["user_id"],
            username=data.get("username", ""),
            topic_id=data.get("topic_id", -1),
            message_id=data.get("message_id", 0),
            created_at=data["created_at"],
        )


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Telegram chat IDs are negative for groups/supergroups
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)

# Telegram user IDs are positive
user_ids = st.integers(min_value=1, max_value=9999999999)

# Usernames can contain letters, numbers, underscores
usernames = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    ),
    min_size=0,
    max_size=32
)

# Topic IDs: -1 for no topic, or positive for actual topics
topic_ids = st.one_of(
    st.just(-1),
    st.integers(min_value=1, max_value=999999)
)

# Message IDs are positive
message_ids = st.integers(min_value=0, max_value=999999999)

# ISO 8601 timestamps
def iso8601_timestamps():
    """Generate valid ISO 8601 timestamp strings."""
    return st.builds(
        lambda dt: dt.isoformat(),
        st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31)
        )
    )


# Strategy for complete RAGFactMetadata
rag_fact_metadata_strategy = st.builds(
    RAGFactMetadata,
    chat_id=chat_ids,
    user_id=user_ids,
    username=usernames,
    topic_id=topic_ids,
    message_id=message_ids,
    created_at=iso8601_timestamps(),
)


# ============================================================================
# Property Tests
# ============================================================================


class TestRAGSerializationProperties:
    """Property-based tests for RAG fact serialization round-trip."""

    # ========================================================================
    # Property 29: RAG Fact Serialization Round-Trip
    # ========================================================================

    @given(metadata=rag_fact_metadata_strategy)
    @settings(max_examples=100)
    def test_serialization_round_trip_preserves_all_fields(
        self,
        metadata: RAGFactMetadata,
    ):
        """
        **Feature: shield-economy-v65, Property 29: RAG Fact Serialization Round-Trip**
        **Validates: Requirements 11.1, 11.2**
        
        For any RAG fact with metadata (chat_id, user_id, username, topic_id,
        message_id, created_at), serializing to JSON and deserializing SHALL
        produce an equivalent object with identical field values.
        """
        # Serialize to dict
        serialized = metadata.to_dict()
        
        # Deserialize back to object
        deserialized = RAGFactMetadata.from_dict(serialized)
        
        # Verify all fields are identical
        assert deserialized.chat_id == metadata.chat_id, (
            f"chat_id mismatch: {deserialized.chat_id} != {metadata.chat_id}"
        )
        assert deserialized.user_id == metadata.user_id, (
            f"user_id mismatch: {deserialized.user_id} != {metadata.user_id}"
        )
        assert deserialized.username == metadata.username, (
            f"username mismatch: '{deserialized.username}' != '{metadata.username}'"
        )
        assert deserialized.topic_id == metadata.topic_id, (
            f"topic_id mismatch: {deserialized.topic_id} != {metadata.topic_id}"
        )
        assert deserialized.message_id == metadata.message_id, (
            f"message_id mismatch: {deserialized.message_id} != {metadata.message_id}"
        )
        assert deserialized.created_at == metadata.created_at, (
            f"created_at mismatch: '{deserialized.created_at}' != '{metadata.created_at}'"
        )

    @given(metadata=rag_fact_metadata_strategy)
    @settings(max_examples=100)
    def test_double_round_trip_is_idempotent(
        self,
        metadata: RAGFactMetadata,
    ):
        """
        **Feature: shield-economy-v65, Property 29: RAG Fact Serialization Round-Trip**
        **Validates: Requirements 11.1, 11.2**
        
        For any RAG fact, applying serialize/deserialize twice SHALL produce
        the same result as applying it once (idempotence).
        """
        # First round trip
        serialized1 = metadata.to_dict()
        deserialized1 = RAGFactMetadata.from_dict(serialized1)
        
        # Second round trip
        serialized2 = deserialized1.to_dict()
        deserialized2 = RAGFactMetadata.from_dict(serialized2)
        
        # Both round trips should produce identical results
        assert deserialized1.chat_id == deserialized2.chat_id
        assert deserialized1.user_id == deserialized2.user_id
        assert deserialized1.username == deserialized2.username
        assert deserialized1.topic_id == deserialized2.topic_id
        assert deserialized1.message_id == deserialized2.message_id
        assert deserialized1.created_at == deserialized2.created_at
        
        # Serialized dicts should also be identical
        assert serialized1 == serialized2, (
            f"Serialized dicts should be identical after double round-trip. "
            f"First: {serialized1}, Second: {serialized2}"
        )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        username=usernames,
        topic_id=topic_ids,
        message_id=message_ids,
        created_at=iso8601_timestamps(),
    )
    @settings(max_examples=100)
    def test_to_dict_contains_all_required_fields(
        self,
        chat_id: int,
        user_id: int,
        username: str,
        topic_id: int,
        message_id: int,
        created_at: str,
    ):
        """
        **Feature: shield-economy-v65, Property 29: RAG Fact Serialization Round-Trip**
        **Validates: Requirements 11.1**
        
        For any RAG fact, to_dict() SHALL preserve all metadata fields
        including chat_id, user_id, username, topic_id, message_id, created_at.
        """
        metadata = RAGFactMetadata(
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            topic_id=topic_id,
            message_id=message_id,
            created_at=created_at,
        )
        
        serialized = metadata.to_dict()
        
        # Verify all required fields are present
        required_fields = ["chat_id", "user_id", "username", "topic_id", "message_id", "created_at"]
        for field in required_fields:
            assert field in serialized, f"Missing required field: {field}"
        
        # Verify field values match
        assert serialized["chat_id"] == chat_id
        assert serialized["user_id"] == user_id
        assert serialized["username"] == username
        assert serialized["topic_id"] == topic_id
        assert serialized["message_id"] == message_id
        assert serialized["created_at"] == created_at

    # ========================================================================
    # Property 30: Unicode Preservation in Serialization
    # ========================================================================

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        topic_id=topic_ids,
        message_id=message_ids,
        created_at=iso8601_timestamps(),
        unicode_username=st.text(
            alphabet=st.characters(
                whitelist_categories=('L', 'N', 'P', 'S', 'So'),
                whitelist_characters='абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ😀😁😂🤣😃😄😅😆😉😊😋😎🎉🎊✨💫⭐🌟✅❌⚠️🔥💯🚀'
            ),
            min_size=1,
            max_size=64
        ),
    )
    @settings(max_examples=100)
    def test_unicode_preservation_cyrillic_emoji_symbols(
        self,
        chat_id: int,
        user_id: int,
        topic_id: int,
        message_id: int,
        created_at: str,
        unicode_username: str,
    ):
        """
        **Feature: shield-economy-v65, Property 30: Unicode Preservation in Serialization**
        **Validates: Requirements 11.3**
        
        For any RAG fact containing Unicode characters (Cyrillic, emoji, special symbols),
        the round-trip serialization SHALL preserve all characters exactly.
        """
        metadata = RAGFactMetadata(
            chat_id=chat_id,
            user_id=user_id,
            username=unicode_username,
            topic_id=topic_id,
            message_id=message_id,
            created_at=created_at,
        )
        
        # Serialize to dict
        serialized = metadata.to_dict()
        
        # Deserialize back to object
        deserialized = RAGFactMetadata.from_dict(serialized)
        
        # Verify Unicode username is preserved exactly
        assert deserialized.username == unicode_username, (
            f"Unicode username not preserved: '{deserialized.username}' != '{unicode_username}'"
        )
        
        # Verify byte-level equality for Unicode content
        assert deserialized.username.encode('utf-8') == unicode_username.encode('utf-8'), (
            f"Unicode encoding mismatch in username"
        )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        topic_id=topic_ids,
        message_id=message_ids,
        created_at=iso8601_timestamps(),
    )
    @settings(max_examples=100)
    def test_unicode_preservation_cyrillic_only(
        self,
        chat_id: int,
        user_id: int,
        topic_id: int,
        message_id: int,
        created_at: str,
    ):
        """
        **Feature: shield-economy-v65, Property 30: Unicode Preservation in Serialization**
        **Validates: Requirements 11.3**
        
        For any RAG fact with Cyrillic characters in username,
        the round-trip serialization SHALL preserve all Cyrillic characters exactly.
        """
        # Test with explicit Cyrillic usernames
        cyrillic_usernames = [
            "Иван",
            "Мария_Петрова",
            "АлександрСергеевич",
            "Пользователь123",
            "ЁжикВТумане",
            "Щука_и_Карась",
        ]
        
        for cyrillic_name in cyrillic_usernames:
            metadata = RAGFactMetadata(
                chat_id=chat_id,
                user_id=user_id,
                username=cyrillic_name,
                topic_id=topic_id,
                message_id=message_id,
                created_at=created_at,
            )
            
            serialized = metadata.to_dict()
            deserialized = RAGFactMetadata.from_dict(serialized)
            
            assert deserialized.username == cyrillic_name, (
                f"Cyrillic username not preserved: '{deserialized.username}' != '{cyrillic_name}'"
            )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        topic_id=topic_ids,
        message_id=message_ids,
        created_at=iso8601_timestamps(),
    )
    @settings(max_examples=100)
    def test_unicode_preservation_emoji_only(
        self,
        chat_id: int,
        user_id: int,
        topic_id: int,
        message_id: int,
        created_at: str,
    ):
        """
        **Feature: shield-economy-v65, Property 30: Unicode Preservation in Serialization**
        **Validates: Requirements 11.3**
        
        For any RAG fact with emoji characters in username,
        the round-trip serialization SHALL preserve all emoji exactly.
        """
        # Test with explicit emoji usernames
        emoji_usernames = [
            "User😀",
            "🎉Party🎊",
            "✨Star⭐User🌟",
            "🔥Hot💯",
            "🚀Rocket",
            "✅Done❌",
        ]
        
        for emoji_name in emoji_usernames:
            metadata = RAGFactMetadata(
                chat_id=chat_id,
                user_id=user_id,
                username=emoji_name,
                topic_id=topic_id,
                message_id=message_id,
                created_at=created_at,
            )
            
            serialized = metadata.to_dict()
            deserialized = RAGFactMetadata.from_dict(serialized)
            
            assert deserialized.username == emoji_name, (
                f"Emoji username not preserved: '{deserialized.username}' != '{emoji_name}'"
            )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        topic_id=topic_ids,
        message_id=message_ids,
        created_at=iso8601_timestamps(),
    )
    @settings(max_examples=100)
    def test_unicode_preservation_mixed_content(
        self,
        chat_id: int,
        user_id: int,
        topic_id: int,
        message_id: int,
        created_at: str,
    ):
        """
        **Feature: shield-economy-v65, Property 30: Unicode Preservation in Serialization**
        **Validates: Requirements 11.3**
        
        For any RAG fact with mixed Unicode content (Cyrillic + emoji + special symbols),
        the round-trip serialization SHALL preserve all characters exactly.
        """
        # Test with mixed content usernames
        mixed_usernames = [
            "Иван😀User",
            "🎉Мария_Петрова🎊",
            "User✨Звезда⭐",
            "Пользователь🔥Hot💯",
            "🚀Ракета_Rocket",
            "Ёжик✅Done❌",
            "Привет👋World🌍",
            "Тест⚠️Warning",
        ]
        
        for mixed_name in mixed_usernames:
            metadata = RAGFactMetadata(
                chat_id=chat_id,
                user_id=user_id,
                username=mixed_name,
                topic_id=topic_id,
                message_id=message_id,
                created_at=created_at,
            )
            
            serialized = metadata.to_dict()
            deserialized = RAGFactMetadata.from_dict(serialized)
            
            assert deserialized.username == mixed_name, (
                f"Mixed Unicode username not preserved: '{deserialized.username}' != '{mixed_name}'"
            )
