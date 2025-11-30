"""
QuikSafe Bot - Task Handler
Handles task management commands.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from src.database.db_manager import DatabaseManager
from src.security.encryption import EncryptionManager
from src.security.auth import SessionManager
from src.utils.validators import validate_task_content, validate_priority, validate_due_date, parse_tags_from_text
from src.utils.formatters import format_task_list
import logging

logger = logging.getLogger(__name__)

# Conversation states
AWAITING_TASK_CONTENT, AWAITING_PRIORITY, AWAITING_DUE_DATE, AWAITING_TASK_TAGS = range(4)


class TaskHandler:
    """Handles task management operations."""
    
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager, session: SessionManager):
        """Initialize task handler."""
        self.db = db
        self.encryption = encryption
        self.session = session
    
    def _check_auth(self, telegram_id: int) -> tuple[bool, str]:
        """Check if user is authenticated."""
        if not self.session.is_authenticated(telegram_id):
            return False, None
        
        session_data = self.session.get_session(telegram_id)
        return True, session_data.get('user_id')
    
    # ==================== Add Task ====================
    
    async def add_task_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start task creation flow."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "✅ **Create New Task**\n\n"
            "Enter the task description:",
            parse_mode='Markdown'
        )
        return AWAITING_TASK_CONTENT
    
    async def receive_task_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive task content."""
        content = update.message.text.strip()
        
        is_valid, error = validate_task_content(content)
        if not is_valid:
            await update.message.reply_text(f"❌ {error}\n\nPlease try again:")
            return AWAITING_TASK_CONTENT
        
        context.user_data['task_content'] = content
        
        await update.message.reply_text(
            "Set priority (low/medium/high) or type 'skip' for default (medium):"
        )
        return AWAITING_PRIORITY
    
    async def receive_priority(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive task priority."""
        priority_text = update.message.text.strip().lower()
        
        if priority_text == 'skip':
            priority = 'medium'
        else:
            is_valid, error = validate_priority(priority_text)
            if not is_valid:
                await update.message.reply_text(f"❌ {error}\n\nPlease try again:")
                return AWAITING_PRIORITY
            priority = priority_text
        
        context.user_data['priority'] = priority
        
        await update.message.reply_text(
            "Set due date (YYYY-MM-DD format) or type 'skip':\n"
            "Example: 2024-12-31"
        )
        return AWAITING_DUE_DATE
    
    async def receive_due_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive due date."""
        date_text = update.message.text.strip()
        
        due_date = None
        if date_text.lower() != 'skip':
            is_valid, error, parsed_date = validate_due_date(date_text)
            if not is_valid:
                await update.message.reply_text(f"❌ {error}\n\nPlease try again:")
                return AWAITING_DUE_DATE
            due_date = parsed_date
        
        context.user_data['due_date'] = due_date
        
        await update.message.reply_text(
            "Add tags (optional)?\n"
            "Use hashtags like: #work #urgent\n"
            "Or type 'skip':"
        )
        return AWAITING_TASK_TAGS
    
    async def receive_task_tags(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive tags and save task."""
        tags_text = update.message.text.strip()
        
        tags = []
        if tags_text.lower() != 'skip':
            tags = parse_tags_from_text(tags_text)
        
        # Get session data
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        # Encrypt task content
        content = context.user_data['task_content']
        encrypted_content = self.encryption.encrypt(content)
        
        priority = context.user_data['priority']
        due_date = context.user_data.get('due_date')
        
        # Save to database
        result = self.db.create_task(
            user_id=user_id,
            encrypted_content=encrypted_content,
            priority=priority,
            due_date=due_date,
            tags=tags
        )
        
        if result:
            due_date_str = f"\nDue: {due_date.strftime('%Y-%m-%d')}" if due_date else ""
            await update.message.reply_text(
                f"✅ Task created successfully!\n\n"
                f"**{content}**\n"
                f"Priority: {priority.capitalize()}{due_date_str}\n"
                f"Tags: {', '.join(tags) if tags else 'None'}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Failed to create task. Please try again.")
        
        context.user_data.clear()
        return ConversationHandler.END
    
    # ==================== List Tasks ====================
    
    async def list_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all tasks."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        # Get filter from args (pending, in_progress, completed)
        status_filter = None
        if context.args:
            status_filter = context.args[0].lower()
        
        tasks = self.db.get_tasks(user_id, status_filter)
        
        # Decrypt task content
        for task in tasks:
            task['encrypted_content'] = self.encryption.decrypt(task['encrypted_content'])
        
        message_text = format_task_list(tasks)
        await update.message.reply_text(message_text, parse_mode='Markdown')
    
    # ==================== Complete Task ====================
    
    async def complete_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mark task as complete."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /completetask <task_id>\n"
                "Use /listtasks to see task IDs"
            )
            return
        
        task_id = context.args[0]
        
        success = self.db.update_task_status(task_id, user_id, 'completed')
        
        if success:
            await update.message.reply_text("✅ Task marked as complete!")
        else:
            await update.message.reply_text("❌ Failed to update task. Check the ID and try again.")
    
    # ==================== Delete Task ====================
    
    async def delete_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete a task."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        if not is_auth:
            await update.message.reply_text("❌ Please /start and authenticate first.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /deletetask <task_id>\n"
                "Use /listtasks to see task IDs"
            )
            return
        
        task_id = context.args[0]
        
        success = self.db.delete_task(task_id, user_id)
        
        if success:
            await update.message.reply_text("✅ Task deleted successfully!")
        else:
            await update.message.reply_text("❌ Failed to delete task. Check the ID and try again.")
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel operation."""
        context.user_data.clear()
        await update.message.reply_text("Operation cancelled.")
        return ConversationHandler.END
    
    def get_add_handler(self) -> ConversationHandler:
        """Get conversation handler for adding tasks."""
        return ConversationHandler(
            entry_points=[CommandHandler('addtask', self.add_task_start)],
            states={
                AWAITING_TASK_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_task_content)],
                AWAITING_PRIORITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_priority)],
                AWAITING_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_due_date)],
                AWAITING_TASK_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_task_tags)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
