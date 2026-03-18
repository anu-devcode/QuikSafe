"""
QuikSafe Bot - Configuration Management
Loads and validates environment variables and bot settings.
"""

import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()


class Config:
    """Application configuration from environment variables."""
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    BOT_USERNAME: str = os.getenv('BOT_USERNAME', 'QuikSafeBot')
    
    # Database Configuration (Coolify-managed PostgreSQL)
    DATABASE_URL: str = os.getenv('DATABASE_URL', '')
    DB_POOL_MIN_SIZE: int = int(os.getenv('DB_POOL_MIN_SIZE', '1'))
    DB_POOL_MAX_SIZE: int = int(os.getenv('DB_POOL_MAX_SIZE', '10'))
    DB_CONNECT_TIMEOUT: int = int(os.getenv('DB_CONNECT_TIMEOUT', '10'))
    DB_RUN_MIGRATIONS_ON_STARTUP: bool = os.getenv('DB_RUN_MIGRATIONS_ON_STARTUP', 'true').lower() == 'true'
    
    # AI Configuration
    HUGGINGFACE_API_KEY: str = os.getenv('HUGGINGFACE_API_KEY', os.getenv('HF_API_TOKEN', ''))
    
    # Security Configuration
    ENCRYPTION_KEY: str = os.getenv('ENCRYPTION_KEY', '')
    SUPPORT_ADMIN_TELEGRAM_IDS: set[int] = {
        int(item.strip())
        for item in os.getenv('SUPPORT_ADMIN_TELEGRAM_IDS', '').split(',')
        if item.strip().isdigit()
    }
    
    # Bot Configuration
    DEBUG_MODE: bool = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    
    @classmethod
    def validate(cls) -> tuple[bool, Optional[str]]:
        """
        Validate that all required configuration is present.
        
        Returns:
            tuple: (is_valid, error_message)
        """
        if not cls.TELEGRAM_BOT_TOKEN:
            return False, "TELEGRAM_BOT_TOKEN is required"
        
        if not cls.DATABASE_URL:
            return False, "DATABASE_URL is required"
        
        if not cls.HUGGINGFACE_API_KEY:
            return False, "HUGGINGFACE_API_KEY is required"
        
        if not cls.ENCRYPTION_KEY:
            return False, "ENCRYPTION_KEY is required"
        
        # Validate encryption key format (Fernet key should be 44 characters)
        if len(cls.ENCRYPTION_KEY) != 44:
            return False, "ENCRYPTION_KEY must be a valid Fernet key (44 characters)"
        
        return True, None
    
    @classmethod
    def get_debug_info(cls) -> dict:
        """Get configuration info for debugging (without sensitive data)."""
        return {
            'bot_username': cls.BOT_USERNAME,
            'database_configured': bool(cls.DATABASE_URL),
            'huggingface_configured': bool(cls.HUGGINGFACE_API_KEY),
            'encryption_configured': bool(cls.ENCRYPTION_KEY),
            'support_admin_count': len(cls.SUPPORT_ADMIN_TELEGRAM_IDS),
            'db_pool_min_size': cls.DB_POOL_MIN_SIZE,
            'db_pool_max_size': cls.DB_POOL_MAX_SIZE,
            'debug_mode': cls.DEBUG_MODE
        }


# Validate configuration on import
is_valid, error = Config.validate()
if not is_valid:
    raise ValueError(f"Configuration Error: {error}")

