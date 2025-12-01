"""
QuikSafe Bot - File Handler
Handles file storage and retrieval with modern inline UI.
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from src.database.db_manager import DatabaseManager
from src.security.encryption import EncryptionManager
from src.security.auth import SessionManager
from src.utils.validators import validate_file_name, parse_tags_from_text
from src.utils.formatters import format_file_list, format_file_details
from src.utils.keyboard_builder import KeyboardBuilder
from src.utils.scene_manager import SceneManager
import logging

logger = logging.getLogger(__name__)


class FileHandler:
    """Handles file storage and retrieval operations."""
    
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager, session: SessionManager, scene_manager: SceneManager):
        """
        Initialize file handler.
        
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
    
    async def show_file_list(self, update: Update, page: int = 0, type_filter: str = None):
        """Show paginated list of files."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
        
        # Get files (TODO: Add type filter in DB)
        files = self.db.get_files(user_id)
        
        # Filter by type if requested
        if type_filter:
            files = [f for f in files if type_filter in f['file_type']]
        
        # Pagination logic
        items_per_page = 5
        total_pages = (len(files) + items_per_page - 1) // items_per_page
        
        if page >= total_pages and total_pages > 0:
            page = total_pages - 1
        
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_page_items = files[start_idx:end_idx]
        
        # Build message
        filter_text = f" ({type_filter})" if type_filter else ""
        if not files:
            message = f"📁 **No files found{filter_text}.**\n\nSend any file to the bot to save it!"
        else:
            message = f"📁 **Your Files**{filter_text} ({len(files)} total)\n\n"
            for i, f in enumerate(current_page_items, 1):
                icon = "🖼️" if "image" in f['file_type'] else "📄"
                escaped_name = self._escape_markdown(f['file_name'])
                message += f"{i}. {icon} **{escaped_name}** ({self._format_size(f['file_size'])})\n"
        
        # Build keyboard
        keyboard = []
        
        # Item buttons
        for f in current_page_items:
            keyboard.append([
                InlineKeyboardButton(
                    f"👁️ {f['file_name'][:20]}...",
                    callback_data=self.kb.encode_callback('file_view', fid=f['id'])
                )
            ])
        
        # Pagination buttons
        if total_pages > 1:
            pagination = self.kb.pagination(page, total_pages, 'file_list')
            keyboard.append(pagination)
        
        # Filter buttons
        keyboard.append([
            InlineKeyboardButton("All", callback_data=self.kb.encode_callback('file_list', p=0)),
            InlineKeyboardButton("Images", callback_data=self.kb.encode_callback('file_list', p=0, f='image')),
            InlineKeyboardButton("Docs", callback_data=self.kb.encode_callback('file_list', p=0, f='application'))
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
            # update is an Update object
            await update.callback_query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        elif hasattr(update, 'edit_message_text'):
            # update is a CallbackQuery object
            await update.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # update is a Message object
            await update.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    async def show_file_details(self, update: Update, file_id: str):
        """Show details for a specific file."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
        
        # Get file details
        files = self.db.get_files(user_id)
        file_entry = next((f for f in files if str(f['id']) == str(file_id)), None)
        
        if not file_entry:
            await self._send_error(update, "File not found.")
            return
        
        # Decrypt description
        description = ""
        if file_entry.get('encrypted_description'):
            description = self.encryption.decrypt(file_entry['encrypted_description'])
        
        message = format_file_details(file_entry, description)
        
        # Action buttons
        reply_markup = self.kb.file_actions(file_id)
        
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

    async def download_file(self, update: Update, file_id: str):
        """Send the file to the user."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        # Get file details
        files = self.db.get_files(user_id)
        file_entry = next((f for f in files if str(f['id']) == str(file_id)), None)
        
        if not file_entry:
            await update.callback_query.answer("File not found", show_alert=True)
            return
            
        tg_file_id = file_entry['file_id']
        caption = f"📎 {file_entry['file_name']}"
        
        try:
            # Send file based on type
            if 'image' in file_entry['file_type']:
                await update.callback_query.message.reply_photo(photo=tg_file_id, caption=caption)
            elif 'video' in file_entry['file_type']:
                await update.callback_query.message.reply_video(video=tg_file_id, caption=caption)
            elif 'audio' in file_entry['file_type']:
                await update.callback_query.message.reply_audio(audio=tg_file_id, caption=caption)
            else:
                await update.callback_query.message.reply_document(document=tg_file_id, caption=caption)
            
            await update.callback_query.answer("File sent!")
        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            await update.callback_query.answer("Failed to retrieve file", show_alert=True)

    async def delete_file(self, update: Update, file_id: str):
        """Delete a file."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        if self.db.delete_file(file_id, user_id):
            await update.callback_query.answer("File deleted")
            await self.show_file_list(update, 0)
        else:
            await update.callback_query.answer("Failed to delete", show_alert=True)

    async def share_file(self, update: Update, file_id: str):
        """Share a file (send it to the chat)."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        # Get file details
        files = self.db.get_files(user_id)
        file_entry = next((f for f in files if str(f['id']) == str(file_id)), None)
        
        if not file_entry:
            await update.callback_query.answer("File not found", show_alert=True)
            return
            
        tg_file_id = file_entry['file_id']
        caption = f"📎 {file_entry['file_name']}"
        
        try:
            # Send file based on type
            if 'image' in file_entry['file_type']:
                await update.callback_query.message.reply_photo(photo=tg_file_id, caption=caption)
            elif 'video' in file_entry['file_type']:
                await update.callback_query.message.reply_video(video=tg_file_id, caption=caption)
            elif 'audio' in file_entry['file_type']:
                await update.callback_query.message.reply_audio(audio=tg_file_id, caption=caption)
            else:
                await update.callback_query.message.reply_document(document=tg_file_id, caption=caption)
            
            await update.callback_query.answer("File shared!")
        except Exception as e:
            logger.error(f"Failed to share file: {e}")
            await update.callback_query.answer("Failed to share file", show_alert=True)

    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle file upload (direct message)."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        # Get file from message
        file = None
        file_name = None
        file_type = None
        file_size = 0
        
        if update.message.document:
            file = update.message.document
            file_name = file.file_name
            file_type = file.mime_type
            file_size = file.file_size
        elif update.message.photo:
            file = update.message.photo[-1]
            file_name = f"photo_{file.file_id[:8]}.jpg"
            file_type = "image/jpeg"
            file_size = file.file_size
        elif update.message.video:
            file = update.message.video
            file_name = file.file_name or f"video_{file.file_id[:8]}.mp4"
            file_type = file.mime_type
            file_size = file.file_size
        elif update.message.audio:
            file = update.message.audio
            file_name = file.file_name or f"audio_{file.file_id[:8]}.mp3"
            file_type = file.mime_type
            file_size = file.file_size
        elif update.message.voice:
            file = update.message.voice
            file_name = f"voice_{file.file_id[:8]}.ogg"
            file_type = file.mime_type
            file_size = file.file_size
        else:
            await update.message.reply_text("❌ Unsupported file type.")
            return
        
        # Get caption as description
        description = update.message.caption or ""
        tags = parse_tags_from_text(description) if description else []
        encrypted_description = self.encryption.encrypt(description) if description else ""
        
        # Save file metadata
        result = self.db.save_file(
            user_id=user_id,
            file_id=file.file_id,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            encrypted_description=encrypted_description,
            tags=tags
        )
        
        if result:
            escaped_name = self._escape_markdown(file_name)
            escaped_tags = [self._escape_markdown(t) for t in tags]
            
            msg = (
                f"✅ **File Saved!**\n\n"
                f"📎 {escaped_name}\n"
                f"Size: {self._format_size(file_size)}\n"
                f"Tags: {', '.join(escaped_tags) if escaped_tags else 'None'}"
            )
            
            keyboard = [[
                InlineKeyboardButton(
                    f"{self.kb.EMOJI['view']} View List",
                    callback_data=self.kb.encode_callback('file_list', p=0)
                ),
                InlineKeyboardButton(
                    f"{self.kb.EMOJI['add']} Upload Another",
                    callback_data=self.kb.encode_callback('quick_upload_file')
                )
            ]]
            
            await update.message.reply_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            # Delete the user's file message to save space and privacy
            try:
                await update.message.delete()
            except Exception as e:
                logger.warning(f"Could not delete file message: {e}")
                
        else:
            await update.message.reply_text("❌ Failed to save file. Please try again.")

    def _format_size(self, size_bytes: int) -> str:
        """Format file size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

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
    
    async def list_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Legacy list files."""
        await self.show_file_list(update)

    async def get_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Legacy get file."""
        # Redirect to list view as getting by name is hard to map to ID in new UI
        await update.message.reply_text("Please use the 'Download' button in the file list.")
        await self.show_file_list(update)

    async def delete_file_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Legacy delete file."""
        await update.message.reply_text("Please use the 'Delete' button in the file list.")
        await self.show_file_list(update)

    def _escape_markdown(self, text: str) -> str:
        """Escape special characters for Markdown."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f"\\{char}")
        return text
