"""
QuikSafe Bot - Message Formatters
Formats messages for clean Telegram responses.
"""

from typing import List, Dict, Any
from datetime import datetime


def format_password_list(passwords: List[Dict[str, Any]]) -> str:
    """
    Format password list for display.
    
    Args:
        passwords: List of password entries
        
    Returns:
        Formatted message string
    """
    if not passwords:
        return "🔐 You have no saved passwords."
    
    message = f"🔐 **Your Saved Passwords** ({len(passwords)} total)\n\n"
    
    for i, pwd in enumerate(passwords, 1):
        service = pwd.get('service_name', 'Unknown')
        tags = pwd.get('tags', [])
        created = pwd.get('created_at', '')
        
        message += f"{i}. **{service}**\n"
        if tags:
            message += f"   Tags: {', '.join(tags)}\n"
        message += f"   ID: `{pwd.get('id', 'N/A')}`\n"
        message += f"   Created: {format_datetime(created)}\n\n"
    
    return message


def format_password_details(password: Dict[str, Any], decrypted_username: str, decrypted_password: str) -> str:
    """
    Format password details for display.
    
    Args:
        password: Password entry
        decrypted_username: Decrypted username
        decrypted_password: Decrypted password
        
    Returns:
        Formatted message string
    """
    service = password.get('service_name', 'Unknown')
    tags = password.get('tags', [])
    
    message = f"🔐 **{service}**\n\n"
    message += f"👤 Username: `{decrypted_username}`\n"
    message += f"🔑 Password: `{decrypted_password}`\n\n"
    
    if tags:
        message += f"🏷️ Tags: {', '.join(tags)}\n"
    
    message += f"\n⚠️ This message will be deleted in 60 seconds for security."
    
    return message


def format_task_list(tasks: List[Dict[str, Any]]) -> str:
    """
    Format task list for display.
    
    Args:
        tasks: List of task entries
        
    Returns:
        Formatted message string
    """
    if not tasks:
        return "✅ You have no tasks."
    
    # Group by status
    pending = [t for t in tasks if t.get('status') == 'pending']
    in_progress = [t for t in tasks if t.get('status') == 'in_progress']
    completed = [t for t in tasks if t.get('status') == 'completed']
    
    message = f"✅ **Your Tasks** ({len(tasks)} total)\n\n"
    
    if pending:
        message += "📋 **Pending**\n"
        for task in pending:
            message += format_task_item(task)
        message += "\n"
    
    if in_progress:
        message += "🔄 **In Progress**\n"
        for task in in_progress:
            message += format_task_item(task)
        message += "\n"
    
    if completed:
        message += "✔️ **Completed**\n"
        for task in completed[:5]:  # Show only last 5 completed
            message += format_task_item(task)
        if len(completed) > 5:
            message += f"   ... and {len(completed) - 5} more\n"
    
    return message


def format_task_item(task: Dict[str, Any]) -> str:
    """Format a single task item."""
    priority_emoji = {
        'low': '🔵',
        'medium': '🟡',
        'high': '🔴'
    }
    
    priority = task.get('priority', 'medium')
    content = task.get('encrypted_content', 'N/A')
    task_id = task.get('id', 'N/A')
    due_date = task.get('due_date')
    
    item = f"{priority_emoji.get(priority, '⚪')} {content}\n"
    item += f"   ID: `{task_id}`"
    
    if due_date:
        item += f" | Due: {format_datetime(due_date)}"
    
    item += "\n"
    
    return item


def format_task_details(task: Dict[str, Any]) -> str:
    """
    Format task details for display.
    
    Args:
        task: Task entry
        
    Returns:
        Formatted message string
    """
    priority_emoji = {
        'low': '🔵',
        'medium': '🟡',
        'high': '🔴'
    }
    
    priority = task.get('priority', 'medium')
    content = task.get('encrypted_content', 'N/A')
    status = task.get('status', 'pending')
    tags = task.get('tags', [])
    due_date = task.get('due_date')
    created_at = task.get('created_at')
    
    status_icon = "✅" if status == 'completed' else "📋"
    
    message = f"{status_icon} **Task Details**\n\n"
    message += f"📝 **Content**: {content}\n"
    message += f"⚡ **Priority**: {priority_emoji.get(priority, '⚪')} {priority.title()}\n"
    message += f"📊 **Status**: {status.title()}\n"
    
    if due_date:
        message += f"📅 **Due**: {format_datetime(due_date)}\n"
        
    if tags:
        message += f"🏷️ **Tags**: {', '.join(tags)}\n"
        
    message += f"\n🕒 Created: {format_datetime(created_at)}\n"
    
    return message


