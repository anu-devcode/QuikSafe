"""
QuikSafe Bot - Authentication Module
Handles user authentication with master password hashing using Argon2.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
from typing import Optional


class AuthManager:
    """Handles password hashing and verification using Argon2."""
    
    def __init__(self):
        """Initialize password hasher with secure defaults."""
        self.ph = PasswordHasher(
            time_cost=2,  # Number of iterations
            memory_cost=65536,  # Memory usage in KiB (64 MB)
            parallelism=4,  # Number of parallel threads
            hash_len=32,  # Length of hash in bytes
            salt_len=16  # Length of salt in bytes
        )
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using Argon2.
        
        Args:
            password: Plain text password to hash
            
        Returns:
            Hashed password string
        """
        if not password:
            raise ValueError("Password cannot be empty")
        
        return self.ph.hash(password)
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plain text password to verify
            password_hash: Hashed password to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        if not password or not password_hash:
            return False
        
        try:
            self.ph.verify(password_hash, password)
            
            # Check if hash needs rehashing (parameters changed)
            if self.ph.check_needs_rehash(password_hash):
                # In production, you'd update the hash in the database here
                pass
            
            return True
        except (VerifyMismatchError, InvalidHash):
            return False
    
    def validate_password_strength(self, password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password strength.
        
        Args:
            password: Password to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if len(password) > 128:
            return False, "Password must be less than 128 characters"
        
        # Check for at least one uppercase letter
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        # Check for at least one lowercase letter
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        # Check for at least one digit
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        
        # Check for at least one special character
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            return False, "Password must contain at least one special character"
        
        return True, None


# User session storage (in-memory for simplicity, use Redis in production)
class SessionManager:
    """Manages user sessions."""
    
    def __init__(self):
        """Initialize session storage."""
        self.sessions = {}  # telegram_id -> user_data
    
    def create_session(self, telegram_id: int, user_data: dict):
        """
        Create a new user session.
        
        Args:
            telegram_id: Telegram user ID
            user_data: User data to store in session
        """
        self.sessions[telegram_id] = user_data
    
    def get_session(self, telegram_id: int) -> Optional[dict]:
        """
        Get user session data.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            User session data or None if not found
        """
        return self.sessions.get(telegram_id)
    
    def update_session(self, telegram_id: int, data: dict):
        """
        Update user session data.
        
        Args:
            telegram_id: Telegram user ID
            data: Data to update in session
        """
        if telegram_id in self.sessions:
            self.sessions[telegram_id].update(data)
    
    def delete_session(self, telegram_id: int):
        """
        Delete user session.
        
        Args:
            telegram_id: Telegram user ID
        """
        if telegram_id in self.sessions:
            del self.sessions[telegram_id]
    
    def is_authenticated(self, telegram_id: int) -> bool:
        """
        Check if user is authenticated.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            True if user has an active session
        """
        return telegram_id in self.sessions
"""
QuikSafe Bot - Authentication Module
Handles user authentication with master password hashing using Argon2.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
from typing import Optional


class AuthManager:
    """Handles password hashing and verification using Argon2."""
    
    def __init__(self):
        """Initialize password hasher with secure defaults."""
        self.ph = PasswordHasher(
            time_cost=2,  # Number of iterations
            memory_cost=65536,  # Memory usage in KiB (64 MB)
            parallelism=4,  # Number of parallel threads
            hash_len=32,  # Length of hash in bytes
            salt_len=16  # Length of salt in bytes
        )
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using Argon2.
        
        Args:
            password: Plain text password to hash
            
        Returns:
            Hashed password string
        """
        if not password:
            raise ValueError("Password cannot be empty")
        
        return self.ph.hash(password)
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plain text password to verify
            password_hash: Hashed password to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        if not password or not password_hash:
            return False
        
        try:
            self.ph.verify(password_hash, password)
            
            # Check if hash needs rehashing (parameters changed)
            if self.ph.check_needs_rehash(password_hash):
                # In production, you'd update the hash in the database here
                pass
            
            return True
        except (VerifyMismatchError, InvalidHash):
            return False
    
    def validate_password_strength(self, password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password strength.
        
        Args:
            password: Password to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if len(password) > 128:
            return False, "Password must be less than 128 characters"
        
        # Check for at least one uppercase letter
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        # Check for at least one lowercase letter
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        # Check for at least one digit
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        
        # Check for at least one special character
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            return False, "Password must contain at least one special character"
        
        return True, None


# User session storage (in-memory for simplicity, use Redis in production)
class SessionManager:
    """Manages user sessions."""
    
    def __init__(self):
        """Initialize session storage."""
        self.sessions = {}  # telegram_id -> user_data
    
    def create_session(self, telegram_id: int, user_data: dict):
        """
        Create a new user session.
        
        Args:
            telegram_id: Telegram user ID
            user_data: User data to store in session
        """
        self.sessions[telegram_id] = user_data
    
    def get_session(self, telegram_id: int) -> Optional[dict]:
        """
        Get user session data.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            User session data or None if not found
        """
        return self.sessions.get(telegram_id)
    
    def update_session(self, telegram_id: int, data: dict):
        """
        Update user session data.
        
        Args:
            telegram_id: Telegram user ID
            data: Data to update in session
        """
        if telegram_id in self.sessions:
            self.sessions[telegram_id].update(data)
    
    def delete_session(self, telegram_id: int):
        """
        Delete user session.
        
        Args:
            telegram_id: Telegram user ID
        """
        if telegram_id in self.sessions:
            del self.sessions[telegram_id]
    
    def is_authenticated(self, telegram_id: int) -> bool:
        """
        Check if user is authenticated.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            True if user has an active session
        """
        return telegram_id in self.sessions
