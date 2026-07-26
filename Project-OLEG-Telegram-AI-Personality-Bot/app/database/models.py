from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, Integer, String, DateTime, Boolean, ForeignKey, Text, UniqueConstraint, CheckConstraint, func, Float, LargeBinary, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base
from app.utils import utc_now


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    status: Mapped[str] = mapped_column(String(16), default='active', index=True)  # active, left
    # Fortress Update: Global reputation score
    reputation_score: Mapped[int] = mapped_column(Integer, default=1000)

    game: Mapped["GameStat"] = relationship(back_populates="user", uselist=False)
    user_achievements: Mapped[list["UserAchievement"]] = relationship(back_populates="user")
    user_quests: Mapped[list["UserQuest"]] = relationship(back_populates="user")
    guild_memberships: Mapped[list["GuildMember"]] = relationship(back_populates="user")
    question_history: Mapped[list["UserQuestionHistory"]] = relationship(back_populates="user")
    private_chat: Mapped["PrivateChat"] = relationship(back_populates="user", uselist=False)


class MessageLog(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    text: Mapped[Optional[str]] = mapped_column(Text)
    has_link: Mapped[bool] = mapped_column(Boolean, default=False)
    links: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # '\n' separated
    topic_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)  # ID топика в форуме
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class GameStat(Base):
    __tablename__ = "game_stats"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(64))

    size_cm: Mapped[int] = mapped_column(Integer, default=0)
    next_grow_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pvp_wins: Mapped[int] = mapped_column(Integer, default=0)
    pvp_losses: Mapped[int] = mapped_column(Integer, default=0)  # PP battle losses
    grow_count: Mapped[int] = mapped_column(Integer, default=0)
    casino_jackpots: Mapped[int] = mapped_column(Integer, default=0)
    reputation: Mapped[int] = mapped_column(Integer, default=0)
    # Fortress Update: ELO and League system
    elo_rating: Mapped[int] = mapped_column(Integer, default=1000)
    league: Mapped[str] = mapped_column(String(20), default='scrap')  # scrap, silicon, quantum, elite
    season_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    # Grand Casino v7.0: Growth history for sparkline (Requirements 7.4)
    # Stores last 7 days of growth data as JSON: [{"date": "2025-12-08", "size": 50, "change": 5}, ...]
    grow_history: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    
    # Game balance cooldowns (v8.0)
    last_cream_use: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_cockfight: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_energy_drink_use: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="game")


class Wallet(Base):
    __tablename__ = "wallets"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)


class Achievement(Base):
    __tablename__ = "achievements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)

    users: Mapped[list["UserAchievement"]] = relationship(back_populates="achievement")


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"), primary_key=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped["User"] = relationship(back_populates="user_achievements")
    achievement: Mapped["Achievement"] = relationship(back_populates="users")


# ============================================================================
# TRADING SYSTEM v9.5 - Trades, Market, Auctions
# ============================================================================


class Trade(Base):
    """
    P2P trade between two users (v9.5).
    
    Allows exchanging items and coins between players.
    Expires after 5 minutes if not accepted.
    """
    __tablename__ = "trades"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    to_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    
    # What the initiator offers
    offer_items: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: [{"item_type": "...", "quantity": 1, "item_data": "..."}]
    offer_coins: Mapped[int] = mapped_column(Integer, default=0)
    
    # What the initiator requests
    request_items: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    request_coins: Mapped[int] = mapped_column(Integer, default=0)
    
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending, accepted, rejected, cancelled, expired
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class MarketListing(Base):
    """
    Market listing for direct item sales (v9.5).
    
    Users can list items for sale at fixed prices.
    Anyone can purchase instantly.
    """
    __tablename__ = "market_listings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    
    # Item data (full item info as JSON)
    item_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: {"item_type": "...", "quantity": 1, "item_name": "...", "item_data": "..."}
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active, sold, cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    sold_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    buyer_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class Auction(Base):
    """
    Auction for bidding on items (v9.5).
    
    Users create auctions with start price and duration.
    Highest bidder wins when auction ends.
    """
    __tablename__ = "auctions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    
    # Item data (full item info as JSON)
    item_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    start_price: Mapped[int] = mapped_column(Integer, nullable=False)
    current_price: Mapped[int] = mapped_column(Integer, nullable=False)  # Current highest bid
    
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active, completed, cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    winner_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    bids: Mapped[list["AuctionBid"]] = relationship(back_populates="auction", cascade="all, delete-orphan")


class AuctionBid(Base):
    """
    Bid on an auction (v9.5).
    
    Tracks all bids made on auctions.
    """
    __tablename__ = "auction_bids"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id", ondelete="CASCADE"), nullable=False, index=True)
    bidder_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    auction: Mapped["Auction"] = relationship(back_populates="bids")


class Quest(Base):
    __tablename__ = "quests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    reward_type: Mapped[str] = mapped_column(String(64))
    reward_amount: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    target_value: Mapped[int] = mapped_column(Integer)

    users_quests: Mapped[list["UserQuest"]] = relationship(back_populates="quest")


class UserQuest(Base):
    __tablename__ = "user_quests"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="user_quests")
    quest: Mapped["Quest"] = relationship(back_populates="users_quests")


class Guild(Base):
    __tablename__ = "guilds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    owner: Mapped["User"] = relationship(foreign_keys=[owner_user_id])
    members: Mapped[list["GuildMember"]] = relationship(back_populates="guild")


class GuildMember(Base):
    __tablename__ = "guild_members"
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    role: Mapped[str] = mapped_column(String(64), default="member")

    guild: Mapped["Guild"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="guild_memberships")


class TeamWar(Base):
    __tablename__ = "team_wars"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    declarer_guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"))
    defender_guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="declared")
    winner_guild_id: Mapped[Optional[int]] = mapped_column(ForeignKey("guilds.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    declarer_guild: Mapped["Guild"] = relationship(foreign_keys=[declarer_guild_id])
    defender_guild: Mapped["Guild"] = relationship(foreign_keys=[defender_guild_id])
    winner_guild: Mapped[Optional["Guild"]] = relationship(foreign_keys=[winner_guild_id])
    participants: Mapped[list["TeamWarParticipant"]] = relationship(back_populates="team_war")


class TeamWarParticipant(Base):
    __tablename__ = "team_war_participants"
    team_war_id: Mapped[int] = mapped_column(ForeignKey("team_wars.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id")) # Guild at the time of participation
    score: Mapped[int] = mapped_column(Integer, default=0)
    kills: Mapped[int] = mapped_column(Integer, default=0)
    deaths: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    team_war: Mapped["TeamWar"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship() # One-way relationship
    guild: Mapped["Guild"] = relationship() # One-way relationship


class DuoTeam(Base):
    __tablename__ = "duo_teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user1_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user2_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user1: Mapped["User"] = relationship(foreign_keys=[user1_id])
    user2: Mapped["User"] = relationship(foreign_keys=[user2_id])
    stats: Mapped["DuoStat"] = relationship(back_populates="duo_team", uselist=False)

    __table_args__ = (
        UniqueConstraint('user1_id', 'user2_id', name='_user1_user2_uc'),
        CheckConstraint('user1_id < user2_id', name='_user1_lt_user2_cc')
    )


class DuoStat(Base):
    __tablename__ = "duo_stats"
    duo_team_id: Mapped[int] = mapped_column(ForeignKey("duo_teams.id"), primary_key=True)
    rating: Mapped[int] = mapped_column(Integer, default=1000) # Initial ELO rating
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    
    duo_team: Mapped["DuoTeam"] = relationship(back_populates="stats")


class GlobalStats(Base):
    __tablename__ = "global_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime, unique=True, index=True) # Date for the stats
    period_type: Mapped[str] = mapped_column(String(64)) # "daily", "weekly", "monthly"

    total_pvp_wins: Mapped[int] = mapped_column(Integer, default=0)
    pvp_wins_delta: Mapped[int] = mapped_column(Integer, default=0)

    total_grow_count: Mapped[int] = mapped_column(Integer, default=0)
    grow_count_delta: Mapped[int] = mapped_column(Integer, default=0)

    total_casino_jackpots: Mapped[int] = mapped_column(Integer, default=0)
    casino_jackpots_delta: Mapped[int] = mapped_column(Integer, default=0)

    total_reputation: Mapped[int] = mapped_column(Integer, default=0)
    reputation_delta: Mapped[int] = mapped_column(Integer, default=0)


class UserQuestionHistory(Base):
    __tablename__ = "user_question_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    asked_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped["User"] = relationship(back_populates="question_history")


class Quote(Base):
    """DEPRECATED: Removed in migration 042d107b23a8"""
    __tablename__ = "quotes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class QuoteVote(Base):
    """DEPRECATED: Removed in migration 042d107b23a8"""
    __tablename__ = "quote_votes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class StickerPack(Base):
    """DEPRECATED: Removed in migration 042d107b23a8"""
    __tablename__ = "sticker_packs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True) # Telegram Chat ID
    title: Mapped[str] = mapped_column(String(255))
    is_forum: Mapped[bool] = mapped_column(Boolean, default=False)

    summary_topic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    creative_topic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active_topic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Топик где бот активен
    auto_reply_chance: Mapped[float] = mapped_column(Float, default=0.0)  # Шанс текстового автоответа (0.0-1.0)
    voice_reply_chance: Mapped[float] = mapped_column(Float, default=0.0)  # Шанс голосового автоответа (0.0-1.0)
    video_reply_chance: Mapped[float] = mapped_column(Float, default=0.0)  # Шанс видео-автоответа (0.0-1.0)
    auto_reply_mode: Mapped[str] = mapped_column(String(20), default="text")  # text, voice, both (legacy/override)
    reactions_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # Включены ли реакции Олега
    persona: Mapped[str] = mapped_column(String(32), default="default")  # Персона Олега: default, oleg_legacy

    owner_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(20), default="moderator")  # 'owner', 'moderator'
    added_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Кто добавил
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PrivateChat(Base):
    __tablename__ = "private_chats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_user_id"), unique=True, index=True)
    message_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON для хранения контекста
    last_interaction: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    toxicity_level: Mapped[float] = mapped_column(Float, default=0.0)  # Уровень токсичности пользователя
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # Заблокирован ли пользователь

    user: Mapped["User"] = relationship(back_populates="private_chat", foreign_keys=[user_id])


class PendingVerification(Base):
    """Ожидающие верификации новых пользователей (Welcome 2.0)."""
    __tablename__ = "pending_verifications"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    welcome_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # ID сообщения с кнопкой
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)  # Когда истекает время на верификацию
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_kicked: Mapped[bool] = mapped_column(Boolean, default=False)


class GameChallenge(Base):
    """Вызов на PvP игру (Requirements 8.1, 8.2, 8.3, 8.4)."""
    __tablename__ = "game_challenges"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    challenger_id: Mapped[int] = mapped_column(BigInteger, index=True)
    target_id: Mapped[int] = mapped_column(BigInteger, index=True)
    game_type: Mapped[str] = mapped_column(String(32))  # pvp, roulette, coinflip
    bet_amount: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending, accepted, expired, cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)  # Timeout handling


class UserBalance(Base):
    """Баланс пользователя для игр (Requirements 10.1, 10.5)."""
    __tablename__ = "user_balances"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, default=100)  # Стартовый баланс
    total_won: Mapped[int] = mapped_column(Integer, default=0)
    total_lost: Mapped[int] = mapped_column(Integer, default=0)


# ============================================================================
# FORTRESS UPDATE v6.0 - New Models
# ============================================================================


class Tournament(Base):
    """Tournament tracking (Requirement 10.1)."""
    __tablename__ = "tournaments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(20), index=True)  # daily, weekly, grand_cup
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default='active', index=True)  # active, completed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    scores: Mapped[list["TournamentScore"]] = relationship(back_populates="tournament", cascade="all, delete-orphan")


class TournamentScore(Base):
    """Tournament scores per user per discipline (Requirement 10.1)."""
    __tablename__ = "tournament_scores"
    
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    discipline: Mapped[str] = mapped_column(String(20), primary_key=True)  # grow, pvp, roulette
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    
    tournament: Mapped["Tournament"] = relationship(back_populates="scores")


