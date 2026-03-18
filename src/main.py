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
from src.notifications import ReminderService
from src.utils.scene_manager import SceneManager
from src.utils.keyboard_builder import KeyboardBuilder
import logging
from time import monotonic

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
        reminder_service = ReminderService(db, encryption, analytics)
        
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
            _touch_activity_if_authenticated(user.id, context)
            return

        await message.reply_text(
            "❌ You must authenticate first.\n"
            "Use /start to log in, or /resetmaster if you forgot your password."
        )
        analytics.track('security_blocked_command', telegram_id=user.id, metadata={'command': command})
        raise ApplicationHandlerStop

    def _should_touch_activity(context) -> bool:
        """Throttle write frequency for activity timestamps to reduce DB churn."""
        now = monotonic()
        last_seen = context.user_data.get('_last_activity_touch_at', 0.0)
        if now - last_seen < 600:
            return False
        context.user_data['_last_activity_touch_at'] = now
        return True

    def _touch_activity_if_authenticated(telegram_id: int, context):
        """Persist best-effort last activity signal for retention nudges."""
        try:
            if not session.is_authenticated(telegram_id):
                return
            if not _should_touch_activity(context):
                return

            session_data = session.get_session(telegram_id) or {}
            user_id = session_data.get('user_id')
            if not user_id:
                return

            settings = db.get_user_settings(user_id)
            reminder_service.mark_seen(user_id, telegram_id, settings)
        except Exception as exc:
            logger.debug("Skipping activity touch for %s: %s", telegram_id, exc)

    async def admin_stats_command(update: Update, context):
        """Show retention/notification analytics snapshot for support admins."""
        user = update.effective_user
        message = update.effective_message
        if not user or not message:
            return

        if user.id not in Config.SUPPORT_ADMIN_TELEGRAM_IDS:
            await message.reply_text("❌ You are not authorized to use this command.")
            analytics.track('security_blocked_command', telegram_id=user.id, metadata={'command': 'adminstats'})
            return

        days = 7
        if context.args:
            try:
                days = int(context.args[0])
            except ValueError:
                pass

        stats = db.get_notification_analytics_snapshot(days)
        conversion_pct = stats['conversion_rate'] * 100
        task_pct = stats['task_conversion_rate'] * 100
        weekly_pct = stats['weekly_conversion_rate'] * 100
        inactivity_pct = stats['inactivity_conversion_rate'] * 100
        await message.reply_text(
            (
                f"📊 **Retention Snapshot ({stats['days']}d)**\n\n"
                f"• Task reminders sent: {stats['task_sent']}\n"
            f"• Task re-engaged: {stats['task_reengaged']} ({task_pct:.1f}%)\n"
                f"• Weekly summaries sent: {stats['weekly_sent']}\n"
            f"• Weekly re-engaged: {stats['weekly_reengaged']} ({weekly_pct:.1f}%)\n"
                f"• Inactivity nudges sent: {stats['inactivity_sent']}\n"
            f"• Inactivity re-engaged: {stats['inactivity_reengaged']} ({inactivity_pct:.1f}%)\n"
                f"• Total notifications: {stats['total_sent']}\n"
                f"• Re-engagement events: {stats['reengaged']}\n"
                f"• Re-engaged users: {stats['reengaged_users']}\n"
                f"• Re-engagement rate: {conversion_pct:.1f}%"
            ),
            parse_mode='Markdown',
        )

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

        text_raw = message.text.strip()
        text = text_raw.lower()

        # Built-in reply-keyboard dock routes.
        session_data = session.get_session(user.id) or {}
        session_user_id = session_data.get('user_id')
        if text in ('🏠 dashboard', 'dashboard') and session_user_id:
            await start_handler._show_main_menu(message, user.first_name, session_user_id)
            raise ApplicationHandlerStop

        if text in ('🔐 vault', 'vault'):
            await password_handler.show_password_list(update)
            raise ApplicationHandlerStop

        if text in ('✅ planner', 'planner'):
            await task_handler.show_task_list(update)
            raise ApplicationHandlerStop

        if text in ('📁 library', 'library'):
            await file_handler.show_file_list(update)
            raise ApplicationHandlerStop

        if text in ('🤖 ai studio', 'ai studio'):
            await ai_handler.show_menu(update)
            raise ApplicationHandlerStop

        if text in ('⚙️ control', 'control', 'settings'):
            await settings_handler.show_menu(update)
            raise ApplicationHandlerStop

        if text in ('➕ quick capture', 'quick capture'):
            await password_handler.start_save_wizard(update)
            raise ApplicationHandlerStop

        if text in ('📝 quick plan', 'quick plan'):
            await task_handler.start_add_wizard(update)
            raise ApplicationHandlerStop

        if text in ('📎 drop file', 'drop file'):
            await message.reply_text(
                "Send any file, photo, video, audio, or voice clip now and I will store it securely."
            )
            raise ApplicationHandlerStop

        if text in ('🔎 instant find', 'instant find'):
            await message.reply_text(
                "Use `/search <query>` for global search.\n"
                "Example: `/search invoices march`",
                parse_mode='Markdown'
            )
            raise ApplicationHandlerStop

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

    async def activity_message_tracker(update: Update, context):
        """Track authenticated user message activity for inactivity reminders."""
        user = update.effective_user
        if not user:
            return
        _touch_activity_if_authenticated(user.id, context)

    async def activity_callback_tracker(update: Update, context):
        """Track authenticated callback interactions for inactivity reminders."""
        user = update.effective_user
        if not user:
            return
        _touch_activity_if_authenticated(user.id, context)

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

            elif scene.scene_id in ['change_password', 'set_timezone']:
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

    # Track activity after auth checks and before feature routing.
    activity_filters = (
        (filters.TEXT & ~filters.COMMAND)
        | filters.Document.ALL
        | filters.PHOTO
        | filters.VIDEO
        | filters.AUDIO
        | filters.VOICE
    )
    application.add_handler(MessageHandler(activity_filters, activity_message_tracker), group=0)
    application.add_handler(CallbackQueryHandler(activity_callback_tracker), group=-1)
    
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
    application.add_handler(CommandHandler('adminstats', admin_stats_command))

    # Search and AI commands
    application.add_handler(CommandHandler('search', search_handler.search))

    supported_commands = {
        'start',
        'help',
        'search',
        'resetmaster',
        'adminreset',
        'adminstats',
        'cancel',
    }

    async def commandless_hint(update: Update, context):
        """Guide users to button-first navigation for unsupported commands."""
        message = update.effective_message
        user = update.effective_user
        if not message or not user or not message.text:
            return

        token = message.text.strip().split()[0]
        command = token[1:].split('@', 1)[0].lower()
        if command in supported_commands:
            return

        if not session.is_authenticated(user.id):
            await message.reply_text(
                "Use /start to authenticate first.\n"
                "After login, use the on-screen buttons to navigate."
            )
            return

        kb = KeyboardBuilder()
        await message.reply_text(
            "This bot now uses button-based flows.\n"
            "Use the main menu buttons (Password Vault, Task Planner, File Hub, AI, Settings).\n"
            "Use /search only when you need global search.",
            reply_markup=kb.main_reply_dock()
        )

    # Catch unsupported slash commands and nudge users to button sequences.
    application.add_handler(MessageHandler(filters.COMMAND, commandless_hint), group=5)

    async def run_task_reminders(context):
        await reminder_service.run_task_reminders(context)

    async def run_weekly_summary(context):
        await reminder_service.run_weekly_summary(context)

    async def run_inactivity_nudges(context):
        await reminder_service.run_inactivity_nudges(context)

    if application.job_queue:
        application.job_queue.run_repeating(
            run_task_reminders,
            interval=60 * 60,
            first=2 * 60,
            name='task_reminders',
        )
        application.job_queue.run_repeating(
            run_weekly_summary,
            interval=6 * 60 * 60,
            first=5 * 60,
            name='weekly_summary',
        )
        application.job_queue.run_repeating(
            run_inactivity_nudges,
            interval=4 * 60 * 60,
            first=3 * 60,
            name='inactivity_nudges',
        )
        logger.info("Notification scheduler initialized")
    else:
        logger.warning(
            "JobQueue unavailable. Install python-telegram-bot job queue extras to enable reminders."
        )
    
    # Start the bot
    application.add_error_handler(global_error_handler)
    logger.info("Bot is starting... Press Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
