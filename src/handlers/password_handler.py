"""
QuikSafe Bot - Password Handler
Handles password management commands.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from src.database.db_manager import DatabaseManager
from src.security.encryption import EncryptionManager
from src.security.auth import SessionManager
from src.utils.validators import validate_service_name, validate_username, validate_password, parse_tags_from_text
from src.utils.formatters import format_password_list, format_password_details
import logging
import asyncio

logger = logging.getLogger(__name__)

# Conversation states
AWAITING_SERVICE, AWAITING_USERNAME, AWAITING_PASSWORD, AWAITING_TAGS = range(4)


class PasswordHandler:
    """Handles password management operations."""
    
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager, session: SessionManager):
        """
        Initialize password handler.
        
        Args:
            db: Database manager instance
            encryption: Encryption manager instance
            session: Session manager instance
        """
        self.db = db
        self.encryption = encryption
        self.session = session
    
    def _check_auth(self, telegram_id: int) -> tuple[bool, str]:
        """Check if user is authenticated."""
        if not self.session.is_authenticated(telegram_id):
            return False, None
        
        session_data = self.session.get_session(telegram_id)
        return True, session_data.get('user_id')
    
    # ==================== Save Password ====================
    
    async def save_password_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start password saving flow."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "🔐 **Save New Password**\n\n"
            "Enter the service name (e.g., Gmail, Facebook, GitHub):"
        )
        return AWAITING_SERVICE
    
    async def receive_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive service name."""
        service_name = update.message.text.strip()
        
        is_valid, error = validate_service_name(service_name)
        if not is_valid:
            await update.message.reply_text(f"❌ {error}\n\nPlease try again:")
            return AWAITING_SERVICE
        
        context.user_data['service_name'] = service_name
        
        await update.message.reply_text(
            f"Service: **{service_name}**\n\n"
            "Enter the username/email (or type 'skip' if not applicable):",
            parse_mode='Markdown'
        )
        return AWAITING_USERNAME
    
    async def receive_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive username."""
        username = update.message.text.strip()
        
        if username.lower() != 'skip':
            is_valid, error = validate_username(username)
            if not is_valid:
                await update.message.reply_text(f"❌ {error}\n\nPlease try again:")
                return AWAITING_USERNAME
            
            context.user_data['username'] = username
        else:
            context.user_data['username'] = ''
        
        await update.message.reply_text("Enter the password:")
        return AWAITING_PASSWORD
    
    async def receive_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive password."""
        password = update.message.text
        
        # Delete message for security
        await update.message.delete()
        
        is_valid, error = validate_password(password)
        if not is_valid:
            await update.message.reply_text(f"❌ {error}\n\nPlease try again:")
            return AWAITING_PASSWORD
        
        context.user_data['password'] = password
        
        await update.message.reply_text(
            "Add tags for organization (optional)?\n"
            "Use hashtags like: #work #important\n"
            "Or type 'skip' to finish:"
        )
        return AWAITING_TAGS
    
    async def receive_tags(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive tags and save password."""
        tags_text = update.message.text.strip()
        
        tags = []
        if tags_text.lower() != 'skip':
            tags = parse_tags_from_text(tags_text)
        
        # Get session data
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        # Encrypt sensitive data
        service_name = context.user_data['service_name']
        username = context.user_data.get('username', '')
        password = context.user_data['password']
        
        encrypted_username = self.encryption.encrypt(username) if username else ''
        encrypted_password = self.encryption.encrypt(password)
        
        # Save to database
        result = self.db.save_password(
            user_id=user_id,
            service_name=service_name,
            encrypted_username=encrypted_username,
            encrypted_password=encrypted_password,
            tags=tags
        )
        
        if result:
            await update.message.reply_text(
                f"✅ Password for **{service_name}** saved successfully!\n\n"
                f"Tags: {', '.join(tags) if tags else 'None'}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Failed to save password. Please try again.")
        
        # Clear user data
        context.user_data.clear()
        
        return ConversationHandler.END
    
    # ==================== Get Password ====================
    
    async def get_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Retrieve a password."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        # Get service name from command
        if not context.args:
            await update.message.reply_text(
                "Usage: /getpassword <service_name>\n"
                "Example: /getpassword gmail"
            )
            return
        
        service_name = ' '.join(context.args)
        
        # Get passwords from database
        passwords = self.db.get_passwords(user_id, service_name)
        
        if not passwords:
            await update.message.reply_text(f"❌ No password found for '{service_name}'")
            return
        
        # If multiple matches, show list
        if len(passwords) > 1:
            await update.message.reply_text(
                f"Found {len(passwords)} matches:\n\n" +
                "\n".join([f"{i+1}. {pwd['service_name']} (ID: `{pwd['id']}`)" 
                          for i, pwd in enumerate(passwords)]) +
                "\n\nUse /getpassword <exact_service_name> to retrieve a specific one.",
                parse_mode='Markdown'
            )
            return
        
        # Decrypt and show password
        password_entry = passwords[0]
        decrypted_username = self.encryption.decrypt(password_entry['encrypted_username']) if password_entry['encrypted_username'] else 'N/A'
        decrypted_password = self.encryption.decrypt(password_entry['encrypted_password'])
        
        message_text = format_password_details(password_entry, decrypted_username, decrypted_password)
        
        sent_message = await update.message.reply_text(message_text, parse_mode='Markdown')
        
        # Delete message after 60 seconds for security
        await asyncio.sleep(60)
        try:
            await sent_message.delete()
        except:
            pass
    
    # ==================== List Passwords ====================
    
    async def list_passwords(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all saved passwords."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        passwords = self.db.get_passwords(user_id)
        message_text = format_password_list(passwords)
        
        await update.message.reply_text(message_text, parse_mode='Markdown')
    
    # ==================== Delete Password ====================
    
    async def delete_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete a password."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /deletepassword <password_id>\n"
                "Use /listpasswords to see IDs"
            )
            return
        
        password_id = context.args[0]
        
        success = self.db.delete_password(password_id, user_id)
        
        if success:
            await update.message.reply_text("✅ Password deleted successfully!")
        else:
            await update.message.reply_text("❌ Failed to delete password. Check the ID and try again.")
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel operation."""
        context.user_data.clear()
        await update.message.reply_text("Operation cancelled.")
        return ConversationHandler.END
    
    def get_save_handler(self) -> ConversationHandler:
        """Get conversation handler for saving passwords."""
        return ConversationHandler(
            entry_points=[CommandHandler('savepassword', self.save_password_start)],
            states={
                AWAITING_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_service)],
                AWAITING_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_username)],
                AWAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_password)],
                AWAITING_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_tags)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
