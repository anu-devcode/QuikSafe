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
import re
from typing import Optional

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

    @staticmethod
    def _get_notification_defaults() -> dict:
        return {
            'tasks': True,
            'summary': False,
            'reminder_window_hours': 24,
            'inactivity_nudge_hours': 72,
            'quiet_hours_enabled': False,
            'quiet_hours_start': 22,
            'quiet_hours_end': 8,
            'timezone_offset_minutes': 0,
        }

    def _get_notification_settings(self, settings: dict) -> dict:
        notifications = settings.get('notifications', {}) if isinstance(settings, dict) else {}
        defaults = self._get_notification_defaults()
        merged = defaults.copy()
        if isinstance(notifications, dict):
            merged.update(notifications)
        return merged

    @staticmethod
    def _format_utc_offset(offset_minutes: int) -> str:
        sign = '+' if offset_minutes >= 0 else '-'
        total = abs(int(offset_minutes))
        hours = total // 60
        minutes = total % 60
        return f"UTC{sign}{hours:02d}:{minutes:02d}"

    @staticmethod
    def _parse_utc_offset(text: str) -> Optional[int]:
        """Parse UTC offset formats like UTC+05:30, +2, -04:00, or Z."""
        raw = (text or '').strip().upper().replace('UTC', '').replace(' ', '')
        if raw in ('Z', '+0', '-0', '+00', '-00', '+00:00', '-00:00', '0'):
            return 0

        match = re.fullmatch(r'([+-])(\d{1,2})(?::?(\d{2}))?', raw)
        if not match:
            return None

        sign, hh, mm = match.groups()
        hours = int(hh)
        minutes = int(mm or '0')
        if hours > 14 or minutes not in (0, 15, 30, 45):
            return None

        total = hours * 60 + minutes
        if sign == '-':
            total = -total

        if total < -12 * 60 or total > 14 * 60:
            return None
        return total
    
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
        notifications = self._get_notification_settings(settings)
        
        auto_lock = security.get('auto_lock_minutes', 60)
        task_reminders = "On" if notifications.get('tasks', True) else "Off"
        weekly_summary = "On" if notifications.get('summary', False) else "Off"
            
        message = (
            "⚙️ **Settings**\n\n"
            "Tune security, alerts, and experience controls.\n\n"
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
            "Manage access posture and protection controls.\n\n"
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
        notifications = self._get_notification_settings(settings)
        
        tasks_on = notifications.get('tasks', True)
        summary_on = notifications.get('summary', False)
        reminder_window = int(notifications.get('reminder_window_hours', 24) or 24)
        inactivity_window = int(notifications.get('inactivity_nudge_hours', 72) or 72)
        quiet_enabled = bool(notifications.get('quiet_hours_enabled', False))
        quiet_start = int(notifications.get('quiet_hours_start', 22) or 22)
        quiet_end = int(notifications.get('quiet_hours_end', 8) or 8)
        tz_offset = int(notifications.get('timezone_offset_minutes', 0) or 0)
        
        tasks_icon = "✅" if tasks_on else "❌"
        summary_icon = "✅" if summary_on else "❌"
        quiet_icon = "✅" if quiet_enabled else "❌"
        quiet_text = f"{quiet_start:02d}:00-{quiet_end:02d}:00" if quiet_enabled else "Off"
        tz_label = self._format_utc_offset(tz_offset)
            
        message = (
            "🔔 **Notification Settings**\n\n"
            "Control cadence, quiet hours, and delivery style.\n\n"
            f"• **Task Reminders**: {tasks_icon} {'On' if tasks_on else 'Off'}\n"
            f"• **Weekly Summary**: {summary_icon} {'On' if summary_on else 'Off'}\n"
            f"• **Task Window**: Next {reminder_window}h\n"
            f"• **Inactivity Nudge**: {inactivity_window}h\n"
            f"• **Quiet Hours**: {quiet_icon} {quiet_text}\n"
            f"• **Timezone**: {tz_label}\n"
            "• **Security Alerts**: ✅ On"
        )
        
        keyboard = [
            [
                InlineKeyboardButton(f"{tasks_icon} Toggle Reminders", callback_data=self.kb.encode_callback('settings_toggle_reminders')),
                InlineKeyboardButton(f"{summary_icon} Toggle Weekly", callback_data=self.kb.encode_callback('settings_toggle_summary'))
            ],
            [
                InlineKeyboardButton("⏱️ Cycle Task Window", callback_data=self.kb.encode_callback('settings_cycle_task_window')),
                InlineKeyboardButton("🕒 Cycle Nudge Gap", callback_data=self.kb.encode_callback('settings_cycle_inactivity'))
            ],
            [
                InlineKeyboardButton(f"{quiet_icon} Toggle Quiet Hours", callback_data=self.kb.encode_callback('settings_toggle_quiet')),
                InlineKeyboardButton("🌙 Cycle Quiet Window", callback_data=self.kb.encode_callback('settings_cycle_quiet_window'))
            ],
            [
                InlineKeyboardButton("🌍 Cycle Timezone", callback_data=self.kb.encode_callback('settings_cycle_timezone')),
                InlineKeyboardButton("⌨️ Set Timezone", callback_data=self.kb.encode_callback('settings_set_timezone')),
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
        settings['notifications'] = self._get_notification_settings(settings)
            
        if setting_type == 'tasks':
            settings['notifications']['tasks'] = not settings['notifications'].get('tasks', True)
        elif setting_type == 'summary':
            settings['notifications']['summary'] = not settings['notifications'].get('summary', False)
            
        self.db.update_user_settings(user_id, settings)
        
        # Refresh menu
        await self.show_notifications_menu(update)

    async def cycle_task_window(self, update: Update):
        """Cycle due-soon reminder window in hours."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        if not is_auth:
            await self._send_auth_error(update)
            return

        options = [6, 12, 24, 48]
        settings = self.db.get_user_settings(user_id)
        settings['notifications'] = self._get_notification_settings(settings)
        current = int(settings['notifications'].get('reminder_window_hours', 24) or 24)
        next_value = options[(options.index(current) + 1) % len(options)] if current in options else 24
        settings['notifications']['reminder_window_hours'] = next_value
        self.db.update_user_settings(user_id, settings)
        await self.show_notifications_menu(update)

    async def cycle_inactivity_window(self, update: Update):
        """Cycle inactivity nudge cooldown in hours."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        if not is_auth:
            await self._send_auth_error(update)
            return

        options = [48, 72, 96, 168]
        settings = self.db.get_user_settings(user_id)
        settings['notifications'] = self._get_notification_settings(settings)
        current = int(settings['notifications'].get('inactivity_nudge_hours', 72) or 72)
        next_value = options[(options.index(current) + 1) % len(options)] if current in options else 72
        settings['notifications']['inactivity_nudge_hours'] = next_value
        self.db.update_user_settings(user_id, settings)
        await self.show_notifications_menu(update)

    async def toggle_quiet_hours(self, update: Update):
        """Enable or disable quiet hours for reminders."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        if not is_auth:
            await self._send_auth_error(update)
            return

        settings = self.db.get_user_settings(user_id)
        settings['notifications'] = self._get_notification_settings(settings)
        enabled = bool(settings['notifications'].get('quiet_hours_enabled', False))
        settings['notifications']['quiet_hours_enabled'] = not enabled
        self.db.update_user_settings(user_id, settings)
        await self.show_notifications_menu(update)

    async def cycle_quiet_window(self, update: Update):
        """Cycle common quiet-hour ranges."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        if not is_auth:
            await self._send_auth_error(update)
            return

        presets = [(22, 8), (23, 7), (0, 6), (21, 6)]
        settings = self.db.get_user_settings(user_id)
        settings['notifications'] = self._get_notification_settings(settings)
        current = (
            int(settings['notifications'].get('quiet_hours_start', 22) or 22),
            int(settings['notifications'].get('quiet_hours_end', 8) or 8),
        )
        next_window = presets[(presets.index(current) + 1) % len(presets)] if current in presets else presets[0]
        settings['notifications']['quiet_hours_enabled'] = True
        settings['notifications']['quiet_hours_start'] = next_window[0]
        settings['notifications']['quiet_hours_end'] = next_window[1]
        self.db.update_user_settings(user_id, settings)
        await self.show_notifications_menu(update)

    async def cycle_timezone(self, update: Update):
        """Cycle commonly used UTC offsets for quiet-hour calculations."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        if not is_auth:
            await self._send_auth_error(update)
            return

        options = [-480, -300, -60, 0, 60, 120, 180, 330, 480]
        settings = self.db.get_user_settings(user_id)
        settings['notifications'] = self._get_notification_settings(settings)
        current = int(settings['notifications'].get('timezone_offset_minutes', 0) or 0)
        next_value = options[(options.index(current) + 1) % len(options)] if current in options else 0
        settings['notifications']['timezone_offset_minutes'] = next_value
        self.db.update_user_settings(user_id, settings)
        await self.show_notifications_menu(update)

    async def start_set_timezone_wizard(self, update: Update):
        """Start one-step wizard for exact UTC offset entry."""
        user = update.effective_user
        is_auth, _ = self._check_auth(user.id)
        if not is_auth:
            await self._send_auth_error(update)
            return

        scene = self.scene_manager.start_scene(user.id, 'set_timezone')
        if scene is None:
            await self._send_error(update, "Timezone setup is not available right now.")
            return

        message = (
            "🌍 **Set Timezone**\n\n"
            "Enter your UTC offset in one of these formats:\n"
            "• `UTC+05:30`\n"
            "• `+2`\n"
            "• `-04:00`\n"
            "• `Z` (for UTC)\n\n"
            "Valid range: UTC-12:00 to UTC+14:00"
        )

        keyboard = [[
            InlineKeyboardButton(
                f"{self.kb.EMOJI['cancel']} Cancel",
                callback_data=self.kb.encode_callback('cancel')
            )
        ]]

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
        if scene.scene_id == 'set_timezone':
            offset_minutes = self._parse_utc_offset(update.message.text.strip())
            if offset_minutes is None:
                await self._send_wizard_step(
                    update,
                    user.id,
                    "❌ Invalid format. Try examples: `UTC+05:30`, `+2`, `-04:00`, `Z`",
                    parse_mode='Markdown'
                )
                return True

            is_auth, user_id = self._check_auth(user.id)
            if not is_auth:
                await self._send_auth_error(update)
                return True

            settings = self.db.get_user_settings(user_id)
            settings['notifications'] = self._get_notification_settings(settings)
            settings['notifications']['timezone_offset_minutes'] = offset_minutes
            self.db.update_user_settings(user_id, settings)
            self.scene_manager.complete_scene(user.id)

            await self._send_wizard_step(
                update,
                user.id,
                f"✅ Timezone updated to {self._format_utc_offset(offset_minutes)}"
            )
            await self.show_notifications_menu(update)
            return True

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

    async def _send_wizard_step(self, update: Update, telegram_id: int, text: str, reply_markup=None, parse_mode='Markdown'):
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
                        parse_mode=parse_mode
                    )
                    return
                except Exception:
                    pass

        if update.message:
            sent = await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            sent = await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

        if scene and sent:
            self.scene_manager.set_scene_data(telegram_id, 'wizard_chat_id', sent.chat_id)
            self.scene_manager.set_scene_data(telegram_id, 'wizard_message_id', sent.message_id)
