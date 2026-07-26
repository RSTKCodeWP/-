"""
Authentication and User Management
Multi-user support infrastructure
"""

import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

#: PBKDF2 work factor. High enough to make offline cracking expensive, low
#: enough to keep a login well under a tenth of a second.
PBKDF2_ITERATIONS = 260_000
PBKDF2_ALGORITHM = "pbkdf2_sha256"


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    """
    Derive a storable password hash.

    Uses PBKDF2-HMAC-SHA256 with a random per-user salt. Plain SHA-256 was used
    before: unsalted and fast by design, so a stolen store could be attacked
    with rainbow tables or brute forced at enormous rates.
    """
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{PBKDF2_ALGORITHM}${iterations}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: Optional[str]) -> tuple[bool, bool]:
    """
    Check a password against a stored hash.

    Returns ``(is_valid, needs_upgrade)``. Legacy unsalted SHA-256 hashes are
    still accepted so existing accounts keep working, and are flagged for
    rehashing on the next successful login.
    """
    if not stored:
        return False, False

    parts = stored.split("$")

    if len(parts) == 4 and parts[0] == PBKDF2_ALGORITHM:
        _, raw_iterations, salt_hex, expected = parts
        try:
            iterations = int(raw_iterations)
            salt = bytes.fromhex(salt_hex)
        except ValueError:
            return False, False
        derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
        # Constant-time: a plain != leaks how much of the digest matched.
        return hmac.compare_digest(derived.hex(), expected), False

    # Legacy: bare hex digest of an unsalted SHA-256.
    legacy = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(legacy, stored), True



class User:
    """User model"""

    def __init__(
        self,
        user_id: str,
        username: str,
        email: str,
        role: str = "user",
        created_at: Optional[str] = None
    ):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.role = role  # 'admin', 'user', 'viewer'
        self.created_at = created_at or datetime.now().isoformat()
        self.last_login: Optional[str] = None
        self.is_active = True

    def to_dict(self) -> Dict:
        """
        Public representation, safe to return from the API.

        Deliberately excludes the password hash: this is what /api/auth/me and
        the user list return.
        """
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "is_active": self.is_active,
        }

    def to_record(self) -> Dict:
        """
        Full representation for on-disk storage.

        Persistence used to go through to_dict(), which omits the password
        hash, so hashes were never written. Every account was locked out after
        a restart, with no reset path.
        """
        record = self.to_dict()
        record["password_hash"] = getattr(self, "_password_hash", None)
        return record

    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        """Create from dictionary"""
        user = cls(
            user_id=data["user_id"],
            username=data["username"],
            email=data["email"],
            role=data.get("role", "user"),
            created_at=data.get("created_at")
        )
        user.last_login = data.get("last_login")
        user.is_active = data.get("is_active", True)
        user._password_hash = data.get("password_hash")
        return user


class Session:
    """User session"""

    def __init__(self, session_id: str, user_id: str, expires_at: datetime):
        self.session_id = session_id
        self.user_id = user_id
        self.created_at = datetime.now()
        self.expires_at = expires_at
        self.last_activity = datetime.now()

    def is_valid(self) -> bool:
        """Check if session is still valid"""
        return datetime.now() < self.expires_at

    def refresh(self, duration: timedelta = timedelta(hours=24)):
        """Refresh session expiry"""
        self.expires_at = datetime.now() + duration
        self.last_activity = datetime.now()


