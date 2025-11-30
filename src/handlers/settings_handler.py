"""
QuikSafe Bot - Settings Handler
Handles user preferences and settings.
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.database.db_manager import DatabaseManager
from src.security.auth import SessionManager
from src.utils.keyboard_builder import KeyboardBuilder
import logging

logger = logging.getLogger(__name__)


class SettingsHandler:
    """Handles user settings and preferences."""
    
    def __init__(self, db: DatabaseManager, session: SessionManager):
        """
        Initialize settings handler.
        
        Args:
            db: Database manager instance
            session: Session manager instance
        """
        self.db = db
        self.session = session
        self.kb = KeyboardBuilder()
    
    def _check_auth(self, telegram_id: int) -> tuple[bool, str]:
        """Check if user is authenticated."""
        if not self.session.is_authenticated(telegram_id):
            return False, None
        
        session_data = self.session.get_session(telegram_id)
        return True, session_data.get('user_id')
    
    async def show_menu(self, update: Update):
        """Show settings menu."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        message = (
            "⚙️ **Settings**\n\n"
            "Configure your bot preferences.\n\n"
            "**Security**\n"
            "• Auto-lock: 1 hour (Default)\n"
            "• Data Encryption: AES-256 (Active)\n\n"
            "**Notifications**\n"
            "• Task Reminders: On\n"
            "• Weekly Summary: Off"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🔒 Security Settings", callback_data=self.kb.encode_callback('settings_security')),
                InlineKeyboardButton("🔔 Notifications", callback_data=self.kb.encode_callback('settings_notifications'))
            ],
            [
                InlineKeyboardButton("🗑️ Clear Session (Logout)", callback_data=self.kb.encode_callback('settings_logout'))
            ],
            [
                InlineKeyboardButton(f"{self.kb.EMOJI['back']} Back to Menu", callback_data=self.kb.encode_callback('main_menu'))
            ]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    async def handle_logout(self, update: Update):
        """Handle logout action."""
        user = update.effective_user
        self.session.logout(user.id)
        
        await update.callback_query.edit_message_text(
            "👋 **Logged Out**\n\n"
            "Your session has been cleared securely.\n"
            "Use /start to log in again."
        )

    async def show_security_menu(self, update: Update):
        """Show security settings menu."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        message = (
            "🔒 **Security Settings**\n\n"
            "Manage your account security.\n\n"
            "• **Encryption**: AES-256 (Always On)\n"
            "• **Auto-Lock**: 1 Hour\n"
            "• **Biometric**: Disabled (Coming Soon)"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("⏱️ Change Auto-Lock", callback_data=self.kb.encode_callback('settings_autolock')),
                InlineKeyboardButton("🔑 Change Master Pass", callback_data=self.kb.encode_callback('settings_changepass'))
            ],
            [
                InlineKeyboardButton(f"{self.kb.EMOJI['back']} Back to Settings", callback_data=self.kb.encode_callback('menu_settings'))
            ]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def show_notifications_menu(self, update: Update):
        """Show notification settings menu."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        message = (
            "🔔 **Notification Settings**\n\n"
            "Customize your alerts.\n\n"
            "• **Task Reminders**: ✅ On\n"
            "• **Weekly Summary**: ❌ Off\n"
            "• **Security Alerts**: ✅ On"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Toggle Reminders", callback_data=self.kb.encode_callback('settings_toggle_reminders')),
                InlineKeyboardButton("❌ Toggle Summary", callback_data=self.kb.encode_callback('settings_toggle_summary'))
            ],
            [
                InlineKeyboardButton(f"{self.kb.EMOJI['back']} Back to Settings", callback_data=self.kb.encode_callback('menu_settings'))
            ]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def _send_auth_error(self, update: Update):
        """Send authentication error message."""
        msg = "❌ Session expired. Please /start again."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
