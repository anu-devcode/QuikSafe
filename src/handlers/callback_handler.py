"""
QuikSafe Bot - Callback Query Handler
Central router for handling inline keyboard callbacks.
"""

from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from src.utils.keyboard_builder import KeyboardBuilder
import logging

logger = logging.getLogger(__name__)


class CallbackHandler:
    """Central handler for all callback queries from inline keyboards."""
    
    def __init__(self, db, encryption, session, ai_client, password_handler=None, task_handler=None, file_handler=None, ai_handler=None, search_handler=None, settings_handler=None, scene_manager=None):
        """
        Initialize callback handler.
        
        Args:
            db: Database manager instance
            encryption: Encryption manager instance
            session: Session manager instance
            ai_client: AI client instance
            password_handler: Password handler instance
            task_handler: Task handler instance
            file_handler: File handler instance
            ai_handler: AI handler instance
            search_handler: Search handler instance
            settings_handler: Settings handler instance
        """
        self.db = db
        self.encryption = encryption
        self.session = session
        self.ai_client = ai_client
        self.kb = KeyboardBuilder()
        
        self.password_handler = password_handler
        self.task_handler = task_handler
        self.file_handler = file_handler
        self.ai_handler = ai_handler
        self.search_handler = search_handler
        self.settings_handler = settings_handler
        self.scene_manager = scene_manager
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Main callback query handler that routes to specific handlers.
        
        Args:
            update: Telegram update
            context: Callback context
        """
        query = update.callback_query
        await query.answer()  # Acknowledge the callback
        
        # Decode callback data
        data = self.kb.decode_callback(query.data)
        action = data.get('a', '')
        
        # Check authentication for protected actions
        if not action.startswith('main_menu') and action != 'noop':
            if not self._check_auth(update.effective_user.id):
                await query.edit_message_text(
                    "❌ Session expired. Please /start again to authenticate."
                )
                return
        
        # Route to appropriate handler
        try:
            if action == 'noop':
                # No operation (e.g., page indicator button)
                return
            
            # Main menu actions
            elif action == 'main_menu':
                await self._show_main_menu(update, context)
            
            # Category menus
            elif action == 'menu_passwords':
                await self._show_password_menu(update, context)
            elif action == 'menu_tasks':
                await self._show_task_menu(update, context)
            elif action == 'menu_files':
                await self._show_file_menu(update, context)
            elif action == 'menu_search':
                await self._show_search_menu(update, context)
            elif action == 'menu_ai':
                await self._show_ai_menu(update, context)
            elif action == 'menu_settings':
                await self._show_settings_menu(update, context)
            
            # Quick actions
            elif action == 'quick_save_password':
                await self._quick_save_password(update, context)
            elif action == 'quick_add_task':
                await self._quick_add_task(update, context)
            elif action == 'quick_upload_file':
                await self._quick_upload_file(update, context)
            elif action == 'quick_search':
                await self._quick_search(update, context)
            
            # Password actions
            elif action.startswith('password_'):
                await self._handle_password_action(update, context, action, data)
            
            # Task actions
            elif action.startswith('task_'):
                await self._handle_task_action(update, context, action, data)
            
            # File actions
            elif action.startswith('file_'):
                await self._handle_file_action(update, context, action, data)
            
            # AI actions
            elif action.startswith('ai_'):
                await self._handle_ai_action(update, context, action, data)
            
            # Settings actions
            elif action.startswith('settings_'):
                await self._handle_settings_action(update, context, action, data)
            
            # Wizard actions (skip buttons, priority selection, etc.)
            elif action == 'wizard_skip' or action.startswith('set_') or action == 'select_priority':
                await self._handle_wizard_action(update, context, action, data)
            
            # Generic actions
            elif action == 'cancel':
                await self._handle_cancel(update, context)
            
            else:
                logger.warning(f"Unknown callback action: {action}")
                await query.edit_message_text(
                    f"⚠️ Unknown action. Please try again or /start to return to main menu."
                )
        
        except BadRequest as e:
            # Handle the case where message content is identical (user clicked same button twice)
            if "message is not modified" in str(e).lower():
                logger.debug(f"Message not modified for action '{action}' - content is identical")
                # Just answer the callback query without editing the message
                return
            else:
                # Other BadRequest errors should still be logged
                user_id = update.effective_user.id if update.effective_user else 'unknown'
                logger.error(f"BadRequest handling callback '{action}' for user {user_id}: {e}", exc_info=True)
                logger.error(f"Callback data: {data}")
                try:
                    await query.edit_message_text(
                        "❌ An error occurred. Please try again or /start to return to main menu."
                    )
                except BadRequest:
                    # If we can't edit the message, just log it
                    logger.debug("Could not edit message to show error")
        
        except Exception as e:
            user_id = update.effective_user.id if update.effective_user else 'unknown'
            logger.error(f"Error handling callback '{action}' for user {user_id}: {e}", exc_info=True)
            logger.error(f"Callback data: {data}")
            try:
                await query.edit_message_text(
                    "❌ An error occurred. Please try again or /start to return to main menu."
                )
            except BadRequest:
                # If we can't edit the message, just log it
                logger.debug("Could not edit message to show error")
    
    def _check_auth(self, telegram_id: int) -> bool:
        """Check if user is authenticated."""
        return self.session.is_authenticated(telegram_id)
    
    def _get_user_id(self, telegram_id: int) -> str:
        """Get user ID from session."""
        session_data = self.session.get_session(telegram_id)
        return session_data.get('user_id') if session_data else None
    
    # ==================== Menu Handlers ====================
    
    async def _show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu."""
        query = update.callback_query
        user_name = query.from_user.first_name
        
        message = (
            f"👋 **Welcome back, {user_name}!**\n\n"
            "What would you like to do today?\n\n"
            "Choose a category below:"
        )
        
        await query.edit_message_text(
            message,
            reply_markup=self.kb.main_menu(),
            parse_mode='Markdown'
        )
    
    async def _show_password_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show password management menu."""
        query = update.callback_query
        message = (
            "🔐 **Password Management**\n\n"
            "Securely manage your passwords with AES-256 encryption.\n\n"
            "What would you like to do?"
        )
        
        await query.edit_message_text(
            message,
            reply_markup=self.kb.password_menu(),
            parse_mode='Markdown'
        )
    
    async def _show_task_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show task management menu."""
        query = update.callback_query
        message = (
            "✅ **Task Management**\n\n"
            "Organize and track your tasks efficiently.\n\n"
            "Choose an option:"
        )
        
        await query.edit_message_text(
            message,
            reply_markup=self.kb.task_menu(),
            parse_mode='Markdown'
        )
    
    async def _show_file_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show file management menu."""
        query = update.callback_query
        message = (
            "📁 **File Management**\n\n"
            "Store and organize your files securely.\n\n"
            "Browse by category or view all:"
        )
        
        await query.edit_message_text(
            message,
            reply_markup=self.kb.file_menu(),
            parse_mode='Markdown'
        )
    
    async def _show_search_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show search menu."""
        query = update.callback_query
        message = (
            "🔍 **Smart Search**\n\n"
            "Search across all your passwords, tasks, and files.\n\n"
            "Type your search query or use /search <query>"
        )
        
        await query.edit_message_text(
            message,
            reply_markup=self.kb.back_to_menu('main'),
            parse_mode='Markdown'
        )
    
    async def _show_ai_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show AI assistant menu."""
        if self.ai_handler:
            await self.ai_handler.show_menu(update)
        else:
            await query.edit_message_text("❌ AI handler not initialized.")
    
    async def _show_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings menu."""
        if self.settings_handler:
            await self.settings_handler.show_menu(update)
        else:
            await update.callback_query.edit_message_text("❌ Settings handler not initialized.")
    
    # ==================== Quick Actions ====================
    
    async def _quick_save_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Quick action: Save password."""
        if self.password_handler:
            await self.password_handler.start_save_wizard(update)
        else:
            await update.callback_query.edit_message_text("❌ Handler not initialized.")
    
    async def _quick_add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Quick action: Add task."""
        if self.task_handler:
            await self.task_handler.start_add_wizard(update)
        else:
            await update.callback_query.edit_message_text("❌ Handler not initialized.")
    
    async def _quick_upload_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Quick action: Upload file."""
        await update.callback_query.edit_message_text(
            "📁 **Upload File**\n\n"
            "Simply send any file, photo, or video to this chat.\n"
            "I'll save it securely for you!"
        )
    
    async def _quick_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Quick action: Search."""
        await update.callback_query.edit_message_text(
            "🔍 **Smart Search**\n\n"
            "Search across all your data.\n\n"
            "Use: /search <your query>\n"
            "Example: /search work passwords"
        )
    
    # ==================== Action Handlers ====================
    
    async def _handle_password_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                      action: str, data: dict):
        """Handle password-related actions."""
        if not self.password_handler:
            await update.callback_query.edit_message_text("❌ Password handler not initialized.")
            return

        if action == 'password_save_start':
            await self.password_handler.start_save_wizard(update)
            
        elif action == 'password_list':
            page = data.get('page', 0)
            await self.password_handler.show_password_list(update, page)
            
        elif action == 'password_view':
            pid = data.get('password_id')
            await self.password_handler.show_password_details(update, pid)
            
        elif action == 'password_delete':
            pid = data.get('password_id')
            # Ask for confirmation first? For now direct delete as per handler
            await self.password_handler.delete_password(update, pid)
            
        elif action == 'password_search':
            # TODO: Implement search
            await update.callback_query.edit_message_text("Search coming soon!")
            
        else:
            await update.callback_query.edit_message_text(f"Unknown password action: {action}")
    
    async def _handle_task_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  action: str, data: dict):
        """Handle task-related actions."""
        if not self.task_handler:
            await update.callback_query.edit_message_text("❌ Task handler not initialized.")
            return

        if action == 'task_add_start':
            await self.task_handler.start_add_wizard(update)
            
        elif action == 'task_list':
            page = data.get('page', 0)
            status_filter = data.get('filter')
            await self.task_handler.show_task_list(update, page, status_filter)
            
        elif action == 'task_view':
            tid = data.get('task_id')
            await self.task_handler.show_task_details(update, tid)
            
        elif action == 'task_toggle':
            tid = data.get('task_id')
            await self.task_handler.toggle_task_status(update, tid)
            
        elif action == 'task_delete':
            tid = data.get('task_id')
            await self.task_handler.delete_task(update, tid)
            
        elif action == 'set_priority':
            # This is part of the wizard flow, handled by handle_wizard_callback
            await self.task_handler.handle_wizard_callback(update, action, data)
            
        else:
            await update.callback_query.edit_message_text(f"Unknown task action: {action}")
    
    async def _handle_file_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  action: str, data: dict):
        """Handle file-related actions."""
        if not self.file_handler:
            await update.callback_query.edit_message_text("❌ File handler not initialized.")
            return

        if action == 'file_list':
            page = data.get('page', 0)
            type_filter = data.get('filter')
            await self.file_handler.show_file_list(update, page, type_filter)
            
        elif action == 'file_upload_start':
            await self._quick_upload_file(update, context)
            
        elif action == 'file_view':
            fid = data.get('file_id')
            await self.file_handler.show_file_details(update, fid)
            
        elif action == 'file_download':
            fid = data.get('file_id')
            await self.file_handler.download_file(update, fid)
            
        elif action == 'file_delete':
            fid = data.get('file_id')
            await self.file_handler.delete_file(update, fid)
            
        else:
            await update.callback_query.edit_message_text(f"Unknown file action: {action}")
    
    async def _handle_ai_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                action: str, data: dict):
        """Handle AI-related actions."""
        if not self.ai_handler:
            return

        if action == 'ai_tag':
            await self.ai_handler.handle_auto_tag(update)
            
        elif action == 'ai_summarize_tasks':
            await self.ai_handler.handle_summarize_tasks(update)
            
        else:
            await update.callback_query.edit_message_text(f"Unknown AI action: {action}")

    async def _handle_settings_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                      action: str, data: dict):
        """Handle settings-related actions."""
        if not self.settings_handler:
            await update.callback_query.edit_message_text("❌ Settings handler not initialized.")
            return

        if action == 'settings_logout':
            await self.settings_handler.handle_logout(update)
            
        elif action == 'settings_security':
            await self.settings_handler.show_security_menu(update)
            
        elif action == 'settings_notifications':
            await self.settings_handler.show_notifications_menu(update)
            
        elif action in ['settings_autolock', 'settings_changepass', 'settings_toggle_reminders', 'settings_toggle_summary']:
            await update.callback_query.answer("Coming soon in next update!", show_alert=True)
            
        else:
            await update.callback_query.edit_message_text(f"Unknown settings action: {action}")

    async def _handle_wizard_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                    action: str, data: dict):
        """Handle wizard-related actions like skip buttons."""
        user = update.effective_user
        
        # Check which wizard is active
        if self.password_handler and self.password_handler.scene_manager.has_active_scene(user.id):
            scene = self.password_handler.scene_manager.get_scene(user.id)
            if scene.scene_id in ['save_password', 'edit_password']:
                if action == 'wizard_skip':
                    await self.password_handler.handle_wizard_skip(update)
                    return
        
        if self.task_handler and self.task_handler.scene_manager.has_active_scene(user.id):
            scene = self.task_handler.scene_manager.get_scene(user.id)
            if scene.scene_id == 'add_task':
                # Handle priority selection from buttons
                if action == 'select_priority':
                    # Convert the action to what task_handler expects
                    # The keyboard uses 'pr' but task_handler expects 'level'
                    modified_data = data.copy()
                    if 'pr' in modified_data:
                        modified_data['level'] = modified_data.pop('pr')
                    await self.task_handler.handle_wizard_callback(update, 'set_priority', modified_data)
                    return
                elif action == 'wizard_skip':
                    await self.task_handler.handle_wizard_callback(update, action, data)
                    return
                elif action.startswith('set_'):
                    await self.task_handler.handle_wizard_callback(update, action, data)
                    return
        
        # No active wizard
        await update.callback_query.answer("No active wizard found", show_alert=True)

    async def _handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle cancel action."""
        # Clear any active scene
        if self.scene_manager:
            self.scene_manager.cancel_scene(update.effective_user.id)
            
        await update.callback_query.edit_message_text(
            "❌ Operation cancelled.\n\n"
            "Use /start to return to the main menu."
        )