class AuthManager:
    """
    Authentication and session management
    """

    def __init__(self, storage_file: Optional[Path] = None):
        """
        Initialize auth manager

        Args:
            storage_file: File to store user data. Defaults to the data
                directory rather than the cache directory, which callers may
                reasonably clear.
        """
        if storage_file is not None:
            self.storage_file = Path(storage_file)
        else:
            from ..config import settings

            self.storage_file = Path(settings.auth_storage_file)
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        self._load_users()

    def _load_users(self):
        """Load users from storage"""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    self.users = {
                        user_id: User.from_dict(user_data)
                        for user_id, user_data in data.get("users", {}).items()
                    }
                logger.info(f"Loaded {len(self.users)} users")
            except Exception as e:
                logger.error(f"Failed to load users: {e}")

    def _save_users(self):
        """Save users to storage"""
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "users": {
                    user_id: user.to_record()
                    for user_id, user in self.users.items()
                }
            }
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save users: {e}")

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "user"
    ) -> Optional[User]:
        """
        Create a new user

        Args:
            username: Username
            email: Email address
            password: Plain password (will be hashed)
            role: User role

        Returns:
            Created user or None if failed
        """
        try:
            # Check if username exists
            if any(u.username == username for u in self.users.values()):
                logger.warning(f"Username already exists: {username}")
                return None

            # Generate user ID
            user_id = secrets.token_urlsafe(16)

            # Create user
            user = User(user_id, username, email, role)

            user._password_hash = hash_password(password)

            self.users[user_id] = user
            self._save_users()

            logger.info(f"Created user: {username} ({user_id})")
            return user

        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return None

    def authenticate(self, username: str, password: str) -> Optional[Session]:
        """
        Authenticate user and create session

        Args:
            username: Username
            password: Password

        Returns:
            Session if authenticated, None otherwise
        """
        try:
            # Find user
            user = next(
                (u for u in self.users.values() if u.username == username),
                None
            )

            if not user:
                logger.warning(f"User not found: {username}")
                return None

            if not user.is_active:
                logger.warning(f"User inactive: {username}")
                return None

            is_valid, needs_upgrade = verify_password(
                password, getattr(user, "_password_hash", None)
            )
            if not is_valid:
                logger.warning(f"Invalid password for user: {username}")
                return None

            if needs_upgrade:
                # Legacy unsalted hash: replace it now that the plaintext is
                # known to be correct.
                user._password_hash = hash_password(password)
                logger.info(f"Upgraded password hash for user: {username}")

            # Create session
            session_id = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=24)

            session = Session(session_id, user.user_id, expires_at)
            self.sessions[session_id] = session

            # Update last login
            user.last_login = datetime.now().isoformat()
            self._save_users()

            logger.info(f"User authenticated: {username}")
            return session

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return None

    def validate_session(self, session_id: str) -> Optional[User]:
        """
        Validate session and return user

        Args:
            session_id: Session ID to validate

        Returns:
            User if session is valid, None otherwise
        """
        session = self.sessions.get(session_id)

        if not session or not session.is_valid():
            if session:
                del self.sessions[session_id]
            return None

        # Refresh session
        session.refresh()

        # Get user
        user = self.users.get(session.user_id)
        return user if user and user.is_active else None

    def logout(self, session_id: str) -> bool:
        """
        Logout user by removing session

        Args:
            session_id: Session ID to remove

        Returns:
            True if logged out
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"User logged out: {session_id}")
            return True
        return False

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)

    def list_users(self) -> List[User]:
        """Get all users"""
        return list(self.users.values())

    #: Fields update_user may change. Anything else - user_id, username,
    #: created_at, the password hash - is not settable this way.
    UPDATABLE_FIELDS = frozenset({"email", "role", "is_active"})

    def update_user(self, user_id: str, updates: Dict) -> bool:
        """
        Update user information.

        Only whitelisted fields are applied. The previous implementation did
        setattr for any attribute that existed on the object, which made the
        method as privileged as whatever called it.
        """
        user = self.users.get(user_id)
        if not user:
            return False

        for key, value in updates.items():
            if key in self.UPDATABLE_FIELDS:
                setattr(user, key, value)
            else:
                logger.warning("Ignoring non-updatable field %r for user %s", key, user_id)

        self._save_users()
        return True

    def set_password(self, user_id: str, password: str) -> bool:
        """Set a user's password, hashing it with the current KDF."""
        user = self.users.get(user_id)
        if not user:
            return False

        user._password_hash = hash_password(password)
        self._save_users()
        return True

    def delete_user(self, user_id: str) -> bool:
        """Delete user"""
        if user_id in self.users:
            del self.users[user_id]
            self._save_users()

            # Remove user sessions
            to_remove = [
                sid for sid, session in self.sessions.items()
                if session.user_id == user_id
            ]
            for sid in to_remove:
                del self.sessions[sid]

            logger.info(f"Deleted user: {user_id}")
            return True
        return False

    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        expired = [
            sid for sid, session in self.sessions.items()
            if not session.is_valid()
        ]

        for sid in expired:
            del self.sessions[sid]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")


# Global instance
_auth_manager = None


def get_auth_manager() -> AuthManager:
    """Get or create global auth manager"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager

