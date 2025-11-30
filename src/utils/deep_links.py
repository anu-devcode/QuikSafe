"""
QuikSafe Bot - Deep Links
Support for deep linking to specific bot features.
"""

from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DeepLinkManager:
    """Manages deep links for direct feature access."""
    
    # Deep link prefixes
    PREFIXES = {
        'add_password': 'addpwd',
        'add_task': 'addtsk',
        'upload_file': 'upfile',
        'view_passwords': 'vpwd',
        'view_tasks': 'vtsk',
        'view_files': 'vfile',
        'search': 'srch',
        'settings': 'sett',
    }
    
    @classmethod
    def generate_link(cls, bot_username: str, action: str, **params) -> Optional[str]:
        """
        Generate a deep link URL.
        
        Args:
            bot_username: Bot's username (without @)
            action: Action identifier
            **params: Additional parameters
            
        Returns:
            Deep link URL or None if action invalid
        """
        if action not in cls.PREFIXES:
            logger.error(f"Invalid deep link action: {action}")
            return None
        
        prefix = cls.PREFIXES[action]
        
        # Build parameter string
        param_str = ""
        if params:
            param_parts = [f"{k}={v}" for k, v in params.items()]
            param_str = "_" + "_".join(param_parts)
        
        link = f"https://t.me/{bot_username}?start={prefix}{param_str}"
        return link
    
    @classmethod
    def parse_link(cls, start_param: str) -> Optional[Dict[str, Any]]:
        """
        Parse deep link parameters.
        
        Args:
            start_param: The parameter from /start command
            
        Returns:
            Dictionary with action and params, or None if invalid
        """
        if not start_param:
            return None
        
        # Find matching prefix
        action = None
        for action_name, prefix in cls.PREFIXES.items():
            if start_param.startswith(prefix):
                action = action_name
                param_str = start_param[len(prefix):]
                break
        
        if not action:
            return None
        
        # Parse parameters
        params = {}
        if param_str and param_str.startswith('_'):
            param_str = param_str[1:]  # Remove leading underscore
            param_parts = param_str.split('_')
            
            for part in param_parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    params[key] = value
        
        return {
            'action': action,
            'params': params
        }
    
    @classmethod
    def get_action_description(cls, action: str) -> str:
        """
        Get human-readable description of action.
        
        Args:
            action: Action identifier
            
        Returns:
            Description string
        """
        descriptions = {
            'add_password': '🔐 Save a new password',
            'add_task': '✅ Create a new task',
            'upload_file': '📁 Upload a file',
            'view_passwords': '🔐 View your passwords',
            'view_tasks': '✅ View your tasks',
            'view_files': '📁 Browse your files',
            'search': '🔍 Search your data',
            'settings': '⚙️ Open settings',
        }
        return descriptions.get(action, 'Unknown action')


# Example usage and documentation
DEEP_LINK_EXAMPLES = """
Deep Link Examples:

1. Add Password:
   https://t.me/your_bot?start=addpwd

2. Add Task:
   https://t.me/your_bot?start=addtsk

3. Upload File:
   https://t.me/your_bot?start=upfile

4. View Passwords:
   https://t.me/your_bot?start=vpwd

5. View Tasks (with filter):
   https://t.me/your_bot?start=vtsk_filter=pending

6. Search:
   https://t.me/your_bot?start=srch_q=work

7. Settings:
   https://t.me/your_bot?start=sett
"""
