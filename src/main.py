"""
QuikSafe Bot - Main Entry Point
Secure Telegram bot for managing passwords, tasks, and files.
"""

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from src.config import Config
from src.database import DatabaseManager
from src.security import EncryptionManager, AuthManager, SessionManager
from src.ai import GeminiClient
from src.handlers import (
    StartHandler,
    help_command,
    PasswordHandler,
    TaskHandler,
    FileHandler,
    SearchHandler
)
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO if not Config.DEBUG_MODE else logging.DEBUG
)
logger = logging.getLogger(__name__)


def main():
    """Start the bot."""
    
    # Validate configuration
    is_valid, error = Config.validate()
    if not is_valid:
        logger.error(f"Configuration error: {error}")
        logger.error("Please check your .env file and ensure all required variables are set.")
        return
    
    logger.info("Starting QuikSafe Bot...")
    logger.info(f"Configuration: {Config.get_debug_info()}")
    
    # Initialize components
    try:
        db = DatabaseManager(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        encryption = EncryptionManager(Config.ENCRYPTION_KEY)
        auth = AuthManager()
        session = SessionManager()
        ai_client = GeminiClient(Config.GEMINI_API_KEY)
        
        logger.info("All components initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        return
    
    # Create application
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # Initialize handlers
    start_handler = StartHandler(db, auth, session)
    password_handler = PasswordHandler(db, encryption, session)
    task_handler = TaskHandler(db, encryption, session)
    file_handler = FileHandler(db, encryption, session)
    search_handler = SearchHandler(db, encryption, session, ai_client)
    
    # Register conversation handlers
    application.add_handler(start_handler.get_handler())
    application.add_handler(password_handler.get_save_handler())
    application.add_handler(task_handler.get_add_handler())
    
    # Register command handlers
    application.add_handler(CommandHandler('help', help_command))
    
    # Password commands
    application.add_handler(CommandHandler('getpassword', password_handler.get_password))
    application.add_handler(CommandHandler('listpasswords', password_handler.list_passwords))
    application.add_handler(CommandHandler('deletepassword', password_handler.delete_password))
    
    # Task commands
    application.add_handler(CommandHandler('listtasks', task_handler.list_tasks))
    application.add_handler(CommandHandler('completetask', task_handler.complete_task))
    application.add_handler(CommandHandler('deletetask', task_handler.delete_task))
    
    # File commands
    application.add_handler(CommandHandler('listfiles', file_handler.list_files))
    application.add_handler(CommandHandler('getfile', file_handler.get_file))
    application.add_handler(CommandHandler('deletefile', file_handler.delete_file))
    
    # Search commands
    application.add_handler(CommandHandler('search', search_handler.search))
    application.add_handler(CommandHandler('summarize', search_handler.summarize))
    
    # File upload handler (for documents, photos, videos, etc.)
    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE,
        file_handler.handle_file
    ))
    
    # Start the bot
    logger.info("Bot is starting... Press Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
