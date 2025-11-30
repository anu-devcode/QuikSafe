"""
QuikSafe Bot - Password Handler
Handles password management with modern inline UI and wizards.
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from src.database.db_manager import DatabaseManager
from src.security.encryption import EncryptionManager
from src.security.auth import SessionManager
from src.utils.validators import validate_service_name, validate_username, validate_password, parse_tags_from_text, check_password_strength
from src.utils.formatters import format_password_list, format_password_details
from src.utils.keyboard_builder import KeyboardBuilder
from src.utils.scene_manager import SceneManager
import logging
import asyncio

logger = logging.getLogger(__name__)

# Legacy conversation states (kept for backward compatibility if needed)
AWAITING_SERVICE, AWAITING_USERNAME, AWAITING_PASSWORD, AWAITING_TAGS = range(4)


class PasswordHandler:
    """Handles password management operations."""
    
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager, session: SessionManager, scene_manager: SceneManager):
        """
        Initialize password handler.
        
        Args:
            db: Database manager instance
            encryption: Encryption manager instance
            session: Session manager instance
            scene_manager: Scene manager instance
        """
        self.db = db
        self.encryption = encryption
        self.session = session
        self.kb = KeyboardBuilder()
        self.scene_manager = scene_manager
    
    def _check_auth(self, telegram_id: int) -> tuple[bool, str]:
        """Check if user is authenticated."""
        if not self.session.is_authenticated(telegram_id):
            return False, None
        
        session_data = self.session.get_session(telegram_id)
        return True, session_data.get('user_id')
    
    # ==================== Inline UI Methods ====================
    
    async def show_password_list(self, update: Update, page: int = 0):
        """Show paginated list of passwords."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
        
        # Get all passwords
        passwords = self.db.get_passwords(user_id)
        
        # Pagination logic
        items_per_page = 5
        total_pages = (len(passwords) + items_per_page - 1) // items_per_page
        
        if page >= total_pages and total_pages > 0:
            page = total_pages - 1
        
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_page_items = passwords[start_idx:end_idx]
        
        # Build message
        if not passwords:
            message = "🔐 **No passwords saved yet.**\n\nUse 'Save New Password' to add one!"
        else:
            message = f"🔐 **Your Passwords** ({len(passwords)} total)\n\n"
            for i, pwd in enumerate(current_page_items, 1):
                service = pwd.get('service_name', 'Unknown')
                tags = pwd.get('tags', [])
                tag_str = f" {', '.join(tags)}" if tags else ""
                message += f"{i}. **{service}**{tag_str}\n"
        
        # Build keyboard
        keyboard = []
        
        # Item buttons
        for pwd in current_page_items:
            keyboard.append([
                InlineKeyboardButton(
                    f"👁️ {pwd['service_name']}",
                    callback_data=self.kb.encode_callback('password_view', pid=pwd['id'])
                )
            ])
        
        # Pagination buttons
        if total_pages > 1:
            pagination = self.kb.pagination(page, total_pages, 'password_list')
            keyboard.append(pagination)
        
        # Action buttons
        keyboard.append([
            InlineKeyboardButton(
                f"{self.kb.EMOJI['add']} Add New",
                callback_data=self.kb.encode_callback('password_save_start')
            ),
            InlineKeyboardButton(
                f"{self.kb.EMOJI['search']} Search",
                callback_data=self.kb.encode_callback('password_search')
            )
        ])
        
        keyboard.append([
            InlineKeyboardButton(
                f"{self.kb.EMOJI['back']} Back to Menu",
                callback_data=self.kb.encode_callback('main_menu')
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Handle both Update and CallbackQuery objects
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        elif hasattr(update, 'edit_message_text'):
            await update.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    async def show_password_details(self, update: Update, password_id: str):
        """Show details for a specific password."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
        
        # Get password details
        # Note: We need a method to get by ID, currently using get_passwords filter
        # Assuming get_passwords can filter or we iterate. 
        # Ideally DB manager should have get_password_by_id. 
        # For now, let's fetch all and find (inefficient but works for prototype)
        # TODO: Add get_password_by_id to DB manager
        passwords = self.db.get_passwords(user_id)
        password_entry = next((p for p in passwords if str(p['id']) == str(password_id)), None)
        
        if not password_entry:
            await self._send_error(update, "Password not found.")
            return
        
        # Decrypt
        decrypted_username = self.encryption.decrypt(password_entry['encrypted_username']) if password_entry['encrypted_username'] else 'N/A'
        decrypted_password = self.encryption.decrypt(password_entry['encrypted_password'])
        
        message = format_password_details(password_entry, decrypted_username, decrypted_password)
        
        # Action buttons
        reply_markup = self.kb.password_actions(password_id)
        
        # Handle both Update and CallbackQuery objects
        if hasattr(update, 'edit_message_text'):
            await update.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            # Auto-delete (handled by client side usually, but we can schedule a delete edit)
            # For inline messages, we can edit it back to a "hidden" state after timeout
            # But that's complex to manage state. We'll rely on user explicit hide or delete.
        
    async def start_save_wizard(self, update: Update):
        """Start the save password wizard."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        self.scene_manager.start_scene(user.id, 'save_password')
        
        message = (
            "🔐 **Save New Password**\n\n"
            "Step 1/4: **Service Name**\n"
            "Enter the name of the service (e.g., Gmail, Netflix):"
        )
        
        keyboard = [[
            InlineKeyboardButton(
                f"{self.kb.EMOJI['cancel']} Cancel",
                callback_data=self.kb.encode_callback('cancel')
            )
        ]]
        
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

    async def handle_wizard_input(self, update: Update):
        """Handle text input for active wizard."""
        user = update.effective_user
        if not self.scene_manager.has_active_scene(user.id):
            return False
            
        scene = self.scene_manager.get_scene(user.id)
        if scene.scene_id != 'save_password':
            return False
            
        current_step = scene.get_current_step()
        text = update.message.text.strip()
        
        # Delete user message to keep chat clean
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete wizard input message: {e}")
            
        if current_step == 'service_name':
            is_valid, error = validate_service_name(text)
            if not is_valid:
                await update.message.reply_text(f"❌ {error}\nPlease try again:")
                return True
                
            self.scene_manager.set_scene_data(user.id, 'service_name', text)
            self.scene_manager.advance_scene(user.id)
            
            await update.message.reply_text(
                f"✅ Service: **{text}**\n\n"
                "Step 2/4: **Username/Email**\n"
                "Enter username (or type 'skip'):",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Skip", callback_data=self.kb.encode_callback('wizard_skip'))
                ]])
            )
            
        elif current_step == 'username':
            username = text if text.lower() != 'skip' else ''
            if username:
                is_valid, error = validate_username(username)
                if not is_valid:
                    await update.message.reply_text(f"❌ {error}\nPlease try again:")
                    return True
            
            self.scene_manager.set_scene_data(user.id, 'username', username)
            self.scene_manager.advance_scene(user.id)
            
            await update.message.reply_text(
                "Step 3/4: **Password**\n"
                "Enter the password:",
                parse_mode='Markdown'
            )
            
        elif current_step == 'password':
            is_valid, error = validate_password(text)
            if not is_valid:
                await update.message.reply_text(f"❌ {error}\nPlease try again:")
                return True
            
            # Check strength
            score, strength_msg = check_password_strength(text)
                
            self.scene_manager.set_scene_data(user.id, 'password', text)
            self.scene_manager.advance_scene(user.id)
            
            await update.message.reply_text(
                f"Password Strength: {strength_msg}\n\n"
                "Step 4/4: **Tags**\n"
                "Enter tags (e.g. #work) or skip:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Skip", callback_data=self.kb.encode_callback('wizard_skip'))
                ]])
            )
            
        elif current_step == 'tags':
            tags = parse_tags_from_text(text) if text.lower() != 'skip' else []
            self.scene_manager.set_scene_data(user.id, 'tags', tags)
            
            # Save data
            data = self.scene_manager.complete_scene(user.id)
            await self._save_password_data(update, data)
            
        return True

    async def handle_wizard_skip(self, update: Update):
        """Handle skip button in wizard."""
        user = update.effective_user
        scene = self.scene_manager.get_scene(user.id)
        if not scene:
            return
            
        current_step = scene.get_current_step()
        
        if current_step == 'username':
            self.scene_manager.set_scene_data(user.id, 'username', '')
            self.scene_manager.advance_scene(user.id)
            await update.callback_query.message.reply_text(
                "Step 3/4: **Password**\n"
                "Enter the password:",
                parse_mode='Markdown'
            )
            
        elif current_step == 'tags':
            self.scene_manager.set_scene_data(user.id, 'tags', [])
            data = self.scene_manager.complete_scene(user.id)
            await self._save_password_data(update, data)

    async def _save_password_data(self, update: Update, data: dict):
        """Internal method to save password to DB."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        service_name = data['service_name']
        username = data.get('username', '')
        password = data['password']
        tags = data.get('tags', [])
        
        encrypted_username = self.encryption.encrypt(username) if username else ''
        encrypted_password = self.encryption.encrypt(password)
        
        result = self.db.save_password(
            user_id=user_id,
            service_name=service_name,
            encrypted_username=encrypted_username,
            encrypted_password=encrypted_password,
            tags=tags
        )
        
        msg = (
            f"✅ **Password Saved!**\n\n"
            f"Service: {service_name}\n"
            f"Tags: {', '.join(tags) if tags else 'None'}"
        )
        
        keyboard = [[
            InlineKeyboardButton(
                f"{self.kb.EMOJI['view']} View List",
                callback_data=self.kb.encode_callback('password_list', p=0)
            ),
            InlineKeyboardButton(
                f"{self.kb.EMOJI['add']} Add Another",
                callback_data=self.kb.encode_callback('password_save_start')
            )
        ]]
        
        if update.callback_query:
            await update.callback_query.message.reply_text(
                msg, 
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                msg, 
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    async def delete_password(self, update: Update, password_id: str):
        """Delete a password."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        if self.db.delete_password(password_id, user_id):
            await update.callback_query.answer("Password deleted")
            await self.show_password_list(update, 0)
        else:
            await update.callback_query.answer("Failed to delete", show_alert=True)

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

    # ==================== Legacy Command Handlers ====================
    # Kept for backward compatibility but redirecting to new UI where appropriate
    
    async def save_password_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Legacy start password saving flow."""
        await self.start_save_wizard(update)
        return ConversationHandler.END

    async def get_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Legacy get password."""
        # Redirect to list view
        await self.show_password_list(update)

    async def list_passwords(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Legacy list passwords."""
        await self.show_password_list(update)

    async def delete_password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Legacy delete password."""
        await update.message.reply_text("Please use the 'Delete' button in the password list.")
        await self.show_password_list(update)

    def get_save_handler(self) -> ConversationHandler:
        """
        Get conversation handler.
        Note: We are moving away from ConversationHandler to SceneManager + MessageHandler
        But we keep this to not break main.py registration yet.
        """
        # We return a dummy handler or the old one if we want to support mixed mode.
        # For now, let's return the old structure but it immediately delegates to new wizard
        # This is a bit tricky because ConversationHandler expects states.
        # To fully migrate, we should remove ConversationHandler from main.py and use a global MessageHandler
        # that checks SceneManager.
        
        # For this step, I will return the OLD handler structure but updated to use new methods
        # to ensure main.py doesn't crash.
        return ConversationHandler(
            entry_points=[CommandHandler('savepassword', self.save_password_start)],
            states={
                # We won't actually use these states if we switch to SceneManager
                # But we need to define them to satisfy the type
                AWAITING_SERVICE: [MessageHandler(filters.TEXT, self.save_password_start)],
            },
            fallbacks=[CommandHandler('cancel', self.save_password_start)]
        )
