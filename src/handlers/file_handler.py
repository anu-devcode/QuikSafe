"""
QuikSafe Bot - File Handler
Handles file storage and retrieval.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from src.database.db_manager import DatabaseManager
from src.security.encryption import EncryptionManager
from src.security.auth import SessionManager
from src.utils.validators import validate_file_name, parse_tags_from_text
from src.utils.formatters import format_file_list
import logging

logger = logging.getLogger(__name__)


class FileHandler:
    """Handles file storage and retrieval operations."""
    
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager, session: SessionManager):
        """Initialize file handler."""
        self.db = db
        self.encryption = encryption
        self.session = session
    
    def _check_auth(self, telegram_id: int) -> tuple[bool, str]:
        """Check if user is authenticated."""
        if not self.session.is_authenticated(telegram_id):
            return False, None
        
        session_data = self.session.get_session(telegram_id)
        return True, session_data.get('user_id')
    
    # ==================== Save File ====================
    
    async def handle_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle file upload."""
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
            file = update.message.photo[-1]  # Get largest photo
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
        
        # Parse tags from caption
        tags = parse_tags_from_text(description) if description else []
        
        # Encrypt description
        encrypted_description = self.encryption.encrypt(description) if description else ""
        
        # Save file metadata to database
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
            await update.message.reply_text(
                f"✅ **File Saved!**\n\n"
                f"📎 {file_name}\n"
                f"Size: {self._format_size(file_size)}\n"
                f"Tags: {', '.join(tags) if tags else 'None'}\n\n"
                f"ID: `{result['id']}`",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Failed to save file. Please try again.")
    
    # ==================== List Files ====================
    
    async def list_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all saved files."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        # Get optional file name filter
        file_name_filter = None
        if context.args:
            file_name_filter = ' '.join(context.args)
        
        files = self.db.get_files(user_id, file_name_filter)
        
        message_text = format_file_list(files)
        await update.message.reply_text(message_text, parse_mode='Markdown')
    
    # ==================== Get File ====================
    
    async def get_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Retrieve a file."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /getfile <file_name_or_id>\n"
                "Use /listfiles to see available files"
            )
            return
        
        search_term = ' '.join(context.args)
        
        # Try to find file by name or ID
        files = self.db.get_files(user_id, search_term)
        
        if not files:
            await update.message.reply_text(f"❌ No file found matching '{search_term}'")
            return
        
        if len(files) > 1:
            await update.message.reply_text(
                f"Found {len(files)} matches:\n\n" +
                "\n".join([f"{i+1}. {f['file_name']} (ID: `{f['id']}`)" 
                          for i, f in enumerate(files)]) +
                "\n\nPlease be more specific.",
                parse_mode='Markdown'
            )
            return
        
        # Send the file
        file_entry = files[0]
        file_id = file_entry['file_id']
        file_name = file_entry['file_name']
        
        # Decrypt description
        description = ""
        if file_entry.get('encrypted_description'):
            description = self.encryption.decrypt(file_entry['encrypted_description'])
        
        caption = f"📎 {file_name}"
        if description:
            caption += f"\n\n{description}"
        
        try:
            # Send file based on type
            if 'image' in file_entry['file_type']:
                await update.message.reply_photo(photo=file_id, caption=caption)
            elif 'video' in file_entry['file_type']:
                await update.message.reply_video(video=file_id, caption=caption)
            elif 'audio' in file_entry['file_type']:
                await update.message.reply_audio(audio=file_id, caption=caption)
            else:
                await update.message.reply_document(document=file_id, caption=caption)
        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            await update.message.reply_text("❌ Failed to retrieve file. It may have been deleted from Telegram.")
    
    # ==================== Delete File ====================
    
    async def delete_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete a file."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /deletefile <file_id>\n"
                "Use /listfiles to see file IDs"
            )
            return
        
        file_id = context.args[0]
        
        success = self.db.delete_file(file_id, user_id)
        
        if success:
            await update.message.reply_text("✅ File deleted successfully!")
        else:
            await update.message.reply_text("❌ Failed to delete file. Check the ID and try again.")
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
