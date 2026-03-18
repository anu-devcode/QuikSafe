"""
QuikSafe Bot - Start Handler
Handles user registration and welcome flow.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from src.database.db_manager import DatabaseManager
from src.security.auth import AuthManager, SessionManager
from src.utils.formatters import format_welcome_message
from src.utils.keyboard_builder import KeyboardBuilder
from src.utils.deep_links import DeepLinkManager
import logging

logger = logging.getLogger(__name__)

# Conversation states
AWAITING_MASTER_PASSWORD = 1


class StartHandler:
    """Handles /start command and user registration."""
    
    def __init__(self, db: DatabaseManager, auth: AuthManager, session: SessionManager, scene_manager=None, analytics=None):
        """
        Initialize start handler.
        
        Args:
            db: Database manager instance
            auth: Authentication manager instance
            session: Session manager instance
        """
        self.db = db
        self.auth = auth
        self.session = session
        self.scene_manager = scene_manager
        self.analytics = analytics
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle /start command.
        
        Args:
            update: Telegram update
            context: Callback context
            
        Returns:
            Next conversation state
        """
        user = update.effective_user
        telegram_id = user.id

        # Always reset previous onboarding markers and stale scenes when /start is used.
        self._clear_auth_flow_context(context)
        if self.scene_manager and self.scene_manager.has_active_scene(telegram_id):
            self.scene_manager.cancel_scene(telegram_id)
        
        # Check for deep link parameters
        deep_link_data = None
        if self.analytics:
            self.analytics.track('onboarding_start_opened', telegram_id=telegram_id)

        if context.args:
            deep_link_param = context.args[0]
            deep_link_data = DeepLinkManager.parse_link(deep_link_param)
            if deep_link_data:
                logger.info(f"Deep link detected: {deep_link_data['action']}")
        
        # Check if user already exists
        existing_user = self.db.get_user_by_telegram_id(telegram_id)
        
        if existing_user:
            context.user_data['auth_flow_mode'] = 'login'
            context.user_data['awaiting_master_password'] = True

            # User exists, ask for master password
            message = f"👋 Welcome back, {user.first_name}!\n\n"
            
            if deep_link_data:
                action_desc = DeepLinkManager.get_action_description(deep_link_data['action'])
                message += f"You're accessing: {action_desc}\n\n"
            
            message += "Please enter your master password to continue:"
            
            await update.message.reply_text(message)
            if self.analytics:
                self.analytics.track('onboarding_login_prompt_shown', telegram_id=telegram_id)
            
            # Store deep link data for after authentication
            if deep_link_data:
                context.user_data['deep_link'] = deep_link_data
            
            return AWAITING_MASTER_PASSWORD
        else:
            context.user_data['auth_flow_mode'] = 'register'
            context.user_data['awaiting_master_password'] = True

            # New user, show welcome and ask to create master password
            welcome_msg = format_welcome_message(user.first_name)
            await update.message.reply_text(welcome_msg)
            
            await update.message.reply_text(
                "🔐 **Create Your Master Password**\n\n"
                "Your master password must:\n"
                "• Be at least 8 characters long\n"
                "• Contain uppercase and lowercase letters\n"
                "• Contain at least one number\n"
                "• Contain at least one special character (!@#$%^&*)\n\n"
                "⚠️ **Important:** This password cannot be recovered if lost!\n\n"
                "Please enter your master password:",
                parse_mode='Markdown'
            )
            if self.analytics:
                self.analytics.track('onboarding_registration_prompt_shown', telegram_id=telegram_id)
            
            # Store deep link data for after registration
            if deep_link_data:
                context.user_data['deep_link'] = deep_link_data
            
            return AWAITING_MASTER_PASSWORD
    
    async def receive_master_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle master password input.
        
        Args:
            update: Telegram update
            context: Callback context
            
        Returns:
            Next conversation state or end
        """
        user = update.effective_user
        telegram_id = user.id
        master_password = update.message.text
        
        # Delete the message containing the password for security
        await update.message.delete()
        
        # Check if user exists
        existing_user = self.db.get_user_by_telegram_id(telegram_id)
        flow_mode = context.user_data.get('auth_flow_mode')

        if flow_mode not in ('login', 'register'):
            flow_mode = 'login' if existing_user else 'register'

        if flow_mode == 'login':
            # If the user was expected to login but no account exists, switch cleanly to registration.
            if not existing_user:
                context.user_data['auth_flow_mode'] = 'register'
                await update.message.reply_text(
                    "ℹ️ No account found for this Telegram user yet.\n"
                    "Please create a master password to register:"
                )
                return AWAITING_MASTER_PASSWORD

            # Verify password
            stored_hash = existing_user['master_password_hash']
            
            if self.auth.verify_password(master_password, stored_hash):
                # Create session
                self.session.create_session(telegram_id, {
                    'user_id': existing_user['id'],
                    'telegram_id': telegram_id,
                    'authenticated': True
                })
                
                # Get deep link data if any
                deep_link_data = context.user_data.get('deep_link')
                
                # Show modern main menu
                await self._show_main_menu(update.message, user.first_name, existing_user['id'], deep_link_data)
                if self.analytics:
                    self.analytics.track('auth_login_success', telegram_id=telegram_id, user_id=existing_user['id'])
                
                # Clear deep link data
                if 'deep_link' in context.user_data:
                    del context.user_data['deep_link']
                self._clear_auth_flow_context(context)
                
                return ConversationHandler.END
            else:
                await update.message.reply_text(
                    "❌ Incorrect master password. Please try again:"
                )
                if self.analytics:
                    self.analytics.track('auth_login_failed', telegram_id=telegram_id)
                return AWAITING_MASTER_PASSWORD
        else:
            # If account already exists during register mode, redirect to login flow.
            if existing_user:
                stored_hash = existing_user.get('master_password_hash', '')
                if stored_hash and self.auth.verify_password(master_password, stored_hash):
                    self.session.create_session(telegram_id, {
                        'user_id': existing_user['id'],
                        'telegram_id': telegram_id,
                        'authenticated': True
                    })

                    deep_link_data = context.user_data.get('deep_link')
                    await self._show_main_menu(update.message, user.first_name, existing_user['id'], deep_link_data)
                    if 'deep_link' in context.user_data:
                        del context.user_data['deep_link']
                    self._clear_auth_flow_context(context)
                    if self.analytics:
                        self.analytics.track('auth_login_success', telegram_id=telegram_id, user_id=existing_user['id'])
                    return ConversationHandler.END

                context.user_data['auth_flow_mode'] = 'login'
                await update.message.reply_text(
                    "ℹ️ An account already exists for this Telegram user.\n"
                    "Please enter your existing master password to continue:"
                )
                return AWAITING_MASTER_PASSWORD

            # New user - validate and create account
            is_valid, error = self.auth.validate_password_strength(master_password)
            
            if not is_valid:
                await update.message.reply_text(
                    f"❌ {error}\n\nPlease try again:"
                )
                return AWAITING_MASTER_PASSWORD
            
            # Hash password and create user
            password_hash = self.auth.hash_password(master_password)
            new_user = self.db.create_user(telegram_id, password_hash)
            
            if new_user:
                # Create session
                self.session.create_session(telegram_id, {
                    'user_id': new_user['id'],
                    'telegram_id': telegram_id,
                    'authenticated': True
                })
                
                # Get deep link data if any
                deep_link_data = context.user_data.get('deep_link')
                
                # Show modern main menu
                await self._show_main_menu(update.message, user.first_name, new_user['id'], deep_link_data)
                if self.analytics:
                    self.analytics.track('auth_registration_success', telegram_id=telegram_id, user_id=new_user['id'])
                
                # Clear deep link data
                if 'deep_link' in context.user_data:
                    del context.user_data['deep_link']
                self._clear_auth_flow_context(context)
                
                return ConversationHandler.END
            else:
                await update.message.reply_text(
                    "❌ Failed to create account. Please try /start again."
                )
                self._clear_auth_flow_context(context)
                return ConversationHandler.END
    
    async def _show_main_menu(self, message, user_name: str, user_id: str, deep_link_data: dict = None):
        """
        Show modern main menu with inline keyboard.
        
        Args:
            message: Message object to reply to
            user_name: User's first name
            deep_link_data: Optional deep link data to handle
        """
        kb = KeyboardBuilder()
        
        # If deep link action provided, show targeted message
        if deep_link_data:
            action = deep_link_data.get('action')
            action_desc = DeepLinkManager.get_action_description(action)
            
            welcome_text = (
                f"✅ **Authentication Successful!**\n\n"
                f"Redirecting you to: {action_desc}\n\n"
                "Use the menu below to navigate:"
            )
        else:
            overview = self.db.get_user_task_overview(user_id)
            focus_line = "You are all caught up."
            if overview['overdue_high'] > 0:
                focus_line = f"Focus now: {overview['overdue_high']} high-priority overdue task(s)."
            elif overview['pending'] > 0:
                focus_line = f"Focus now: {overview['pending']} pending task(s)."

            welcome_text = (
                f"👋 **Welcome, {user_name}!**\n\n"
                "Your secure workspace is ready.\n\n"
                f"⚡ **Today**: {focus_line}\n\n"
                "**Fast lane**\n"
                "• Quick Save for passwords\n"
                "• Quick Task for instant planning\n"
                "• Quick Upload for files\n"
                "• Quick Search across everything\n\n"
                "**Workspace modules**\n"
                "• Password Vault\n"
                "• Task Planner\n"
                "• File Hub\n"
                "• AI Assistant\n\n"
                "Choose an option below:"
            )
        
        await message.reply_text(
            welcome_text,
            reply_markup=kb.main_menu(),
            parse_mode='Markdown'
        )
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Cancel the conversation.
        
        Args:
            update: Telegram update
            context: Callback context
            
        Returns:
            End conversation
        """
        await update.message.reply_text(
            "Operation cancelled. Type /start to begin again."
        )
        self._clear_auth_flow_context(context)
        return ConversationHandler.END

    @staticmethod
    def _clear_auth_flow_context(context: ContextTypes.DEFAULT_TYPE):
        """Clear temporary onboarding flags from user context."""
        context.user_data.pop('auth_flow_mode', None)
        context.user_data.pop('awaiting_master_password', None)
    
    def get_handler(self) -> ConversationHandler:
        """
        Get the conversation handler for registration.
        
        Returns:
            ConversationHandler instance
        """
        return ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                AWAITING_MASTER_PASSWORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_master_password)
                ]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    from src.utils.formatters import format_help_message
    
    help_text = format_help_message()
    await update.message.reply_text(help_text, parse_mode='Markdown')
