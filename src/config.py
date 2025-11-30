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
    
    # Supabase Configuration
    SUPABASE_URL: str = os.getenv('SUPABASE_URL', '')
    SUPABASE_KEY: str = os.getenv('SUPABASE_KEY', '')
    
    # AI Configuration
    GEMINI_API_KEY: str = os.getenv('GEMINI_API_KEY', '')
    
    # Security Configuration
    ENCRYPTION_KEY: str = os.getenv('ENCRYPTION_KEY', '')
    
    # Storage Configuration
    USE_SUPABASE_STORAGE: bool = os.getenv('USE_SUPABASE_STORAGE', 'false').lower() == 'true'
    SUPABASE_STORAGE_BUCKET: str = os.getenv('SUPABASE_STORAGE_BUCKET', 'quiksafe-files')
    
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
        
        # Supabase is optional for now - can be added later
        # if not cls.SUPABASE_URL:
        #     return False, "SUPABASE_URL is required"
        
        # if not cls.SUPABASE_KEY:
        #     return False, "SUPABASE_KEY is required"
        
        if not cls.GEMINI_API_KEY:
            return False, "GEMINI_API_KEY is required"
        
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
            'supabase_configured': bool(cls.SUPABASE_URL),
            'gemini_configured': bool(cls.GEMINI_API_KEY),
            'encryption_configured': bool(cls.ENCRYPTION_KEY),
            'use_supabase_storage': cls.USE_SUPABASE_STORAGE,
            'debug_mode': cls.DEBUG_MODE
        }


# Validate configuration on import
is_valid, error = Config.validate()
if not is_valid:
    print(f"⚠️  Configuration Error: {error}")
    print("Please check your .env file and ensure all required variables are set.")
    print("See .env.example for reference.")
