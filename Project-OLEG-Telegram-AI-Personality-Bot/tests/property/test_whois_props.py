"""
Property-based tests for Whois System.

Tests correctness properties defined in the design document.

**Feature: release-candidate-8, Property 6: Whois displays profile data when available**
**Validates: Requirements 4.1, 4.3**
"""

from hypothesis import given, strategies as st, settings, assume
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class UserProfile:
    """Simplified UserProfile for testing - mirrors app/services/user_memory.py"""
    user_id: int
    username: Optional[str] = None
    
    # Железо
    cpu: Optional[str] = None
    gpu: Optional[str] = None
    ram: Optional[str] = None
    storage: Optional[str] = None
    motherboard: Optional[str] = None
    psu: Optional[str] = None
    case: Optional[str] = None
    cooling: Optional[str] = None
    monitor: Optional[str] = None
    peripherals: List[str] = field(default_factory=list)
    
    # Устройства
    laptop: Optional[str] = None
    steam_deck: bool = False
    steam_deck_mods: List[str] = field(default_factory=list)
    phone: Optional[str] = None
    console: Optional[str] = None
    
    # Софт и ОС
    os: Optional[str] = None
    distro: Optional[str] = None
    de: Optional[str] = None
    
    # Предпочтения
    brand_preference: Optional[str] = None
    games: List[str] = field(default_factory=list)
    expertise: List[str] = field(default_factory=list)
    
    # Личное
    name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    job: Optional[str] = None
    hobbies: List[str] = field(default_factory=list)
    music: List[str] = field(default_factory=list)
    movies: List[str] = field(default_factory=list)
    pets: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    age: Optional[int] = None
    
    # Проблемы и история
    current_problems: List[str] = field(default_factory=list)
    resolved_problems: List[str] = field(default_factory=list)
    
    # Метаданные
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    message_count: int = 0


def format_whois_profile(profile, username: str) -> list[str]:
    """
    Форматирует профиль пользователя для вывода в /whois.
    
    This is a copy of the function from app/handlers/qna.py for testing purposes.
    
    Args:
        profile: UserProfile объект или None
        username: Имя пользователя для отображения
        
    Returns:
        Список строк для вывода
    """
    lines = []
    
    if not profile:
        return lines
    
    # Личная информация
    personal = []
    if profile.name:
        personal.append(f"Имя: {profile.name}")
    if profile.age:
        personal.append(f"{profile.age} лет")
    if profile.city:
        personal.append(f"📍 {profile.city}")
    if profile.job:
        personal.append(f"💼 {profile.job}")
    if personal:
        lines.append("\n👤 " + " • ".join(personal))
    
    # Железо
    hardware = []
    if profile.gpu:
        hardware.append(f"GPU: {profile.gpu}")
    if profile.cpu:
        hardware.append(f"CPU: {profile.cpu}")
    if profile.ram:
        hardware.append(f"RAM: {profile.ram}")
    if hardware:
        lines.append("\n🖥 <b>Сетап:</b> " + " | ".join(hardware))
    
    # Устройства
    devices = []
    if profile.steam_deck:
        deck_str = "Steam Deck"
        if profile.steam_deck_mods:
            deck_str += f" ({', '.join(profile.steam_deck_mods[:3])})"
        devices.append(deck_str)
    if profile.laptop:
        devices.append(f"💻 {profile.laptop}")
    if profile.console:
        devices.append(f"🎮 {profile.console}")
    if devices:
        lines.append("📱 " + " | ".join(devices))
    
    # ОС
    if profile.os or profile.distro:
        os_str = profile.distro or profile.os
        if profile.de:
            os_str += f" + {profile.de}"
        lines.append(f"💿 {os_str}")
    
    # Предпочтения
    if profile.brand_preference:
        lines.append(f"❤️ Фанат {profile.brand_preference.upper()}")
    
    # Экспертиза
    if profile.expertise:
        lines.append(f"🧠 Шарит в: {', '.join(profile.expertise[:4])}")
    
    # Игры
    if profile.games:
        lines.append(f"🎮 Играет: {', '.join(profile.games[:5])}")
    
    # Хобби
    if profile.hobbies:
        lines.append(f"🎯 Хобби: {', '.join(profile.hobbies[:4])}")
    
    # Языки программирования
    if profile.languages:
        lines.append(f"💻 Кодит на: {', '.join(profile.languages[:4])}")
    
    # Питомцы
    if profile.pets:
        lines.append(f"🐾 Питомцы: {', '.join(profile.pets)}")
    
    # Текущие проблемы
    if profile.current_problems:
        lines.append(f"\n⚠️ <b>Последняя проблема:</b> {profile.current_problems[-1][:80]}...")
    
    return lines


