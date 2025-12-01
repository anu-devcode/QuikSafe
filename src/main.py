"""
QuikSafe Bot - Main Entry Point
Secure Telegram bot for managing passwords, tasks, and files.
"""

from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
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
    SearchHandler,
    AIHandler,
    SettingsHandler
)
from src.handlers.callback_handler import CallbackHandler
from src.utils.scene_manager import SceneManager
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
        # Check if Supabase is configured
        if Config.SUPABASE_URL == 'your_supabase_project_url' or not Config.SUPABASE_URL:
            logger.warning("⚠️  Supabase is not configured yet!")
            logger.warning("The bot will not function properly without a database.")
            logger.warning("Please set up Supabase and update your .env file:")
            logger.warning("  1. Create a Supabase project at https://supabase.com")
            logger.warning("  2. Run the schema from src/database/schema.sql")
            logger.warning("  3. Update SUPABASE_URL and SUPABASE_KEY in .env")
            logger.warning("")
            logger.warning("Press Ctrl+C to stop the bot.")
            return
        
        db = DatabaseManager(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        encryption = EncryptionManager(Config.ENCRYPTION_KEY)
        auth = AuthManager()
        session = SessionManager()
        ai_client = GeminiClient(Config.GEMINI_API_KEY)
        scene_manager = SceneManager()
        
        logger.info("All components initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        logger.error("Please check your configuration and try again.")
        return
    
    # Create application
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # Initialize handlers
    start_handler = StartHandler(db, auth, session)
    password_handler = PasswordHandler(db, encryption, session, scene_manager)
    task_handler = TaskHandler(db, encryption, session, scene_manager)
    file_handler = FileHandler(db, encryption, session, scene_manager)
    search_handler = SearchHandler(db, encryption, session, ai_client)
    ai_handler = AIHandler(db, encryption, session, ai_client)
    settings_handler = SettingsHandler(db, session, scene_manager, auth)
    
    callback_handler = CallbackHandler(
        db, encryption, session, ai_client,
        password_handler=password_handler,
        task_handler=task_handler,
        file_handler=file_handler,
        ai_handler=ai_handler,
        search_handler=search_handler,
        settings_handler=settings_handler,
        scene_manager=scene_manager
    )
    
    # Global message handler for wizards
    async def global_message_handler(update: Update, context):
        """Route messages to appropriate wizard handler."""
        user = update.effective_user
        if not user:
            return
            
        # Check if user has active scene
        if scene_manager.has_active_scene(user.id):
            scene = scene_manager.get_scene(user.id)
            
            # Route based on scene ID
            if scene.scene_id in ['save_password', 'edit_password']:
                if await password_handler.handle_wizard_input(update):
                    return
            
            elif scene.scene_id == 'add_task':
                if await task_handler.handle_wizard_input(update):
                    return

            elif scene.scene_id == 'change_password':
                if await settings_handler.handle_wizard_input(update):
                    return

    # Register conversation handlers
    application.add_handler(start_handler.get_handler())
    
    # We keep the legacy handlers for now but they might not be needed if we use global handler
    # application.add_handler(password_handler.get_save_handler())
    # application.add_handler(task_handler.get_add_handler())
    
    # Register callback query handler (for inline keyboards)
    application.add_handler(CallbackQueryHandler(callback_handler.handle_callback))
    
    # Register global message handler for wizards (high priority)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, global_message_handler), group=1)
    
    # Register file upload handler
    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE,
        file_handler.handle_file_upload
    ))
    
    # Register command handlers
    application.add_handler(CommandHandler('help', help_command))
    
    # Password commands
    application.add_handler(CommandHandler('savepassword', password_handler.save_password_start))
    application.add_handler(CommandHandler('getpassword', password_handler.get_password))
    application.add_handler(CommandHandler('listpasswords', password_handler.list_passwords))
    application.add_handler(CommandHandler('deletepassword', password_handler.delete_password_command))
    
    # Task commands
    application.add_handler(CommandHandler('listtasks', task_handler.list_tasks))
    application.add_handler(CommandHandler('addtask', task_handler.add_task_start))
    application.add_handler(CommandHandler('completetask', task_handler.complete_task_command))
    application.add_handler(CommandHandler('deletetask', task_handler.delete_task_command))
    
    # File commands
    application.add_handler(CommandHandler('listfiles', file_handler.list_files))
    application.add_handler(CommandHandler('getfile', file_handler.get_file))
    application.add_handler(CommandHandler('deletefile', file_handler.delete_file_command))

    # Search and AI commands
    application.add_handler(CommandHandler('search', search_handler.search))
    application.add_handler(CommandHandler('ai', ai_handler.show_menu))
    application.add_handler(CommandHandler('summarize', search_handler.summarize))
    
    # Start the bot
    logger.info("Bot is starting... Press Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
