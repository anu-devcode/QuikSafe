"""
QuikSafe Bot - Main Entry Point
Secure Telegram bot for managing passwords, tasks, and files.
"""

from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ApplicationHandlerStop, filters
from telegram import Update
from src.config import Config
from src.database import DatabaseManager
from src.security import EncryptionManager, AuthManager, SessionManager
from src.ai import HuggingFaceClient
from src.handlers import (
    StartHandler,
    help_command,
    PasswordHandler,
    TaskHandler,
    FileHandler,
    SearchHandler,
    AIHandler,
    SettingsHandler,
    ResetHandler
)
from src.handlers.callback_handler import CallbackHandler
from src.analytics import AnalyticsTracker
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
        db = DatabaseManager(
            Config.DATABASE_URL,
            min_pool_size=Config.DB_POOL_MIN_SIZE,
            max_pool_size=Config.DB_POOL_MAX_SIZE,
            connect_timeout=Config.DB_CONNECT_TIMEOUT,
        )
        if Config.DB_RUN_MIGRATIONS_ON_STARTUP:
            db.initialize_database()

        encryption = EncryptionManager(Config.ENCRYPTION_KEY)
        auth = AuthManager()
        session = SessionManager()
        ai_client = HuggingFaceClient(Config.HUGGINGFACE_API_KEY)
        scene_manager = SceneManager()
        analytics = AnalyticsTracker(db)
        
        logger.info("All components initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        logger.error("Please check your configuration and try again.")
        return
    
    # Create application
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # Initialize handlers
    start_handler = StartHandler(db, auth, session, scene_manager, analytics=analytics)
    password_handler = PasswordHandler(db, encryption, session, scene_manager)
    task_handler = TaskHandler(db, encryption, session, scene_manager)
    file_handler = FileHandler(db, encryption, session, scene_manager)
    search_handler = SearchHandler(db, encryption, session, ai_client)
    ai_handler = AIHandler(db, encryption, session, ai_client)
    settings_handler = SettingsHandler(db, session, scene_manager, auth)
    reset_handler = ResetHandler(db, auth, session, Config.SUPPORT_ADMIN_TELEGRAM_IDS)
    
    callback_handler = CallbackHandler(
        db, encryption, session, ai_client,
        password_handler=password_handler,
        task_handler=task_handler,
        file_handler=file_handler,
        ai_handler=ai_handler,
        search_handler=search_handler,
        settings_handler=settings_handler,
        scene_manager=scene_manager,
        analytics=analytics,
    )

    # Commands that are safe to use without an authenticated session.
    public_commands = {
        'start',
        'help',
        'resetmaster',
        'cancel',
        'adminreset',  # Admin handler enforces allowlist checks.
    }

    async def command_auth_guard(update: Update, context):
        """Prevent unauthenticated access to protected slash commands."""
        message = update.effective_message
        user = update.effective_user
        if not message or not user or not message.text:
            return

        text = message.text.strip()
        if not text.startswith('/'):
            return

        command_token = text.split()[0][1:]
        command = command_token.split('@', 1)[0].lower()

        if command in public_commands:
            return

        if session.is_authenticated(user.id):
            return

        await message.reply_text(
            "❌ You must authenticate first.\n"
            "Use /start to log in, or /resetmaster if you forgot your password."
        )
        analytics.track('security_blocked_command', telegram_id=user.id, metadata={'command': command})
        raise ApplicationHandlerStop

    async def unauth_input_guard(update: Update, context):
        """Block unauthenticated text/uploads outside login and reset recovery flows."""
        message = update.effective_message
        user = update.effective_user
        if not message or not user:
            return

        if session.is_authenticated(user.id):
            return

        if context.user_data.get('awaiting_master_password'):
            return

        if context.user_data.get('in_reset_flow'):
            return

        await message.reply_text(
            "❌ You must authenticate first.\n"
            "Use /start to log in, or /resetmaster if you forgot your password."
        )
        analytics.track('security_blocked_input', telegram_id=user.id)
        raise ApplicationHandlerStop

    async def smart_intent_router(update: Update, context):
        """Route natural text intents to UI actions for commandless UX."""
        user = update.effective_user
        message = update.effective_message
        if not user or not message or not message.text:
            return

        if not session.is_authenticated(user.id):
            return

        if scene_manager.has_active_scene(user.id):
            return

        text = message.text.strip().lower()

        if any(word in text for word in ['add task', 'new task', 'task']) and len(text) <= 32:
            analytics.track('intent_routed_task_create', telegram_id=user.id)
            await task_handler.start_add_wizard(update)
            raise ApplicationHandlerStop

        if any(word in text for word in ['save password', 'new password', 'password']) and len(text) <= 40:
            analytics.track('intent_routed_password_create', telegram_id=user.id)
            await password_handler.start_save_wizard(update)
            raise ApplicationHandlerStop

        if any(word in text for word in ['files', 'file hub', 'my files']) and len(text) <= 32:
            analytics.track('intent_routed_file_hub', telegram_id=user.id)
            await file_handler.show_file_list(update)
            raise ApplicationHandlerStop

        if text.startswith('search ') or text == 'search':
            analytics.track('intent_routed_search_help', telegram_id=user.id)
            await message.reply_text(
                "Use `/search <query>` to search everything.\n"
                "Example: `/search invoices march`",
                parse_mode='Markdown'
            )
            raise ApplicationHandlerStop

    async def global_error_handler(update: object, context):
        """Graceful fallback for unexpected failures."""
        logger.exception("Unhandled bot error", exc_info=context.error)
        try:
            if isinstance(update, Update) and update.effective_user:
                analytics.track('runtime_unhandled_error', telegram_id=update.effective_user.id)
            if isinstance(update, Update) and update.effective_message:
                await update.effective_message.reply_text(
                    "⚠️ Something went wrong on our side. Please try again."
                )
        except Exception:
            # Avoid secondary failures in error handler.
            pass
    
    # Global message handler for wizards
    async def global_message_handler(update: Update, context):
        """Route messages to appropriate wizard handler."""
        user = update.effective_user
        if not user:
            return

        # Never mix onboarding auth input with wizard flows.
        if context.user_data.get('awaiting_master_password'):
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
    application.add_handler(reset_handler.get_handler())
    application.add_handler(reset_handler.get_admin_handler())

    # Enforce command authentication before command-specific handlers run.
    application.add_handler(MessageHandler(filters.COMMAND, command_auth_guard), group=-1)

    # Enforce auth for non-command sensitive inputs (text/uploads) before feature handlers.
    protected_non_command_filters = (
        (filters.TEXT & ~filters.COMMAND)
        | filters.Document.ALL
        | filters.PHOTO
        | filters.VIDEO
        | filters.AUDIO
        | filters.VOICE
    )
    application.add_handler(MessageHandler(protected_non_command_filters, unauth_input_guard), group=-1)
    
    # We keep the legacy handlers for now but they might not be needed if we use global handler
    # application.add_handler(password_handler.get_save_handler())
    # application.add_handler(task_handler.get_add_handler())
    
    # Register callback query handler (for inline keyboards)
    application.add_handler(CallbackQueryHandler(callback_handler.handle_callback))
    
    # Register global message handler for wizards (high priority)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, global_message_handler), group=1)

    # Smart intent routing for commandless UX.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, smart_intent_router), group=2)
    
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
    application.add_error_handler(global_error_handler)
    logger.info("Bot is starting... Press Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
