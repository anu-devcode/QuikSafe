"""
QuikSafe Bot - AI Handler
Handles AI-powered features like auto-organization and summarization.
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.database.db_manager import DatabaseManager
from src.security.encryption import EncryptionManager
from src.security.auth import SessionManager
from src.ai.gemini_client import GeminiClient
from src.utils.keyboard_builder import KeyboardBuilder
import logging

logger = logging.getLogger(__name__)


class AIHandler:
    """Handles AI operations."""
    
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager, session: SessionManager, ai_client: GeminiClient):
        """
        Initialize AI handler.
        
        Args:
            db: Database manager instance
            encryption: Encryption manager instance
            session: Session manager instance
            ai_client: AI client instance
        """
        self.db = db
        self.encryption = encryption
        self.session = session
        self.ai_client = ai_client
        self.kb = KeyboardBuilder()
    
    def _check_auth(self, telegram_id: int) -> tuple[bool, str]:
        """Check if user is authenticated."""
        if not self.session.is_authenticated(telegram_id):
            return False, None
        
        session_data = self.session.get_session(telegram_id)
        return True, session_data.get('user_id')
    
    async def show_menu(self, update: Update):
        """Show AI menu."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        message = (
            "🤖 **AI Assistant**\n\n"
            "I can help you organize and understand your data.\n\n"
            "Choose an action:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🏷️ Auto-Tag Items", callback_data=self.kb.encode_callback('ai_tag')),
                InlineKeyboardButton("📝 Summarize Tasks", callback_data=self.kb.encode_callback('ai_summarize_tasks'))
            ],
            [
                InlineKeyboardButton("🔍 Smart Search", callback_data=self.kb.encode_callback('quick_search'))
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

    async def handle_auto_tag(self, update: Update):
        """Suggest tags for untagged items."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        await update.callback_query.edit_message_text("🤖 Analyzing your data... This may take a moment.")
        
        # Get untagged passwords (example)
        passwords = self.db.get_passwords(user_id)
        untagged = [p for p in passwords if not p.get('tags')]
        
        if not untagged:
            await update.callback_query.edit_message_text(
                "✅ All your items are already tagged!",
                reply_markup=self.kb.back_to_menu('menu_ai')
            )
            return
            
        # Process first 3 untagged items to avoid hitting rate limits
        suggestions = []
        for item in untagged[:3]:
            service_name = item['service_name']
            suggested = self.ai_client.suggest_tags(service_name, "password")
            suggestions.append(f"• **{service_name}**: {', '.join(suggested)}")
            
            # Auto-save tags (optional, for now just suggest)
            # self.db.update_password_tags(item['id'], suggested)
            
        msg = (
            "🏷️ **Tag Suggestions**\n\n"
            "Here are some suggestions for your untagged items:\n\n" +
            "\n".join(suggestions) +
            "\n\n(Auto-applying tags is coming soon!)"
        )
        
        await update.callback_query.edit_message_text(
            msg,
            reply_markup=self.kb.back_to_menu('menu_ai'),
            parse_mode='Markdown'
        )

    async def handle_summarize_tasks(self, update: Update):
        """Summarize tasks."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        await update.callback_query.edit_message_text("🤖 Generating summary...")
        
        tasks = self.db.get_tasks(user_id)
        
        # Decrypt content
        for task in tasks:
            task['encrypted_content'] = self.encryption.decrypt(task['encrypted_content'])
            
        summary = self.ai_client.summarize_tasks(tasks)
        
        await update.callback_query.edit_message_text(
            f"📝 **Task Summary**\n\n{summary}",
            reply_markup=self.kb.back_to_menu('menu_ai'),
            parse_mode='Markdown'
        )

    async def _send_auth_error(self, update: Update):
        """Send authentication error message."""
        msg = "❌ Session expired. Please /start again."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
