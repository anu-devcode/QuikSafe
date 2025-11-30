"""
QuikSafe Bot - Search Handler
Handles AI-powered search and summarization.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from src.database.db_manager import DatabaseManager
from src.security.encryption import EncryptionManager
from src.security.auth import SessionManager
from src.ai.gemini_client import GeminiClient
from src.utils.formatters import format_search_results
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
    
    def _check_auth(self, telegram_id: int) -> tuple[bool, str]:
        """Check if user is authenticated."""
        if not self.session.is_authenticated(telegram_id):
            return False, None
        
        session_data = self.session.get_session(telegram_id)
        return True, session_data.get('user_id')
    
    # ==================== Search ====================
    
    async def search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """AI-powered search across all data."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /search <query>\n"
                "Example: /search work passwords\n"
                "Example: /search urgent tasks"
            )
            return
        
        query = ' '.join(context.args)
        
        await update.message.reply_text("🔍 Searching...")
        
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
            
            # Format results
            message = f"🔍 **Search Results for:** '{query}'\n\n"
            
            if password_results:
                message += format_search_results(password_results, "passwords") + "\n"
            
            if task_results:
                message += format_search_results(task_results, "tasks") + "\n"
            
            if file_results:
                message += format_search_results(file_results, "files") + "\n"
            
            if not password_results and not task_results and not file_results:
                message += "No results found."
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            await update.message.reply_text(
                "❌ Search failed. Please try again or use specific commands like /listpasswords, /listtasks, /listfiles"
            )
    
    # ==================== Summarize ====================
    
    async def summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate AI summary of tasks."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        await update.message.reply_text("🤖 Generating summary...")
        
        # Get tasks
        tasks = self.db.get_tasks(user_id)
        
        if not tasks:
            await update.message.reply_text("You have no tasks to summarize.")
            return
        
        # Decrypt task content
        for task in tasks:
            task['encrypted_content'] = self.encryption.decrypt(task['encrypted_content'])
        
        try:
            summary = self.ai.summarize_tasks(tasks)
            
            await update.message.reply_text(
                f"📊 **Task Summary**\n\n{summary}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            await update.message.reply_text(
                "❌ Failed to generate summary. Please try /listtasks instead."
            )
