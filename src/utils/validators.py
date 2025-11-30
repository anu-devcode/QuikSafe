"""
QuikSafe Bot - Input Validators
Validates user input for security and data integrity.
"""

import re
from typing import Tuple, Optional
from datetime import datetime


def validate_service_name(service_name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate service name for password storage.
    
    Args:
        service_name: Service name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not service_name or not service_name.strip():
        return False, "Service name cannot be empty"
    
    if len(service_name) > 100:
        return False, "Service name must be less than 100 characters"
    
    # Allow alphanumeric, spaces, dots, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9\s\.\-_]+$', service_name):
        return False, "Service name contains invalid characters"
    
    return True, None


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Validate username.
    
    Args:
        username: Username to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username or not username.strip():
        return False, "Username cannot be empty"
    
    if len(username) > 255:
        return False, "Username must be less than 255 characters"
    
    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password (not master password, just stored passwords).
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Password cannot be empty"
    
    if len(password) > 500:
        return False, "Password must be less than 500 characters"
    
    return True, None


def validate_task_content(content: str) -> Tuple[bool, Optional[str]]:
    """
    Validate task content.
    
    Args:
        content: Task content to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not content or not content.strip():
        return False, "Task content cannot be empty"
    
    if len(content) > 1000:
        return False, "Task content must be less than 1000 characters"
    
    return True, None


def validate_priority(priority: str) -> Tuple[bool, Optional[str]]:
    """
    Validate task priority.
    
    Args:
        priority: Priority to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_priorities = ['low', 'medium', 'high']
    
    if priority.lower() not in valid_priorities:
        return False, f"Priority must be one of: {', '.join(valid_priorities)}"
    
    return True, None


def validate_due_date(date_str: str) -> Tuple[bool, Optional[str], Optional[datetime]]:
    """
    Validate and parse due date.
    
    Args:
        date_str: Date string to validate (YYYY-MM-DD format)
        
    Returns:
        Tuple of (is_valid, error_message, parsed_datetime)
    """
    try:
        # Try parsing YYYY-MM-DD format
        parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Check if date is in the past
        if parsed_date.date() < datetime.now().date():
            return False, "Due date cannot be in the past", None
        
        return True, None, parsed_date
    except ValueError:
        return False, "Invalid date format. Use YYYY-MM-DD (e.g., 2024-12-31)", None


def validate_tags(tags: list) -> Tuple[bool, Optional[str]]:
    """
    Validate tags list.
    
    Args:
        tags: List of tags to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(tags, list):
        return False, "Tags must be a list"
    
    if len(tags) > 10:
        return False, "Maximum 10 tags allowed"
    
    for tag in tags:
        if not isinstance(tag, str):
            return False, "All tags must be strings"
        
        if len(tag) > 50:
            return False, "Each tag must be less than 50 characters"
        
        # Allow alphanumeric, hyphens, underscores
        if not re.match(r'^[a-zA-Z0-9\-_]+$', tag):
            return False, f"Tag '{tag}' contains invalid characters"
    
    return True, None


def validate_file_name(file_name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate file name.
    
    Args:
        file_name: File name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_name or not file_name.strip():
        return False, "File name cannot be empty"
    
    if len(file_name) > 255:
        return False, "File name must be less than 255 characters"
    
    # Check for invalid characters in file names
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in invalid_chars:
        if char in file_name:
            return False, f"File name cannot contain '{char}'"
    
    return True, None


def sanitize_input(text: str) -> str:
    """
    Sanitize user input by removing potentially dangerous characters.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text
    """
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def parse_tags_from_text(text: str) -> list:
    """
    Parse tags from text (hashtags or comma-separated).
    
    Args:
        text: Text containing tags
        
    Returns:
        List of parsed tags
    """
    tags = []
    
    # Extract hashtags
    hashtags = re.findall(r'#(\w+)', text)
    tags.extend(hashtags)
    
    # If no hashtags, try comma-separated
    if not tags and ',' in text:
        tags = [tag.strip() for tag in text.split(',')]
    
    # Clean and deduplicate
    tags = [tag.lower() for tag in tags if tag]
    tags = list(set(tags))  # Remove duplicates
    
    return tags[:10]  # Limit to 10 tags
