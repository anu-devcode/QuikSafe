"""
QuikSafe Bot - Inline Keyboard Builder
Utility for creating consistent, beautiful inline keyboards.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any, Optional, Tuple
import json


class KeyboardBuilder:
    """Builder for creating inline keyboards with consistent styling."""
    
    # Emoji constants for consistent usage
    EMOJI = {
        # Main categories
        'password': '🔐',
        'task': '✅',
        'file': '📁',
        'search': '🔍',
        'settings': '⚙️',
        'ai': '🤖',
        
        # Actions
        'add': '➕',
        'edit': '✏️',
        'delete': '🗑️',
        'view': '👁️',
        'copy': '📋',
        'download': '⬇️',
        'upload': '⬆️',
        'share': '📤',
        
        # Navigation
        'back': '◀️',
        'next': '▶️',
        'home': '🏠',
        'cancel': '❌',
        'confirm': '✔️',
        
        # Status
        'pending': '⏳',
        'in_progress': '🔄',
        'completed': '✔️',
        'priority_low': '🔵',
        'priority_medium': '🟡',
        'priority_high': '🔴',
        
        # Filters
        'filter': '🔽',
        'sort': '🔃',
        'calendar': '📅',
        'tag': '🏷️',
    }
    
    @staticmethod
    def encode_callback(action: str, **kwargs) -> str:
        """
        Encode callback data as JSON string.
        
        Args:
            action: Action identifier
            **kwargs: Additional data
            
        Returns:
            Encoded callback data (max 64 bytes)
        """
        # Action abbreviations to save space
        action_map = {
            'password_view': 'pv',
            'password_list': 'pl',
            'password_delete': 'pd',
            'password_edit': 'pe',
            'password_copy': 'pc',
            'password_save_start': 'pss',
            'password_search': 'ps',
            
            'task_view': 'tv',
            'task_list': 'tl',
            'task_delete': 'td',
            'task_edit': 'te',
            'task_status': 'ts',
            'task_add_start': 'tas',
            
            'file_view': 'fv',
            'file_list': 'fl',
            'file_delete': 'fd',
            'file_edit': 'fe',
            'file_download': 'fdown',
            'file_share': 'fs',
            'file_upload_start': 'fus',
        }
        
        # Use abbreviation if available
        short_action = action_map.get(action, action)
        
        data = {'a': short_action, **kwargs}
        encoded = json.dumps(data, separators=(',', ':'))
        
        # Telegram callback data limit is 64 bytes
        if len(encoded.encode('utf-8')) > 64:
            # Use abbreviations for common keys
            abbrev_map = {
                'password_id': 'pid',
                'task_id': 'tid',
                'file_id': 'fid',
                'page': 'p',
                'filter': 'f',
                'status': 's',
                'priority': 'pr',
            }
            for old, new in abbrev_map.items():
                if old in data:
                    data[new] = data.pop(old)
            
            # Also check if keys are ALREADY abbreviated (e.g. passed as 'pid')
            # This ensures we don't double-abbreviate or miss them
            # No action needed as they are already short, but good to note.
            
            encoded = json.dumps(data, separators=(',', ':'))
        
        return encoded[:64]  # Ensure limit
    
    @staticmethod
    def decode_callback(callback_data: str) -> Dict[str, Any]:
        """
        Decode callback data from JSON string.
        
        Args:
            callback_data: Encoded callback data
            
        Returns:
            Decoded data dictionary
        """
        try:
            data = json.loads(callback_data)
            
            # Expand action abbreviations
            action_map_rev = {
                'pv': 'password_view',
                'pl': 'password_list',
                'pd': 'password_delete',
                'pe': 'password_edit',
                'pc': 'password_copy',
                'pss': 'password_save_start',
                'ps': 'password_search',
                
                'tv': 'task_view',
                'tl': 'task_list',
                'td': 'task_delete',
                'te': 'task_edit',
                'ts': 'task_status',
                'tas': 'task_add_start',
                
                'fv': 'file_view',
                'fl': 'file_list',
                'fd': 'file_delete',
                'fe': 'file_edit',
                'fdown': 'file_download',
                'fs': 'file_share',
                'fus': 'file_upload_start',
            }
            
            if 'a' in data and data['a'] in action_map_rev:
                data['a'] = action_map_rev[data['a']]
            
            # Expand key abbreviations
            abbrev_map = {
                'pid': 'password_id',
                'tid': 'task_id',
                'fid': 'file_id',
                'p': 'page',
                'f': 'filter',
                's': 'status',
                'pr': 'priority',
            }
            for abbrev, full in abbrev_map.items():
                if abbrev in data:
                    data[full] = data.pop(abbrev)
            return data
        except json.JSONDecodeError:
            return {'a': 'error'}
    
    @classmethod
    def main_menu(cls) -> InlineKeyboardMarkup:
        """Create main menu keyboard."""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['password']} Passwords",
                    callback_data=cls.encode_callback('menu_passwords')
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJI['task']} Tasks",
                    callback_data=cls.encode_callback('menu_tasks')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['file']} Files",
                    callback_data=cls.encode_callback('menu_files')
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJI['search']} Search",
                    callback_data=cls.encode_callback('menu_search')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['ai']} AI Assistant",
                    callback_data=cls.encode_callback('menu_ai')
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJI['settings']} Settings",
                    callback_data=cls.encode_callback('menu_settings')
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def quick_actions(cls) -> InlineKeyboardMarkup:
        """Create quick actions keyboard."""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['add']} Save Password",
                    callback_data=cls.encode_callback('quick_save_password')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['add']} Add Task",
                    callback_data=cls.encode_callback('quick_add_task')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['upload']} Upload File",
                    callback_data=cls.encode_callback('quick_upload_file')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['search']} Smart Search",
                    callback_data=cls.encode_callback('quick_search')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['home']} Main Menu",
                    callback_data=cls.encode_callback('main_menu')
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def password_menu(cls) -> InlineKeyboardMarkup:
        """Create password management menu."""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['add']} Save New Password",
                    callback_data=cls.encode_callback('password_save_start')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['view']} View All Passwords",
                    callback_data=cls.encode_callback('password_list', p=0)
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['search']} Search Passwords",
                    callback_data=cls.encode_callback('password_search')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['back']} Back to Main Menu",
                    callback_data=cls.encode_callback('main_menu')
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def task_menu(cls) -> InlineKeyboardMarkup:
        """Create task management menu."""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['add']} Add New Task",
                    callback_data=cls.encode_callback('task_add_start')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['pending']} Pending",
                    callback_data=cls.encode_callback('task_list', s='pending')
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJI['in_progress']} In Progress",
                    callback_data=cls.encode_callback('task_list', s='in_progress')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['completed']} Completed",
                    callback_data=cls.encode_callback('task_list', s='completed')
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJI['view']} All Tasks",
                    callback_data=cls.encode_callback('task_list', s='all')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['back']} Back to Main Menu",
                    callback_data=cls.encode_callback('main_menu')
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def file_menu(cls) -> InlineKeyboardMarkup:
        """Create file management menu."""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['upload']} Upload File",
                    callback_data=cls.encode_callback('file_upload_start')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['view']} Browse All Files",
                    callback_data=cls.encode_callback('file_list', p=0)
                ),
            ],
            [
                InlineKeyboardButton(
                    f"🖼️ Images",
                    callback_data=cls.encode_callback('file_list', f='image')
                ),
                InlineKeyboardButton(
                    f"📄 Documents",
                    callback_data=cls.encode_callback('file_list', f='document')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"🎥 Videos",
                    callback_data=cls.encode_callback('file_list', f='video')
                ),
                InlineKeyboardButton(
                    f"🎵 Audio",
                    callback_data=cls.encode_callback('file_list', f='audio')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['back']} Back to Main Menu",
                    callback_data=cls.encode_callback('main_menu')
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def password_actions(cls, password_id: str) -> InlineKeyboardMarkup:
        """Create action buttons for a password entry."""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['view']} View",
                    callback_data=cls.encode_callback('password_view', pid=password_id)
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJI['copy']} Copy",
                    callback_data=cls.encode_callback('password_copy', pid=password_id)
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['edit']} Edit",
                    callback_data=cls.encode_callback('password_edit', pid=password_id)
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJI['delete']} Delete",
                    callback_data=cls.encode_callback('password_delete', pid=password_id)
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['back']} Back to List",
                    callback_data=cls.encode_callback('password_list', p=0)
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def task_actions(cls, task_id: str, current_status: str) -> InlineKeyboardMarkup:
        """Create action buttons for a task entry."""
        keyboard = []
        
        # Status change buttons
        status_row = []
        if current_status != 'in_progress':
            status_row.append(InlineKeyboardButton(
                f"{cls.EMOJI['in_progress']} Start",
                callback_data=cls.encode_callback('task_status', tid=task_id, s='in_progress')
            ))
        if current_status != 'completed':
            status_row.append(InlineKeyboardButton(
                f"{cls.EMOJI['completed']} Complete",
                callback_data=cls.encode_callback('task_status', tid=task_id, s='completed')
            ))
        if status_row:
            keyboard.append(status_row)
        
        # Edit and delete
        keyboard.append([
            InlineKeyboardButton(
                f"{cls.EMOJI['edit']} Edit",
                callback_data=cls.encode_callback('task_edit', tid=task_id)
            ),
            InlineKeyboardButton(
                f"{cls.EMOJI['delete']} Delete",
                callback_data=cls.encode_callback('task_delete', tid=task_id)
            ),
        ])
        
        # Back button
        keyboard.append([
            InlineKeyboardButton(
                f"{cls.EMOJI['back']} Back to Tasks",
                callback_data=cls.encode_callback('menu_tasks')
            ),
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def file_actions(cls, file_id: str) -> InlineKeyboardMarkup:
        """Create action buttons for a file entry."""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['download']} Download",
                    callback_data=cls.encode_callback('file_download', fid=file_id)
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJI['share']} Share",
                    callback_data=cls.encode_callback('file_share', fid=file_id)
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['edit']} Edit Info",
                    callback_data=cls.encode_callback('file_edit', fid=file_id)
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJI['delete']} Delete",
                    callback_data=cls.encode_callback('file_delete', fid=file_id)
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['back']} Back to Files",
                    callback_data=cls.encode_callback('menu_files')
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def pagination(cls, current_page: int, total_pages: int, callback_prefix: str, **kwargs) -> List[InlineKeyboardButton]:
        """
        Create pagination buttons.
        
        Args:
            current_page: Current page number (0-indexed)
            total_pages: Total number of pages
            callback_prefix: Prefix for callback action
            **kwargs: Additional callback data
            
        Returns:
            List of pagination buttons
        """
        buttons = []
        
        if current_page > 0:
            buttons.append(InlineKeyboardButton(
                f"{cls.EMOJI['back']} Previous",
                callback_data=cls.encode_callback(callback_prefix, p=current_page - 1, **kwargs)
            ))
        
        # Page indicator
        buttons.append(InlineKeyboardButton(
            f"📄 {current_page + 1}/{total_pages}",
            callback_data=cls.encode_callback('noop')
        ))
        
        if current_page < total_pages - 1:
            buttons.append(InlineKeyboardButton(
                f"Next {cls.EMOJI['next']}",
                callback_data=cls.encode_callback(callback_prefix, p=current_page + 1, **kwargs)
            ))
        
        return buttons
    
    @classmethod
    def priority_selector(cls) -> InlineKeyboardMarkup:
        """Create priority selector keyboard."""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['priority_low']} Low",
                    callback_data=cls.encode_callback('select_priority', pr='low')
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJI['priority_medium']} Medium",
                    callback_data=cls.encode_callback('select_priority', pr='medium')
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJI['priority_high']} High",
                    callback_data=cls.encode_callback('select_priority', pr='high')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['cancel']} Cancel",
                    callback_data=cls.encode_callback('cancel')
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def date_selector(cls) -> InlineKeyboardMarkup:
        """Create date selector keyboard."""
        keyboard = [
            [
                InlineKeyboardButton(
                    "📅 Today",
                    callback_data=cls.encode_callback('select_date', d='today')
                ),
                InlineKeyboardButton(
                    "📅 Tomorrow",
                    callback_data=cls.encode_callback('select_date', d='tomorrow')
                ),
            ],
            [
                InlineKeyboardButton(
                    "📅 This Week",
                    callback_data=cls.encode_callback('select_date', d='week')
                ),
                InlineKeyboardButton(
                    "📅 Next Week",
                    callback_data=cls.encode_callback('select_date', d='next_week')
                ),
            ],
            [
                InlineKeyboardButton(
                    "✏️ Custom Date",
                    callback_data=cls.encode_callback('select_date', d='custom')
                ),
                InlineKeyboardButton(
                    "⏭️ Skip",
                    callback_data=cls.encode_callback('select_date', d='skip')
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['cancel']} Cancel",
                    callback_data=cls.encode_callback('cancel')
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def confirmation(cls, action: str, item_id: str, item_type: str) -> InlineKeyboardMarkup:
        """Create confirmation keyboard."""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['confirm']} Yes, {action}",
                    callback_data=cls.encode_callback(f'confirm_{action}', id=item_id, t=item_type)
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['cancel']} No, Cancel",
                    callback_data=cls.encode_callback('cancel')
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def back_to_menu(cls, menu: str = 'main') -> InlineKeyboardMarkup:
        """Create simple back button."""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJI['back']} Back to {menu.title()} Menu",
                    callback_data=cls.encode_callback(f'menu_{menu}' if menu != 'main' else 'main_menu')
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
