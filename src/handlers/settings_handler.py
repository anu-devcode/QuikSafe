"""
QuikSafe Bot - Settings Handler
Handles user preferences and settings.
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.database.db_manager import DatabaseManager
from src.security.auth import SessionManager
from src.utils.keyboard_builder import KeyboardBuilder
from src.utils.scene_manager import SceneManager
from src.security.auth import AuthManager
import logging

logger = logging.getLogger(__name__)


class SettingsHandler:
    """Handles user settings and preferences."""
    
    def __init__(self, db: DatabaseManager, session: SessionManager, scene_manager: SceneManager, auth: AuthManager):
        """
        Initialize settings handler.
        
        Args:
            db: Database manager instance
            session: Session manager instance
            scene_manager: Scene manager instance
            auth: Auth manager instance
        """
        self.db = db
        self.session = session
        self.scene_manager = scene_manager
        self.auth = auth
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
            
        # Get current settings
        settings = self.db.get_user_settings(user_id)
        
        # Defaults
        security = settings.get('security', {})
        notifications = settings.get('notifications', {})
        
        auto_lock = security.get('auto_lock_minutes', 60)
        task_reminders = "On" if notifications.get('tasks', True) else "Off"
        weekly_summary = "On" if notifications.get('summary', False) else "Off"
            
        message = (
            "⚙️ **Settings**\n\n"
            "Customize security and notifications in one place.\n\n"
            "**Security**\n"
            f"• Auto-lock: {auto_lock} minutes\n"
            "• Data Encryption: AES-256 (Active)\n\n"
            "**Notifications**\n"
            f"• Task Reminders: {task_reminders}\n"
            f"• Weekly Summary: {weekly_summary}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🔒 Security", callback_data=self.kb.encode_callback('settings_security')),
                InlineKeyboardButton("🔔 Notifications", callback_data=self.kb.encode_callback('settings_notifications'))
            ],
            [
                InlineKeyboardButton("🚪 Log Out", callback_data=self.kb.encode_callback('settings_logout'))
            ],
            [
                InlineKeyboardButton("🆘 Contact Support", url="https://t.me/Billaden5")
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
        self.session.delete_session(user.id)
        
        await update.callback_query.edit_message_text(
            "👋 **Logged Out**\n\n"
            "Your secure session has been cleared.\n"
            "Use /start to log in again."
        )

    async def show_security_menu(self, update: Update):
        """Show security settings menu."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        settings = self.db.get_user_settings(user_id)
        auto_lock = settings.get('security', {}).get('auto_lock_minutes', 60)
            
        message = (
            "🔒 **Security Settings**\n\n"
            "Manage access and protection controls.\n\n"
            "• **Encryption**: AES-256 (Always On)\n"
            f"• **Auto-Lock**: {auto_lock} Minutes\n"
            "• **Biometric**: Disabled (Coming Soon)"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("⏱️ Change Auto-Lock", callback_data=self.kb.encode_callback('settings_autolock')),
                InlineKeyboardButton("🔑 Change Master Password", callback_data=self.kb.encode_callback('settings_changepass'))
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

    async def change_auto_lock(self, update: Update):
        """Cycle through auto-lock durations."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        settings = self.db.get_user_settings(user_id)
        current = settings.get('security', {}).get('auto_lock_minutes', 60)
        
        # Cycle: 15 -> 30 -> 60 -> 120 -> 15
        durations = [15, 30, 60, 120]
        try:
            next_idx = (durations.index(current) + 1) % len(durations)
            new_duration = durations[next_idx]
        except ValueError:
            new_duration = 60
            
        # Update settings
        if 'security' not in settings:
            settings['security'] = {}
        settings['security']['auto_lock_minutes'] = new_duration
        
        self.db.update_user_settings(user_id, settings)
        
        # Refresh menu
        await self.show_security_menu(update)

    async def show_notifications_menu(self, update: Update):
        """Show notification settings menu."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        settings = self.db.get_user_settings(user_id)
        notifications = settings.get('notifications', {})
        
        tasks_on = notifications.get('tasks', True)
        summary_on = notifications.get('summary', False)
        
        tasks_icon = "✅" if tasks_on else "❌"
        summary_icon = "✅" if summary_on else "❌"
            
        message = (
            "🔔 **Notification Settings**\n\n"
            "Choose which reminders you want to receive.\n\n"
            f"• **Task Reminders**: {tasks_icon} {'On' if tasks_on else 'Off'}\n"
            f"• **Weekly Summary**: {summary_icon} {'On' if summary_on else 'Off'}\n"
            "• **Security Alerts**: ✅ On"
        )
        
        keyboard = [
            [
                InlineKeyboardButton(f"{tasks_icon} Toggle Reminders", callback_data=self.kb.encode_callback('settings_toggle_reminders')),
                InlineKeyboardButton(f"{summary_icon} Toggle Weekly", callback_data=self.kb.encode_callback('settings_toggle_summary'))
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

    async def toggle_setting(self, update: Update, setting_type: str):
        """Toggle a notification setting."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        settings = self.db.get_user_settings(user_id)
        if 'notifications' not in settings:
            settings['notifications'] = {'tasks': True, 'summary': False}
            
        if setting_type == 'tasks':
            settings['notifications']['tasks'] = not settings['notifications'].get('tasks', True)
        elif setting_type == 'summary':
            settings['notifications']['summary'] = not settings['notifications'].get('summary', False)
            
        self.db.update_user_settings(user_id, settings)
        
        # Refresh menu
        await self.show_notifications_menu(update)

    async def start_change_password_wizard(self, update: Update):
        """Start the change password wizard."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        scene = self.scene_manager.start_scene(user.id, 'change_password')
        if scene is None:
            await self._send_error(update, "Password change flow is not available right now.")
            return
        
        message = (
            "🔑 **Change Master Password**\n\n"
            "Step 1/3: **Current Password**\n"
            "Enter your current master password:"
        )
        
        keyboard = [[
            InlineKeyboardButton(
                f"{self.kb.EMOJI['cancel']} Cancel",
                callback_data=self.kb.encode_callback('cancel')
            )
        ]]
        
        wizard_message = None
        if update.callback_query:
            wizard_message = await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            wizard_message = await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        if wizard_message:
            self.scene_manager.set_scene_data(user.id, 'wizard_chat_id', wizard_message.chat_id)
            self.scene_manager.set_scene_data(user.id, 'wizard_message_id', wizard_message.message_id)

    async def handle_wizard_input(self, update: Update):
        """Handle wizard input for settings."""
        user = update.effective_user
        if not self.scene_manager.has_active_scene(user.id):
            return False
            
        scene = self.scene_manager.get_scene(user.id)
        if scene.scene_id != 'change_password':
            return False
            
        current_step = scene.get_current_step()
        text = update.message.text.strip()
        
        # Delete user message for security
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete password input: {e}")
            
        if current_step == 'current_password':
            # Verify current password
            is_auth, user_id = self._check_auth(user.id)
            if not is_auth or not user_id:
                await self._send_auth_error(update)
                return True

            db_user = self.db.get_user_by_id(user_id)
            if not db_user or not self.auth.verify_password(text, db_user.get('master_password_hash', '')):
                await update.message.reply_text("❌ Incorrect password. Please try again:")
                return True
                
            self.scene_manager.advance_scene(user.id)
            await self._send_wizard_step(
                update,
                user.id,
                "✅ Password verified.\n\n"
                "Step 2/3: **New Password**\n"
                "Enter your new strong password:"
            )
            
        elif current_step == 'new_password':
            is_valid, error = self.auth.validate_password_strength(text)
            if not is_valid:
                await update.message.reply_text(f"❌ {error}\nPlease try again:")
                return True
                
            self.scene_manager.set_scene_data(user.id, 'new_password', text)
            self.scene_manager.advance_scene(user.id)
            
            await self._send_wizard_step(
                update,
                user.id,
                "Step 3/3: **Confirm Password**\n"
                "Please re-enter your new password:"
            )
            
        elif current_step == 'confirm_password':
            new_password = scene.get_data('new_password')
            if text != new_password:
                await update.message.reply_text("❌ Passwords do not match. Please try again:")
                return True
            
            # Update password
            is_auth, user_id = self._check_auth(user.id)
            new_hash = self.auth.hash_password(new_password)
            
            if self.db.update_master_password_by_user_id(user_id, new_hash):
                self.scene_manager.complete_scene(user.id)
                await update.message.reply_text(
                    "✅ **Success!**\n\n"
                    "Your master password has been changed.",
                    parse_mode='Markdown'
                )
                if update.callback_query:
                    await self.show_security_menu(update)
            else:
                await update.message.reply_text("❌ Failed to update password. Please try again later.")
                self.scene_manager.cancel_scene(user.id)
                
        return True

    async def _send_auth_error(self, update: Update):
        """Send authentication error message."""
        msg = "❌ Session expired. Please /start again."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)

    async def _send_error(self, update: Update, text: str):
        """Send generic error message."""
        if update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
        else:
            await update.message.reply_text(f"❌ {text}")

    async def _send_wizard_step(self, update: Update, telegram_id: int, text: str, reply_markup=None):
        """Edit existing wizard prompt when possible to keep chat clean."""
        scene = self.scene_manager.get_scene(telegram_id)
        if scene:
            chat_id = scene.get_data('wizard_chat_id')
            message_id = scene.get_data('wizard_message_id')
            if chat_id and message_id:
                try:
                    await update.get_bot().edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    return
                except Exception:
                    pass

        if update.message:
            sent = await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            sent = await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

        if scene and sent:
            self.scene_manager.set_scene_data(telegram_id, 'wizard_chat_id', sent.chat_id)
            self.scene_manager.set_scene_data(telegram_id, 'wizard_message_id', sent.message_id)
