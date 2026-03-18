"""
QuikSafe Bot - AI Handler
Handles AI-powered features like auto-organization and summarization.
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.database.db_manager import DatabaseManager
from src.security.encryption import EncryptionManager
from src.security.auth import SessionManager
from src.ai.huggingface_client import HuggingFaceClient
from src.utils.keyboard_builder import KeyboardBuilder
import logging

logger = logging.getLogger(__name__)


class AIHandler:
    """Handles AI operations."""
    
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager, session: SessionManager, ai_client: HuggingFaceClient):
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
    
    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE = None):
        """Show AI menu."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        message = (
            "🤖 **AI Assistant**\n\n"
            "Your intelligence layer for clarity, focus, and momentum.\n\n"
            "Choose an AI workflow:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🏷️ Smart Tag", callback_data=self.kb.encode_callback('ai_tag')),
                InlineKeyboardButton("📝 Task Brief", callback_data=self.kb.encode_callback('ai_summarize_tasks'))
            ],
            [
                InlineKeyboardButton("📌 Priority Queue", callback_data=self.kb.encode_callback('ai_prioritize_tasks')),
                InlineKeyboardButton("📊 Performance Insights", callback_data=self.kb.encode_callback('ai_productivity_insights'))
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
        """Suggest tags for untagged passwords, tasks, and files."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        await update.callback_query.edit_message_text("🤖 AI Studio is analyzing your data for stronger tags...")
        
        # Get untagged items across all categories
        passwords = self.db.get_passwords(user_id)
        tasks = self.db.get_tasks(user_id)
        files = self.db.get_files(user_id)

        for task in tasks:
            task['encrypted_content'] = self.encryption.decrypt(task['encrypted_content'])

        for file_entry in files:
            description = ""
            if file_entry.get('encrypted_description'):
                description = self.encryption.decrypt(file_entry['encrypted_description'])
            file_entry['description'] = description

        untagged_passwords = [p for p in passwords if not p.get('tags')]
        untagged_tasks = [t for t in tasks if not t.get('tags')]
        untagged_files = [f for f in files if not f.get('tags')]
        
        if not untagged_passwords and not untagged_tasks and not untagged_files:
            await update.callback_query.edit_message_text(
                "✅ Your workspace is already fully tagged.",
                reply_markup=self.kb.back_to_menu('menu_ai')
            )
            return
            
        # Process a small batch to avoid long response times
        suggestions = []

        for item in untagged_passwords[:3]:
            service_name = item['service_name']
            suggested = self.ai_client.suggest_tags(service_name, "password")
            suggestions.append(f"• **Password / {service_name}**: {', '.join(suggested)}")

        for item in untagged_tasks[:3]:
            content = item['encrypted_content']
            suggested = self.ai_client.suggest_tags(content, "task")
            suggestions.append(f"• **Task / {content[:30]}**: {', '.join(suggested)}")

        for item in untagged_files[:3]:
            file_context = f"{item.get('file_name', '')} {item.get('description', '')}".strip()
            suggested = self.ai_client.suggest_tags(file_context, "file")
            suggestions.append(f"• **File / {item.get('file_name', 'Unnamed')}**: {', '.join(suggested)}")
            
        msg = (
            "🏷️ **Tag Suggestions**\n\n"
            "Recommended tags for your unclassified items:\n\n" +
            "\n".join(suggestions) +
            "\n\nTap **Apply All** to apply instantly."
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Apply All", callback_data=self.kb.encode_callback('ai_apply_tags'))],
            [InlineKeyboardButton(f"{self.kb.EMOJI['back']} Back to Menu", callback_data=self.kb.encode_callback('menu_ai'))]
        ]
        
        await update.callback_query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def handle_apply_tags(self, update: Update):
        """Apply suggested tags to untagged passwords, tasks, and files."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        await update.callback_query.edit_message_text("🤖 Applying smart tags across your workspace...")
        
        # Get untagged items
        passwords = self.db.get_passwords(user_id)
        tasks = self.db.get_tasks(user_id)
        files = self.db.get_files(user_id)

        for task in tasks:
            task['encrypted_content'] = self.encryption.decrypt(task['encrypted_content'])

        for file_entry in files:
            description = ""
            if file_entry.get('encrypted_description'):
                description = self.encryption.decrypt(file_entry['encrypted_description'])
            file_entry['description'] = description

        untagged_passwords = [p for p in passwords if not p.get('tags')]
        untagged_tasks = [t for t in tasks if not t.get('tags')]
        untagged_files = [f for f in files if not f.get('tags')]
        
        if not untagged_passwords and not untagged_tasks and not untagged_files:
            await update.callback_query.edit_message_text(
                "✅ No untagged items found.",
                reply_markup=self.kb.back_to_menu('menu_ai')
            )
            return
            
        count_passwords = 0
        count_tasks = 0
        count_files = 0

        for item in untagged_passwords[:5]:
            service_name = item['service_name']
            suggested = self.ai_client.suggest_tags(service_name, "password")
            
            if suggested:
                if self.db.update_password_tags(item['id'], suggested):
                    count_passwords += 1

        for item in untagged_tasks[:5]:
            content = item['encrypted_content']
            suggested = self.ai_client.suggest_tags(content, "task")
            if suggested and self.db.update_task_tags(item['id'], suggested):
                count_tasks += 1

        for item in untagged_files[:5]:
            file_context = f"{item.get('file_name', '')} {item.get('description', '')}".strip()
            suggested = self.ai_client.suggest_tags(file_context, "file")
            if suggested and self.db.update_file_tags(item['id'], suggested):
                count_files += 1

        total = count_passwords + count_tasks + count_files
        
        await update.callback_query.edit_message_text(
            f"✅ Smart tagging complete: {total} item(s) updated.\n"
            f"• Passwords: {count_passwords}\n"
            f"• Tasks: {count_tasks}\n"
            f"• Files: {count_files}\n\n"
            "Your workspace is now cleaner and faster to search.",
            reply_markup=self.kb.back_to_menu('menu_ai')
        )

    async def handle_summarize_tasks(self, update: Update):
        """Summarize tasks."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        await update.callback_query.edit_message_text("🤖 Preparing your task brief...")
        
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

    async def handle_prioritize_tasks(self, update: Update):
        """Show AI-prioritized task queue."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)

        if not is_auth:
            await self._send_auth_error(update)
            return

        await update.callback_query.edit_message_text("🤖 Building your priority queue...")

        tasks = self.db.get_tasks(user_id)
        for task in tasks:
            task['encrypted_content'] = self.encryption.decrypt(task['encrypted_content'])

        prioritized = self.ai_client.prioritize_tasks(tasks)

        if not prioritized:
            await update.callback_query.edit_message_text(
                "✅ No tasks available for prioritization.",
                reply_markup=self.kb.back_to_menu('menu_ai')
            )
            return

        lines = ["📌 **Prioritized Tasks**\n"]
        for idx, task in enumerate(prioritized[:7], 1):
            lines.append(
                f"{idx}. **{task['content'][:45]}**\n"
                f"   Score: {task['score']} | {task['reason']}"
            )

        await update.callback_query.edit_message_text(
            "\n".join(lines),
            reply_markup=self.kb.back_to_menu('menu_ai'),
            parse_mode='Markdown'
        )

    async def handle_productivity_insights(self, update: Update):
        """Show AI-generated productivity insights across bot data."""
        user = update.effective_user
        is_auth, user_id = self._check_auth(user.id)

        if not is_auth:
            await self._send_auth_error(update)
            return

        await update.callback_query.edit_message_text("🤖 Generating productivity insights...")

        tasks = self.db.get_tasks(user_id)
        passwords = self.db.get_passwords(user_id)
        files = self.db.get_files(user_id)

        for task in tasks:
            task['encrypted_content'] = self.encryption.decrypt(task['encrypted_content'])

        insights = self.ai_client.generate_productivity_insights(tasks, passwords, files)

        await update.callback_query.edit_message_text(
            f"📊 **Productivity Insights**\n\n{insights}",
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