def format_file_list(files: List[Dict[str, Any]]) -> str:
    """
    Format file list for display.
    
    Args:
        files: List of file entries
        
    Returns:
        Formatted message string
    """
    if not files:
        return "📁 You have no saved files."
    
    message = f"📁 **Your Saved Files** ({len(files)} total)\n\n"
    
    for i, file in enumerate(files, 1):
        file_name = file.get('file_name', 'Unknown')
        file_type = file.get('file_type', 'unknown')
        file_size = file.get('file_size', 0)
        tags = file.get('tags', [])
        
        # Get emoji based on file type
        emoji = get_file_emoji(file_type)
        
        message += f"{i}. {emoji} **{file_name}**\n"
        message += f"   Type: {file_type}\n"
        message += f"   Size: {format_file_size(file_size)}\n"
        
        if tags:
            message += f"   Tags: {', '.join(tags)}\n"
        
        message += f"   ID: `{file.get('id', 'N/A')}`\n\n"
    
    return message


def format_file_details(file: Dict[str, Any], description: str = "") -> str:
    """
    Format file details for display.
    
    Args:
        file: File entry
        description: Decrypted description
        
    Returns:
        Formatted message string
    """
    file_name = file.get('file_name', 'Unknown')
    file_type = file.get('file_type', 'unknown')
    file_size = file.get('file_size', 0)
    tags = file.get('tags', [])
    created_at = file.get('created_at')
    
    emoji = get_file_emoji(file_type)
    
    message = f"{emoji} **File Details**\n\n"
    message += f"📄 **Name**: `{file_name}`\n"
    message += f"📦 **Size**: {format_file_size(file_size)}\n"
    message += f"📎 **Type**: {file_type}\n"
    
    if description:
        message += f"\n📝 **Description**: {description}\n"
        
    if tags:
        message += f"\n🏷️ **Tags**: {', '.join(tags)}\n"
        
    message += f"\n🕒 Uploaded: {format_datetime(created_at)}\n"
    
    return message


def format_search_results(results: List[Dict[str, Any]], result_type: str) -> str:
    """
    Format search results for display.
    
    Args:
        results: List of search results
        result_type: Type of results (passwords, tasks, files)
        
    Returns:
        Formatted message string
    """
    if not results:
        return f"🔍 No {result_type} found matching your search."
    
    message = f"🔍 **Search Results** ({len(results)} {result_type} found)\n\n"
    
    if result_type == "passwords":
        for pwd in results:
            message += f"🔐 {pwd.get('service_name', 'Unknown')} (ID: `{pwd.get('id', 'N/A')}`)\n"
    elif result_type == "tasks":
        for task in results:
            message += format_task_item(task)
    elif result_type == "files":
        for file in results:
            emoji = get_file_emoji(file.get('file_type', ''))
            message += f"{emoji} {file.get('file_name', 'Unknown')} (ID: `{file.get('id', 'N/A')}`)\n"
    
    return message


def format_datetime(dt_str: str) -> str:
    """Format datetime string for display."""
    if not dt_str:
        return "N/A"
    
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return dt_str


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_file_emoji(file_type: str) -> str:
    """Get emoji based on file type."""
    if 'image' in file_type:
        return '🖼️'
    elif 'video' in file_type:
        return '🎥'
    elif 'audio' in file_type:
        return '🎵'
    elif 'pdf' in file_type:
        return '📄'
    elif 'document' in file_type or 'text' in file_type:
        return '📝'
    elif 'zip' in file_type or 'archive' in file_type:
        return '📦'
    else:
        return '📎'


def format_welcome_message(user_name: str) -> str:
    """Format welcome message for new users."""
    return f"""👋 **Welcome to QuikSafe Bot, {user_name}!**

I'm your secure personal assistant for managing:
🔐 Passwords
✅ Tasks
📁 Files

**Getting Started:**
1. Set up your master password (required for security)
2. Start saving your data securely

**Available Commands:**
/help - Show all commands
/savepassword - Save a new password
/addtask - Create a new task
/search - Smart search across all your data

Let's get started! Please create a master password to secure your data.
"""


def format_help_message() -> str:
    """Format help message with all commands."""
    return """📖 **QuikSafe Bot - Help**

**Password Management** 🔐
/savepassword - Save a new password
/getpassword <service> - Retrieve a password
/listpasswords - List all saved passwords
/deletepassword <id> - Delete a password

**Task Management** ✅
/addtask <task> - Create a new task
/listtasks - View all tasks
/completetask <id> - Mark task as complete
/deletetask <id> - Delete a task

**File Management** 📁
Send any file to save it
/listfiles - List all saved files
/getfile <name> - Retrieve a file
/deletefile <id> - Delete a file

**AI Features** 🤖
/search <query> - Smart search across all data
/summarize - Get AI summary of your tasks

**Other Commands**
/help - Show this help message
/start - Restart the bot

💡 **Tips:**
- Use tags (e.g., #work #important) to organize your data
- All sensitive data is encrypted with AES-256
- Your master password is never stored in plaintext
"""