class UserElo(Base):
    """User ELO ratings for league system (Requirement 11.1)."""
    __tablename__ = "user_elo"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    elo: Mapped[int] = mapped_column(Integer, default=1000, index=True)
    league: Mapped[str] = mapped_column(String(20), default='scrap', index=True)  # scrap, silicon, quantum, elite
    season_wins: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class NotificationConfig(Base):
    """Owner notification settings per chat (Requirement 15.8)."""
    __tablename__ = "notification_configs"
    
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    daily_tips: Mapped[bool] = mapped_column(Boolean, default=True)


class SecurityBlacklist(Base):
    """Security blacklist for abuse prevention (Requirement 17.7)."""
    __tablename__ = "security_blacklist"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    blacklisted_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class DailiesConfig(Base):
    """
    Dailies configuration per chat (Requirements 13.4, 13.5).
    
    Stores settings for daily scheduled messages including:
    - Morning summary enabled/disabled
    - Evening quote enabled/disabled
    - Evening stats enabled/disabled
    """
    __tablename__ = "dailies_configs"
    
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    summary_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # Morning summary
    quote_enabled: Mapped[bool] = mapped_column(Boolean, default=True)    # Evening quote
    stats_enabled: Mapped[bool] = mapped_column(Boolean, default=True)    # Evening stats
    summary_time_hour: Mapped[int] = mapped_column(Integer, default=9)    # 09:00 Moscow
    quote_time_hour: Mapped[int] = mapped_column(Integer, default=21)     # 21:00 Moscow
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class BotConfig(Base):
    """
    Bot behavior configuration per chat.
    
    Controls auto-reply chance and feature toggles.
    """
    __tablename__ = "bot_configs"
    
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    
    # Автоответ (0-100%)
    auto_reply_chance: Mapped[int] = mapped_column(Integer, default=5)  # 5% по умолчанию
    
    # Функции бота
    quotes_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # /q команда
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True)   # Распознавание голоса
    vision_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # Анализ картинок
    games_enabled: Mapped[bool] = mapped_column(Boolean, default=True)   # Игровые команды
    
    # Время на принятие вызова в PvP/ПП (в секундах)
    pvp_accept_timeout: Mapped[int] = mapped_column(Integer, default=120)  # 2 минуты по умолчанию
    
    # Персона бота: "oleg" (дерзкий) или "dude" (расслабленный The Dude)
    persona: Mapped[str] = mapped_column(String(20), default="oleg")
    
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


# ============================================================================
# SHIELD & ECONOMY v6.5 - New Models
# ============================================================================


class UserEnergy(Base):
    """
    Personal energy system for LLM request limiting (Requirements 1.1, 1.2, 1.3, 1.4).
    
    Each user has an energy counter (0-3) that decrements on rapid requests.
    When energy reaches 0, user enters cooldown period.
    Energy resets after 60 seconds of inactivity.
    """
    __tablename__ = "user_energy"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    energy: Mapped[int] = mapped_column(Integer, default=3)  # 0-3, starts at 3
    last_request: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_energy'),
    )


class ChatRateLimitConfig(Base):
    """
    Global chat rate limit configuration (Requirements 2.1, 2.3).
    
    Configures the maximum LLM requests per minute for each chat.
    Default limit is 20 requests per minute.
    """
    __tablename__ = "chat_rate_limit_config"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    llm_requests_per_minute: Mapped[int] = mapped_column(Integer, default=20)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


# ============================================================================
# GAMES v7.5 - New Models for Economy and Inventory
# ============================================================================


class CockfightStats(Base):
    """
    Cockfight statistics per user (v7.5).
    
    Tracks cockfight wins, losses, and owned roosters.
    """
    __tablename__ = "cockfight_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    total_earnings: Mapped[int] = mapped_column(Integer, default=0)
    owned_roosters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of rooster types
    
    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_cockfight'),
    )


class GameHistory(Base):
    """
    Game history for tracking all game results (v7.5).
    
    Stores history of all games played for statistics and leaderboards.
    """
    __tablename__ = "game_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    game_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    bet_amount: Mapped[int] = mapped_column(Integer, default=0)
    result_amount: Mapped[int] = mapped_column(Integer, default=0)  # Positive = win, negative = loss
    won: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON with game-specific details
    played_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


# ============================================================================
# INVENTORY & FISHING SYSTEM v7.5.1
# ============================================================================