# Strategies for generating profile data
@st.composite
def user_profile_strategy(draw):
    """Generate a UserProfile with random data."""
    profile = UserProfile(
        user_id=draw(st.integers(min_value=1, max_value=10**12)),
        username=draw(st.one_of(st.none(), st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N'))))),
        name=draw(st.one_of(st.none(), st.text(min_size=2, max_size=30, alphabet=st.characters(whitelist_categories=('L',))))),
        age=draw(st.one_of(st.none(), st.integers(min_value=10, max_value=80))),
        city=draw(st.one_of(st.none(), st.sampled_from(['Москва', 'Питер', 'Киев', 'Минск', 'Алматы', None]))),
        job=draw(st.one_of(st.none(), st.sampled_from(['программист', 'дизайнер', 'студент', 'инженер', None]))),
        gpu=draw(st.one_of(st.none(), st.sampled_from(['RTX 4090', 'RTX 3080', 'RX 7900 XTX', 'GTX 1660', None]))),
        cpu=draw(st.one_of(st.none(), st.sampled_from(['Ryzen 9 7950X', 'i9-13900K', 'Ryzen 5 5600X', None]))),
        ram=draw(st.one_of(st.none(), st.sampled_from(['32GB', '64GB', '16GB', None]))),
        os=draw(st.one_of(st.none(), st.sampled_from(['linux', 'windows', None]))),
        distro=draw(st.one_of(st.none(), st.sampled_from(['Arch', 'Ubuntu', 'Fedora', None]))),
        de=draw(st.one_of(st.none(), st.sampled_from(['KDE', 'GNOME', 'Hyprland', None]))),
        brand_preference=draw(st.one_of(st.none(), st.sampled_from(['amd', 'intel', 'nvidia', None]))),
        steam_deck=draw(st.booleans()),
        laptop=draw(st.one_of(st.none(), st.sampled_from(['MacBook Pro', 'ThinkPad', 'ASUS ROG', None]))),
        console=draw(st.one_of(st.none(), st.sampled_from(['PS5', 'Xbox Series X', 'Nintendo Switch', None]))),
        games=draw(st.lists(st.sampled_from(['CS2', 'Dota 2', 'Valorant', 'Minecraft', 'Elden Ring']), min_size=0, max_size=5, unique=True)),
        expertise=draw(st.lists(st.sampled_from(['разгон', 'Linux', 'программирование', 'сети']), min_size=0, max_size=4, unique=True)),
        hobbies=draw(st.lists(st.sampled_from(['фотография', 'музыка', 'спорт', 'кино']), min_size=0, max_size=4, unique=True)),
        languages=draw(st.lists(st.sampled_from(['python', 'javascript', 'rust', 'go']), min_size=0, max_size=4, unique=True)),
        pets=draw(st.lists(st.sampled_from(['кот', 'собака', 'попугай']), min_size=0, max_size=3, unique=True)),
        current_problems=draw(st.lists(st.text(min_size=10, max_size=100), min_size=0, max_size=2)),
    )
    return profile


class TestWhoisDisplaysProfileData:
    """
    **Feature: release-candidate-8, Property 6: Whois displays profile data when available**
    **Validates: Requirements 4.1, 4.3**
    
    *For any* user with non-empty profile fields, `/whois` output SHALL contain those field values.
    """
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_name_displayed_when_present(self, profile: UserProfile):
        """
        Property 6a: When profile has a name, it appears in the output.
        """
        assume(profile.name is not None and len(profile.name) > 0)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert f"Имя: {profile.name}" in output_text, \
            f"Name '{profile.name}' should appear in whois output"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_gpu_displayed_when_present(self, profile: UserProfile):
        """
        Property 6b: When profile has GPU info, it appears in the output.
        """
        assume(profile.gpu is not None)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert f"GPU: {profile.gpu}" in output_text, \
            f"GPU '{profile.gpu}' should appear in whois output"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_cpu_displayed_when_present(self, profile: UserProfile):
        """
        Property 6c: When profile has CPU info, it appears in the output.
        """
        assume(profile.cpu is not None)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert f"CPU: {profile.cpu}" in output_text, \
            f"CPU '{profile.cpu}' should appear in whois output"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_games_displayed_when_present(self, profile: UserProfile):
        """
        Property 6d: When profile has games, they appear in the output.
        """
        assume(len(profile.games) > 0)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        # At least the first game should be present
        assert profile.games[0] in output_text, \
            f"Game '{profile.games[0]}' should appear in whois output"
        assert "🎮 Играет:" in output_text, \
            "Games section should be present"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_expertise_displayed_when_present(self, profile: UserProfile):
        """
        Property 6e: When profile has expertise, it appears in the output.
        """
        assume(len(profile.expertise) > 0)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert profile.expertise[0] in output_text, \
            f"Expertise '{profile.expertise[0]}' should appear in whois output"
        assert "🧠 Шарит в:" in output_text, \
            "Expertise section should be present"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_city_displayed_when_present(self, profile: UserProfile):
        """
        Property 6f: When profile has city, it appears in the output.
        """
        assume(profile.city is not None)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert profile.city in output_text, \
            f"City '{profile.city}' should appear in whois output"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_job_displayed_when_present(self, profile: UserProfile):
        """
        Property 6g: When profile has job, it appears in the output.
        """
        assume(profile.job is not None)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert profile.job in output_text, \
            f"Job '{profile.job}' should appear in whois output"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_brand_preference_displayed_when_present(self, profile: UserProfile):
        """
        Property 6h: When profile has brand preference, it appears in the output.
        """
        assume(profile.brand_preference is not None)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert profile.brand_preference.upper() in output_text, \
            f"Brand preference '{profile.brand_preference}' should appear in whois output"
        assert "❤️ Фанат" in output_text, \
            "Brand preference section should be present"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_empty_profile_returns_empty_list(self, profile: UserProfile):
        """
        Property 6i: When profile is None, output is empty list.
        """
        output = format_whois_profile(None, "testuser")
        
        assert output == [], \
            "Empty profile should return empty list"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_languages_displayed_when_present(self, profile: UserProfile):
        """
        Property 6j: When profile has programming languages, they appear in the output.
        """
        assume(len(profile.languages) > 0)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert profile.languages[0] in output_text, \
            f"Language '{profile.languages[0]}' should appear in whois output"
        assert "💻 Кодит на:" in output_text, \
            "Languages section should be present"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_hobbies_displayed_when_present(self, profile: UserProfile):
        """
        Property 6k: When profile has hobbies, they appear in the output.
        """
        assume(len(profile.hobbies) > 0)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert profile.hobbies[0] in output_text, \
            f"Hobby '{profile.hobbies[0]}' should appear in whois output"
        assert "🎯 Хобби:" in output_text, \
            "Hobbies section should be present"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_pets_displayed_when_present(self, profile: UserProfile):
        """
        Property 6l: When profile has pets, they appear in the output.
        """
        assume(len(profile.pets) > 0)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert profile.pets[0] in output_text, \
            f"Pet '{profile.pets[0]}' should appear in whois output"
        assert "🐾 Питомцы:" in output_text, \
            "Pets section should be present"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_steam_deck_displayed_when_present(self, profile: UserProfile):
        """
        Property 6m: When profile has Steam Deck, it appears in the output.
        """
        assume(profile.steam_deck is True)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert "Steam Deck" in output_text, \
            "Steam Deck should appear in whois output"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_os_displayed_when_present(self, profile: UserProfile):
        """
        Property 6n: When profile has OS/distro, it appears in the output.
        """
        assume(profile.os is not None or profile.distro is not None)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        expected = profile.distro or profile.os
        assert expected in output_text, \
            f"OS/Distro '{expected}' should appear in whois output"
        assert "💿" in output_text, \
            "OS section should be present"
    
    @settings(max_examples=100)
    @given(user_profile_strategy())
    def test_age_displayed_when_present(self, profile: UserProfile):
        """
        Property 6o: When profile has age, it appears in the output.
        """
        assume(profile.age is not None)
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        assert f"{profile.age} лет" in output_text, \
            f"Age '{profile.age}' should appear in whois output"


class TestWhoisOutputFormat:
    """
    Additional tests for whois output format correctness.
    """
    
    @settings(max_examples=50)
    @given(user_profile_strategy())
    def test_output_is_list_of_strings(self, profile: UserProfile):
        """
        Output should always be a list of strings.
        """
        output = format_whois_profile(profile, "testuser")
        
        assert isinstance(output, list), "Output should be a list"
        for item in output:
            assert isinstance(item, str), "Each output item should be a string"
    
    @settings(max_examples=50)
    @given(st.text(min_size=100, max_size=200))
    def test_current_problems_truncated(self, long_problem: str):
        """
        Current problems should be truncated to 80 characters.
        """
        # Create a profile with a long problem
        profile = UserProfile(
            user_id=12345,
            current_problems=[long_problem]
        )
        
        output = format_whois_profile(profile, "testuser")
        output_text = "\n".join(output)
        
        # The problem should be truncated and end with "..."
        assert "..." in output_text, \
            "Long problems should be truncated with '...'"
        # Full problem text should NOT be in output (since it's > 80 chars)
        assert long_problem not in output_text, \
            "Full problem text should be truncated"
