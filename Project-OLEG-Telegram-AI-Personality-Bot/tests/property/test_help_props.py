"""
Property-based tests for Help command context differentiation.

**Feature: oleg-commands-fix, Property 4: Help context differentiation**
**Validates: Requirements 4.1, 4.2**
"""

import os
import re
from hypothesis import given, strategies as st, settings


# ============================================================================
# Extract help texts and function from help.py without importing aiogram
# ============================================================================

def _load_help_texts():
    """Load help texts from help.py by parsing the file directly.
    
    The new help.py uses multiple section constants instead of two main texts.
    We combine them to create equivalent group and private help texts.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    help_file = os.path.join(project_root, 'app', 'handlers', 'help.py')
    
    with open(help_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract all help section constants
    sections = {}
    section_names = ['HELP_INTRO', 'HELP_FEATURES', 'HELP_GAMES', 'HELP_MODERATION', 
                     'HELP_QUOTES', 'HELP_SOCIAL', 'HELP_ADMIN', 'HELP_PRIVATE']
    
    for name in section_names:
        # Match triple-quoted strings (both """ and ''')
        pattern = rf'{name}\s*=\s*"""(.*?)"""'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            pattern = rf"{name}\s*=\s*'''(.*?)'''"
            match = re.search(pattern, content, re.DOTALL)
        if match:
            sections[name] = match.group(1)
    
    # Build group help text (combines intro + all sections except private)
    group_text = sections.get('HELP_INTRO', '') + sections.get('HELP_FEATURES', '') + \
                 sections.get('HELP_GAMES', '') + sections.get('HELP_MODERATION', '') + \
                 sections.get('HELP_QUOTES', '') + sections.get('HELP_SOCIAL', '') + \
                 sections.get('HELP_ADMIN', '')
    
    # Private help text
    private_text = sections.get('HELP_PRIVATE', '')
    
    if not group_text or not private_text:
        raise ValueError("Could not extract help texts from help.py")
    
    return group_text, private_text


HELP_TEXT_GROUP, HELP_TEXT_PRIVATE = _load_help_texts()


def get_help_text(chat_type: str, bot_username: str = "@bot") -> str:
    """
    Get appropriate help text based on chat type.
    
    This mirrors the function in app/handlers/help.py for testing purposes.
    """
    if chat_type == "private":
        return HELP_TEXT_PRIVATE
    else:
        return HELP_TEXT_GROUP.format(bot_username=bot_username)


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for group chat types
group_chat_types = st.sampled_from(["group", "supergroup"])

# Strategy for private chat type
private_chat_type = st.just("private")

# Strategy for any chat type
any_chat_type = st.sampled_from(["private", "group", "supergroup"])

# Strategy for bot usernames
bot_usernames = st.from_regex(r"@[a-zA-Z][a-zA-Z0-9_]{4,31}", fullmatch=True)


# ============================================================================
# Property 4: Help context differentiation
# ============================================================================

class TestHelpContextDifferentiation:
    """
    **Feature: oleg-commands-fix, Property 4: Help context differentiation**
    **Validates: Requirements 4.1, 4.2**
    
    For any help request, the response content SHALL differ based on chat type 
    (private vs group), with private help containing "admin" and group help 
    containing game commands.
    """
    
    @settings(max_examples=100)
    @given(chat_type=private_chat_type)
    def test_property_4_private_help_contains_admin(self, chat_type: str):
        """
        **Feature: oleg-commands-fix, Property 4: Help context differentiation**
        **Validates: Requirements 4.1, 4.2**
        
        For any private chat, help text SHALL contain admin panel reference.
        """
        help_text = get_help_text(chat_type)
        
        # Private help must contain admin command reference
        assert "/admin" in help_text, "Private help must contain /admin command"
        assert "Админ-панель" in help_text, "Private help must mention admin panel"
    
    @settings(max_examples=100)
    @given(chat_type=group_chat_types, bot_username=bot_usernames)
    def test_property_4_group_help_contains_games(self, chat_type: str, bot_username: str):
        """
        **Feature: oleg-commands-fix, Property 4: Help context differentiation**
        **Validates: Requirements 4.1, 4.2**
        
        For any group chat, help text SHALL contain game commands.
        """
        help_text = get_help_text(chat_type, bot_username)
        
        # Group help must contain game commands
        assert "/games" in help_text, "Group help must contain /games command"
        assert "/grow" in help_text, "Group help must contain /grow command"
        assert "/challenge" in help_text, "Group help must contain /challenge command"
        assert "/casino" in help_text, "Group help must contain /casino command"
    
    @settings(max_examples=100)
    @given(chat_type=group_chat_types, bot_username=bot_usernames)
    def test_property_4_group_help_contains_moderation(self, chat_type: str, bot_username: str):
        """
        **Feature: oleg-commands-fix, Property 4: Help context differentiation**
        **Validates: Requirements 4.1, 4.2**
        
        For any group chat, help text SHALL contain moderation commands.
        """
        help_text = get_help_text(chat_type, bot_username)
        
        # Group help must contain moderation commands
        assert "бан" in help_text.lower(), "Group help must contain ban command"
        assert "мут" in help_text.lower(), "Group help must contain mute command"
        assert "/warn" in help_text, "Group help must contain /warn command"
    
    @settings(max_examples=100)
    @given(bot_username=bot_usernames)
    def test_property_4_private_and_group_differ(self, bot_username: str):
        """
        **Feature: oleg-commands-fix, Property 4: Help context differentiation**
        **Validates: Requirements 4.1, 4.2**
        
        Private and group help texts SHALL be different.
        """
        private_help = get_help_text("private")
        group_help = get_help_text("group", bot_username)
        
        # Help texts must be different
        assert private_help != group_help, "Private and group help must differ"
    
    @settings(max_examples=100)
    @given(chat_type=private_chat_type)
    def test_private_help_contains_reset(self, chat_type: str):
        """
        Property: Private help contains reset command.
        """
        help_text = get_help_text(chat_type)
        
        assert "/reset" in help_text, "Private help must contain /reset command"
    
    @settings(max_examples=100)
    @given(chat_type=group_chat_types, bot_username=bot_usernames)
    def test_group_help_contains_guilds(self, chat_type: str, bot_username: str):
        """
        Property: Group help contains guild commands.
        """
        help_text = get_help_text(chat_type, bot_username)
        
        assert "/create_guild" in help_text, "Group help must contain guild commands"
        assert "/guild_info" in help_text, "Group help must contain guild info command"
    
    @settings(max_examples=100)
    @given(chat_type=any_chat_type)
    def test_help_always_returns_string(self, chat_type: str):
        """
        Property: get_help_text always returns a non-empty string.
        """
        help_text = get_help_text(chat_type)
        
        assert isinstance(help_text, str), "Help text must be a string"
        assert len(help_text) > 0, "Help text must not be empty"
    
    @settings(max_examples=100)
    @given(chat_type=any_chat_type)
    def test_help_contains_basic_commands(self, chat_type: str):
        """
        Property: All help texts contain basic commands.
        """
        help_text = get_help_text(chat_type)
        
        # Both contexts should have /say command (common to both)
        assert "/say" in help_text, "Help text must contain /say command"
        # Both contexts should have /admin command
        assert "/admin" in help_text, "Help text must contain /admin command"
    
    def test_supergroup_uses_group_help(self):
        """
        Property: Supergroup chat type uses group help text.
        """
        group_help = get_help_text("group", "@testbot")
        supergroup_help = get_help_text("supergroup", "@testbot")
        
        # Supergroup should get the same help as group
        assert group_help == supergroup_help, "Supergroup should use group help"
    
    def test_unknown_chat_type_uses_group_help(self):
        """
        Property: Unknown chat types default to group help.
        """
        group_help = get_help_text("group", "@testbot")
        unknown_help = get_help_text("channel", "@testbot")
        
        # Unknown types should default to group help
        assert group_help == unknown_help, "Unknown chat type should use group help"
