"""
QuikSafe Bot - Task Handler
Handles task management with modern inline UI and wizards.
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from src.database.db_manager import DatabaseManager
from src.security.encryption import EncryptionManager
from src.security.auth import SessionManager
from src.utils.validators import validate_task_content, validate_priority, validate_due_date, parse_tags_from_text
from src.utils.formatters import format_task_list, format_task_details
from src.utils.keyboard_builder import KeyboardBuilder
from src.utils.scene_manager import SceneManager
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

# Legacy conversation states
AWAITING_TASK_CONTENT, AWAITING_PRIORITY, AWAITING_DUE_DATE, AWAITING_TASK_TAGS = range(4)


class TaskHandler:
    """Handles task management operations."""
    
    def __init__(self, db: DatabaseManager, encryption: EncryptionManager, session: SessionManager, scene_manager: SceneManager):
        """
        Initialize task handler.
        
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
    
    async def show_task_list(self, update: Update, page: int = 0, status_filter: str = None):
        """Show paginated list of tasks."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
        
        # Get tasks
        tasks = self.db.get_tasks(user_id, status_filter)
        
        # Decrypt content for display
        for task in tasks:
            task['content'] = self.encryption.decrypt(task['encrypted_content'])
        
        # Pagination logic
        items_per_page = 5
        total_pages = (len(tasks) + items_per_page - 1) // items_per_page
        
        if page >= total_pages and total_pages > 0:
            page = total_pages - 1
        
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_page_items = tasks[start_idx:end_idx]
        
        # Build message
        filter_text = f" ({status_filter})" if status_filter else ""
        if not tasks:
            message = f"✅ **No tasks found{filter_text}.**\n\nUse 'Add New Task' to create one!"
        else:
            message = f"✅ **Your Tasks**{filter_text} ({len(tasks)} total)\n\n"
            for i, task in enumerate(current_page_items, 1):
                status_icon = "✅" if task['status'] == 'completed' else "⬜"
                priority_icon = "🔴" if task['priority'] == 'high' else "🟡" if task['priority'] == 'medium' else "🟢"
                message += f"{i}. {status_icon} {priority_icon} **{task['content']}**\n"
        
        # Build keyboard
        keyboard = []
        
        # Item buttons
        for task in current_page_items:
            keyboard.append([
                InlineKeyboardButton(
                    f"👁️ {task['content'][:20]}...",
                    callback_data=self.kb.encode_callback('task_view', tid=task['id'])
                )
            ])
        
        # Pagination buttons
        if total_pages > 1:
            pagination = self.kb.pagination(page, total_pages, 'task_list')
            keyboard.append(pagination)
        
        # Filter buttons
        keyboard.append([
            InlineKeyboardButton("All", callback_data=self.kb.encode_callback('task_list', p=0)),
            InlineKeyboardButton("Pending", callback_data=self.kb.encode_callback('task_list', p=0, f='pending')),
            InlineKeyboardButton("Completed", callback_data=self.kb.encode_callback('task_list', p=0, f='completed'))
        ])
        
        # Action buttons
        keyboard.append([
            InlineKeyboardButton(
                f"{self.kb.EMOJI['add']} Add New",
                callback_data=self.kb.encode_callback('task_add_start')
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

    async def show_task_details(self, update: Update, task_id: str):
        """Show details for a specific task."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
        
        # Get task details (inefficient fetch all again, TODO: optimize)
        tasks = self.db.get_tasks(user_id)
        task = next((t for t in tasks if str(t['id']) == str(task_id)), None)
        
        if not task:
            await self._send_error(update, "Task not found.")
            return
        
        # Decrypt
        task['content'] = self.encryption.decrypt(task['encrypted_content'])
        
        message = format_task_details(task)
        
        # Action buttons
        reply_markup = self.kb.task_actions(task_id, task['status'])
        
        # Handle both Update and CallbackQuery objects
        if hasattr(update, 'edit_message_text'):
            await update.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    async def start_add_wizard(self, update: Update):
        """Start the add task wizard."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        if not is_auth:
            await self._send_auth_error(update)
            return
            
        self.scene_manager.start_scene(user.id, 'add_task')
        
        message = (
            "✅ **Add New Task**\n\n"
            "Step 1/4: **Task Description**\n"
            "What needs to be done?"
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
        if scene.scene_id != 'add_task':
            return False
            
        current_step = scene.get_current_step()
        text = update.message.text.strip()
        
        # Delete user message
        try:
            await update.message.delete()
        except:
            pass
            
        if current_step == 'content':
            is_valid, error = validate_task_content(text)
            if not is_valid:
                await update.message.reply_text(f"❌ {error}\nPlease try again:")
                return True
                
            self.scene_manager.set_scene_data(user.id, 'content', text)
            self.scene_manager.advance_scene(user.id)
            
            await update.message.reply_text(
                f"✅ Task: **{text}**\n\n"
                "Step 2/4: **Priority**\n"
                "Select priority:",
                parse_mode='Markdown',
                reply_markup=self.kb.priority_selector()
            )
            
        elif current_step == 'priority':
            # Priority is usually handled by buttons, but handle text too
            is_valid, error = validate_priority(text)
            if not is_valid:
                await update.message.reply_text(f"❌ {error}\nPlease try again or use buttons:")
                return True
                
            self.scene_manager.set_scene_data(user.id, 'priority', text.lower())
            self.scene_manager.advance_scene(user.id)
            
            await update.message.reply_text(
                "Step 3/4: **Due Date**\n"
                "Enter date (YYYY-MM-DD) or skip:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Skip", callback_data=self.kb.encode_callback('wizard_skip'))
                ]])
            )
            
        elif current_step == 'due_date':
            due_date = None
            if text.lower() != 'skip':
                is_valid, error, parsed_date = validate_due_date(text)
                if not is_valid:
                    await update.message.reply_text(f"❌ {error}\nPlease try again:")
                    return True
                due_date = parsed_date
            
            self.scene_manager.set_scene_data(user.id, 'due_date', due_date)
            self.scene_manager.advance_scene(user.id)
            
            await update.message.reply_text(
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
            await self._save_task_data(update, data)
            
        return True

    async def handle_wizard_callback(self, update: Update, action: str, data: dict):
        """Handle callback inputs for wizard (e.g. priority buttons)."""
        user = update.effective_user
        scene = self.scene_manager.get_scene(user.id)
        if not scene or scene.scene_id != 'add_task':
            return

        current_step = scene.get_current_step()
        
        if current_step == 'priority' and action == 'set_priority':
            priority = data.get('level', 'medium')
            self.scene_manager.set_scene_data(user.id, 'priority', priority)
            self.scene_manager.advance_scene(user.id)
            
            await update.callback_query.edit_message_text(
                f"Priority: {priority.capitalize()}\n\n"
                "Step 3/4: **Due Date**\n"
                "Enter date (YYYY-MM-DD) or skip:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Skip", callback_data=self.kb.encode_callback('wizard_skip'))
                ]])
            )
            
        elif action == 'wizard_skip':
            if current_step == 'due_date':
                self.scene_manager.set_scene_data(user.id, 'due_date', None)
                self.scene_manager.advance_scene(user.id)
                await update.callback_query.edit_message_text(
                    "Step 4/4: **Tags**\n"
                    "Enter tags (e.g. #work) or skip:",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Skip", callback_data=self.kb.encode_callback('wizard_skip'))
                    ]])
                )
            elif current_step == 'tags':
                self.scene_manager.set_scene_data(user.id, 'tags', [])
                data = self.scene_manager.complete_scene(user.id)
                await self._save_task_data(update, data)

    async def _save_task_data(self, update: Update, data: dict):
        """Internal method to save task to DB."""
        is_auth, user_id = self._check_auth(update.effective_user.id)
        
        content = data['content']
        priority = data.get('priority', 'medium')
        due_date = data.get('due_date')
        tags = data.get('tags', [])
        
        encrypted_content = self.encryption.encrypt(content)
        
        result = self.db.create_task(
            user_id=user_id,
            encrypted_content=encrypted_content,
            priority=priority,
            due_date=due_date,
            tags=tags
        )
        
        msg = (
            f"✅ **Task Created!**\n\n"
            f"**{content}**\n"
            f"Priority: {priority.capitalize()}\n"
            f"Tags: {', '.join(tags) if tags else 'None'}"
        )
        
        keyboard = [[
            InlineKeyboardButton(
                f"{self.kb.EMOJI['view']} View List",
                callback_data=self.kb.encode_callback('task_list', p=0)
            ),
            InlineKeyboardButton(
                f"{self.kb.EMOJI['add']} Add Another",
                callback_data=self.kb.encode_callback('task_add_start')
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

    async def toggle_task_status(self, update: Update, task_id: str):
        """Toggle task status (pending/completed)."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        # Get current status
        tasks = self.db.get_tasks(user_id)
        task = next((t for t in tasks if str(t['id']) == str(task_id)), None)
        
        if not task:
            await update.callback_query.answer("Task not found")
            return
            
        new_status = 'completed' if task['status'] == 'pending' else 'pending'
        
        if self.db.update_task_status(task_id, user_id, new_status):
            await update.callback_query.answer(f"Marked as {new_status}")
            await self.show_task_details(update, task_id)
        else:
            await update.callback_query.answer("Failed to update", show_alert=True)

    async def delete_task(self, update: Update, task_id: str):
        """Delete a task."""
        user = getattr(update, 'effective_user', None) or getattr(update, 'from_user', None)
        is_auth, user_id = self._check_auth(user.id)
        
        if self.db.delete_task(task_id, user_id):
            await update.callback_query.answer("Task deleted")
            await self.show_task_list(update, 0)
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
    
    async def add_task_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Legacy start task flow."""
        await self.start_add_wizard(update)
        return ConversationHandler.END

    async def list_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Legacy list tasks."""
        await self.show_task_list(update)

    async def complete_task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Legacy complete task."""
        await update.message.reply_text("Please use the 'View' button in the task list to complete tasks.")
        await self.show_task_list(update)

    async def delete_task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Legacy delete task."""
        await update.message.reply_text("Please use the 'Delete' button in the task list.")
        await self.show_task_list(update)

    def get_add_handler(self) -> ConversationHandler:
        """Get conversation handler."""
        return ConversationHandler(
            entry_points=[CommandHandler('addtask', self.add_task_start)],
            states={
                AWAITING_TASK_CONTENT: [MessageHandler(filters.TEXT, self.add_task_start)],
            },
            fallbacks=[CommandHandler('cancel', self.add_task_start)]
        )