class UserInventory(Base):
    """
    User inventory for items from lootboxes and shop.
    
    Stores items like fishing rods, lucky charms, shields, etc.
    """
    __tablename__ = "user_inventory"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    item_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON for item-specific data
    acquired_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', 'item_type', name='uq_user_chat_item'),
    )


class FishingStats(Base):
    """
    Fishing statistics per user.
    
    Tracks fish caught by rarity, total earnings, equipped rod, etc.
    """
    __tablename__ = "fishing_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    
    # Fish caught by rarity
    trash_caught: Mapped[int] = mapped_column(Integer, default=0)
    common_caught: Mapped[int] = mapped_column(Integer, default=0)
    uncommon_caught: Mapped[int] = mapped_column(Integer, default=0)
    rare_caught: Mapped[int] = mapped_column(Integer, default=0)
    epic_caught: Mapped[int] = mapped_column(Integer, default=0)
    legendary_caught: Mapped[int] = mapped_column(Integer, default=0)
    
    # Totals
    total_casts: Mapped[int] = mapped_column(Integer, default=0)
    total_earnings: Mapped[int] = mapped_column(Integer, default=0)
    biggest_catch_value: Mapped[int] = mapped_column(Integer, default=0)
    biggest_catch_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Equipped rod (item_type from inventory)
    equipped_rod: Mapped[str] = mapped_column(String(64), default="basic_rod")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_fishing'),
    )


# ============================================================================
# SDOC INTEGRATION - Олег как резидент Steam Deck OC
# ============================================================================


class GroupAdmin(Base):
    """
    Админы/приписочники группы SDOC.
    
    Синхронизируется с Telegram API getChatAdministrators.
    Олег знает их по именам и может упоминать в разговоре.
    """
    __tablename__ = "group_admins"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # Кастомный титул в группе
    role: Mapped[str] = mapped_column(String(20), default="administrator")  # creator, administrator
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    
    __table_args__ = (
        UniqueConstraint('chat_id', 'user_id', name='uq_chat_admin'),
    )


class GroupMeme(Base):
    """
    Локальные мемы и приколы группы.
    
    Олег собирает их из чата и может использовать в разговоре.
    Примеры: "Синица с яйцами", "Иваново", местные шутки.
    """
    __tablename__ = "group_memes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    meme_type: Mapped[str] = mapped_column(String(32), index=True)  # quote, joke, reference, nickname
    content: Mapped[str] = mapped_column(Text)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Контекст/объяснение
    author_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Кто автор
    author_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)  # Сколько раз Олег использовал
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    __table_args__ = (
        UniqueConstraint('chat_id', 'content', name='uq_chat_meme_content'),
    )


class SDOCTopic(Base):
    """
    Топики группы SDOC.
    
    Олег знает структуру группы и может направлять людей в нужные топики.
    """
    __tablename__ = "sdoc_topics"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, index=True)  # message_thread_id
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(32), default="general")  # tech, fun, trade, meta
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON список ключевых слов
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    __table_args__ = (
        UniqueConstraint('chat_id', 'topic_id', name='uq_chat_topic'),
    )


# ============================================================================
# MARRIAGE SYSTEM v8.0 - Requirements 9.1-9.6
# ============================================================================


class Marriage(Base):
    """
    Marriage between two users in a chat (Requirements 9.1, 9.2).
    
    Stores active and divorced marriages.
    user1_id is always < user2_id to ensure uniqueness.
    """
    __tablename__ = "marriages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user1_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user2_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    married_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    divorced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('user1_id', 'user2_id', 'chat_id', name='uq_marriage_users_chat'),
        CheckConstraint('user1_id < user2_id', name='ck_marriage_user_order'),
    )


class MarriageProposal(Base):
    """
    Marriage proposal between users (Requirements 9.1, 9.3, 9.4).
    
    Proposals expire after 5 minutes if not accepted/rejected.
    """
    __tablename__ = "marriage_proposals"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    to_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending, accepted, rejected, expired
    
    __table_args__ = (
        UniqueConstraint('from_user_id', 'to_user_id', 'chat_id', 'status', name='uq_proposal_pending'),
    )


