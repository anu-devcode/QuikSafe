"""
QuikSafe Bot - Search Handler
Handles AI-powered search with interactive inline results.
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler
from src.database.db_manager import DatabaseManager
from src.security.encryption import EncryptionManager
from src.security.auth import SessionManager
from src.ai.gemini_client import GeminiClient
from src.utils.keyboard_builder import KeyboardBuilder
import logging

logger = logging.getLogger(__name__)


class SearchHandler:
    """Handles AI-powered search and summarization."""
    
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager, 
                 session: SessionManager, ai_client: GeminiClient):
        """Initialize search handler."""
        self.db = db
        self.encryption = encryption
        self.session = session
        self.ai = ai_client
        self.kb = KeyboardBuilder()
    
    def _check_auth(self, telegram_id: int) -> tuple[bool, str]:
        """Check if user is authenticated."""
        if not self.session.is_authenticated(telegram_id):
            return False, None
        
        session_data = self.session.get_session(telegram_id)
        return True, session_data.get('user_id')
    
    # ==================== Search ====================
    
    async def search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """AI-powered search across all data."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
        
        query = ""
        if context.args:
            query = ' '.join(context.args)
        
        if not query:
            await update.message.reply_text(
                "🔍 **Smart Search**\n\n"
                "Usage: /search <query>\n"
                "Example: `/search work passwords`",
                parse_mode='Markdown'
            )
            return
        
        await update.message.reply_text(f"🔍 Searching for '{query}'...")
        
        # Get all data
        passwords = self.db.get_passwords(user_id)
        tasks = self.db.get_tasks(user_id)
        files = self.db.get_files(user_id)
        
        # Decrypt task content for search
        for task in tasks:
            task['encrypted_content'] = self.encryption.decrypt(task['encrypted_content'])
        
        # Search using AI
        try:
            password_results = self.ai.search_content(query, passwords, "passwords")
            task_results = self.ai.search_content(query, tasks, "tasks")
            file_results = self.ai.search_content(query, files, "files")
            
            total_results = len(password_results) + len(task_results) + len(file_results)
            
            if total_results == 0:
                await update.message.reply_text(
                    f"❌ No results found for '{query}'.\n"
                    "Try different keywords or browse categories.",
                    reply_markup=self.kb.back_to_menu('main')
                )
                return
            
            message = f"🔍 **Found {total_results} results for '{query}'**\n\n"
            keyboard = []
            
            # Passwords
            if password_results:
                message += "**🔐 Passwords**\n"
                for p in password_results[:3]:  # Limit to 3 inline
                    message += f"• {p['service_name']}\n"
                    keyboard.append([
                        InlineKeyboardButton(
                            f"🔐 {p['service_name']}",
                            callback_data=self.kb.encode_callback('password_view', password_id=p['id'])
                        )
                    ])
                message += "\n"
            
            # Tasks
            if task_results:
                message += "**✅ Tasks**\n"
                for t in task_results[:3]:
                    content = t['encrypted_content']
                    message += f"• {content[:30]}...\n"
                    keyboard.append([
                        InlineKeyboardButton(
                            f"✅ {content[:20]}...",
                            callback_data=self.kb.encode_callback('task_view', task_id=t['id'])
                        )
                    ])
                message += "\n"
            
            # Files
            if file_results:
                message += "**📁 Files**\n"
                for f in file_results[:3]:
                    message += f"• {f['file_name']}\n"
                    keyboard.append([
                        InlineKeyboardButton(
                            f"📁 {f['file_name'][:20]}...",
                            callback_data=self.kb.encode_callback('file_view', file_id=f['id'])
                        )
                    ])
            
            keyboard.append([
                InlineKeyboardButton(f"{self.kb.EMOJI['back']} Back to Menu", callback_data=self.kb.encode_callback('main_menu'))
            ])
            
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            await update.message.reply_text(
                "❌ Search failed. Please try again later."
            )
    
    # ==================== Summarize ====================
    
    async def summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate AI summary of tasks."""
        # Redirect to AI handler's summarize feature
        # This command is kept for backward compatibility
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        # We can't easily call AIHandler here without circular dependency or passing it in.
        # For now, let's just reimplement the basic call or redirect user to menu.
        
        await update.message.reply_text(
            "🤖 **AI Summary**\n\n"
            "Please use the AI Assistant menu for summaries.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Go to AI Assistant", callback_data=self.kb.encode_callback('menu_ai'))
            ]]),
            parse_mode='Markdown'
        )

    async def _send_auth_error(self, update: Update):
        """Send authentication error message."""
        msg = "❌ Session expired. Please /start again."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