# ============================================================================
# MAFIA GAME v9.5.0 - Cooperative Social Deduction Game
# ============================================================================


class MafiaGame(Base):
    """
    Mafia game session (v9.5.0).
    
    Tracks the state of an active or completed mafia game.
    Phases: lobby -> night -> day_discussion -> day_voting -> (repeat) -> finished
    """
    __tablename__ = "mafia_games"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="lobby", index=True)  # lobby, night, day_discussion, day_voting, finished
    phase_number: Mapped[int] = mapped_column(Integer, default=0)  # Current round number
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    winner: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # mafia, citizens, None
    phase_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # When current phase started
    
    players: Mapped[list["MafiaPlayer"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    night_actions: Mapped[list["MafiaNightAction"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    votes: Mapped[list["MafiaVote"]] = relationship(back_populates="game", cascade="all, delete-orphan")


class MafiaPlayer(Base):
    """
    Player in a mafia game (v9.5.0).
    
    Stores role, alive status, and death information.
    """
    __tablename__ = "mafia_players"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("mafia_games.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # citizen, mafia, doctor, detective, don
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    death_phase: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Phase number when died
    death_reason: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # killed, lynched
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    game: Mapped["MafiaGame"] = relationship(back_populates="players")
    
    __table_args__ = (
        UniqueConstraint('game_id', 'user_id', name='uq_mafia_game_user'),
    )


class MafiaNightAction(Base):
    """
    Night action in mafia game (v9.5.0).
    
    Tracks actions taken during night phase (kill, heal, check).
    """
    __tablename__ = "mafia_night_actions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("mafia_games.id", ondelete="CASCADE"), nullable=False, index=True)
    phase_number: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)  # Who performs action
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)  # kill, heal, check
    target_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Target of action
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    game: Mapped["MafiaGame"] = relationship(back_populates="night_actions")
    
    __table_args__ = (
        UniqueConstraint('game_id', 'phase_number', 'user_id', name='uq_mafia_night_action'),
    )


class MafiaVote(Base):
    """
    Day voting in mafia game (v9.5.0).
    
    Tracks votes during day phase for lynching suspects.
    """
    __tablename__ = "mafia_votes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("mafia_games.id", ondelete="CASCADE"), nullable=False, index=True)
    phase_number: Mapped[int] = mapped_column(Integer, nullable=False)
    voter_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    game: Mapped["MafiaGame"] = relationship(back_populates="votes")
    
    __table_args__ = (
        UniqueConstraint('game_id', 'phase_number', 'voter_id', name='uq_mafia_vote'),
    )


class MafiaStats(Base):
    """
    Mafia game statistics per user (v9.5.0).
    
    Tracks wins, losses, and role-specific stats.
    """
    __tablename__ = "mafia_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    
    # Overall stats
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    games_won: Mapped[int] = mapped_column(Integer, default=0)
    games_survived: Mapped[int] = mapped_column(Integer, default=0)  # Survived to end
    
    # Role-specific stats
    mafia_wins: Mapped[int] = mapped_column(Integer, default=0)
    mafia_games: Mapped[int] = mapped_column(Integer, default=0)
    citizen_wins: Mapped[int] = mapped_column(Integer, default=0)
    citizen_games: Mapped[int] = mapped_column(Integer, default=0)
    detective_checks: Mapped[int] = mapped_column(Integer, default=0)  # Successful mafia detections
    detective_games: Mapped[int] = mapped_column(Integer, default=0)
    doctor_saves: Mapped[int] = mapped_column(Integer, default=0)  # Successful saves
    doctor_games: Mapped[int] = mapped_column(Integer, default=0)
    
    # Voting accuracy
    correct_votes: Mapped[int] = mapped_column(Integer, default=0)  # Voted for mafia
    total_votes: Mapped[int] = mapped_column(Integer, default=0)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', name='uq_mafia_user_chat_stats'),
    )


class GlobalEvent(Base):
    """
    Global dynamic events (Requirements 18.1).
    
    Stores active/historical AI-generated events.
    """
    __tablename__ = "global_events"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(20), index=True)  # weekly, daily
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    lore: Mapped[str] = mapped_column(Text)
    modifiers: Mapped[str] = mapped_column(Text)  # JSON list of modifiers
    
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
