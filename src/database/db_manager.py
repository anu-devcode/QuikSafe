"""
QuikSafe Bot - Database Manager
Handles all database operations with Supabase PostgreSQL.
"""

from supabase import create_client, Client
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages all database operations for QuikSafe Bot."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize database connection.
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key
        """
        try:
            self.client: Client = create_client(supabase_url, supabase_key)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    # ==================== User Operations ====================
    
    def create_user(self, telegram_id: int, master_password_hash: str) -> Optional[Dict[str, Any]]:
        """
        Create a new user.
        
        Args:
            telegram_id: Telegram user ID
            master_password_hash: Hashed master password
            
        Returns:
            Created user data or None if failed
        """
        try:
            result = self.client.table('users').insert({
                'telegram_id': telegram_id,
                'master_password_hash': master_password_hash
            }).execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return None
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by Telegram ID.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            User data or None if not found
        """
        try:
            result = self.client.table('users').select('*').eq('telegram_id', telegram_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            return None
    
    def update_master_password(self, telegram_id: int, new_password_hash: str) -> bool:
        """
        Update user's master password.
        
        Args:
            telegram_id: Telegram user ID
            new_password_hash: New hashed password
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.table('users').update({
                'master_password_hash': new_password_hash
            }).eq('telegram_id', telegram_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update master password: {e}")
            return False
    
    # ==================== Password Operations ====================
    
    def save_password(self, user_id: str, service_name: str, encrypted_username: str,
                     encrypted_password: str, tags: List[str] = None, notes: str = None) -> Optional[Dict[str, Any]]:
        """
        Save a new password entry.
        
        Args:
            user_id: User UUID
            service_name: Name of the service
            encrypted_username: Encrypted username
            encrypted_password: Encrypted password
            tags: Optional list of tags
            notes: Optional encrypted notes
            
        Returns:
            Created password entry or None if failed
        """
        try:
            result = self.client.table('passwords').insert({
                'user_id': user_id,
                'service_name': service_name,
                'encrypted_username': encrypted_username,
                'encrypted_password': encrypted_password,
                'tags': tags or [],
                'notes': notes
            }).execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to save password: {e}")
            return None
    
    def get_passwords(self, user_id: str, service_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get password entries for a user.
        
        Args:
            user_id: User UUID
            service_name: Optional service name filter
            
        Returns:
            List of password entries
        """
        try:
            query = self.client.table('passwords').select('*').eq('user_id', user_id)
            
            if service_name:
                query = query.ilike('service_name', f'%{service_name}%')
            
            result = query.order('created_at', desc=True).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Failed to get passwords: {e}")
            return []
    
    def delete_password(self, password_id: str, user_id: str) -> bool:
        """
        Delete a password entry.
        
        Args:
            password_id: Password entry UUID
            user_id: User UUID (for security)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.table('passwords').delete().eq('id', password_id).eq('user_id', user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete password: {e}")
            return False
    
    # ==================== Task Operations ====================
    
    def create_task(self, user_id: str, encrypted_content: str, priority: str = 'medium',
                   due_date: Optional[datetime] = None, tags: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create a new task.
        
        Args:
            user_id: User UUID
            encrypted_content: Encrypted task content
            priority: Task priority (low, medium, high)
            due_date: Optional due date
            tags: Optional list of tags
            
        Returns:
            Created task or None if failed
        """
        try:
            result = self.client.table('tasks').insert({
                'user_id': user_id,
                'encrypted_content': encrypted_content,
                'priority': priority,
                'due_date': due_date.isoformat() if due_date else None,
                'tags': tags or []
            }).execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return None
    
    def get_tasks(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get tasks for a user.
        
        Args:
            user_id: User UUID
            status: Optional status filter (pending, in_progress, completed)
            
        Returns:
            List of tasks
        """
        try:
            query = self.client.table('tasks').select('*').eq('user_id', user_id)
            
            if status:
                query = query.eq('status', status)
            
            result = query.order('created_at', desc=True).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return []
    
    def update_task_status(self, task_id: str, user_id: str, status: str) -> bool:
        """
        Update task status.
        
        Args:
            task_id: Task UUID
            user_id: User UUID (for security)
            status: New status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            update_data = {'status': status}
            if status == 'completed':
                update_data['completed_at'] = datetime.now().isoformat()
            
            self.client.table('tasks').update(update_data).eq('id', task_id).eq('user_id', user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
            return False
    
    def delete_task(self, task_id: str, user_id: str) -> bool:
        """
        Delete a task.
        
        Args:
            task_id: Task UUID
            user_id: User UUID (for security)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.table('tasks').delete().eq('id', task_id).eq('user_id', user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete task: {e}")
            return False
    
    # ==================== File Operations ====================
    
    def save_file(self, user_id: str, file_id: str, file_name: str, file_type: str,
                 file_size: int, encrypted_description: str = None, tags: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Save file metadata.
        
        Args:
            user_id: User UUID
            file_id: Telegram file ID
            file_name: Original file name
            file_type: MIME type
            file_size: File size in bytes
            encrypted_description: Optional encrypted description
            tags: Optional list of tags
            
        Returns:
            Created file entry or None if failed
        """
        try:
            result = self.client.table('files').insert({
                'user_id': user_id,
                'file_id': file_id,
                'file_name': file_name,
                'file_type': file_type,
                'file_size': file_size,
                'encrypted_description': encrypted_description,
                'tags': tags or []
            }).execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            return None
    
    def get_files(self, user_id: str, file_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get files for a user.
        
        Args:
            user_id: User UUID
            file_name: Optional file name filter
            
        Returns:
            List of files
        """
        try:
            query = self.client.table('files').select('*').eq('user_id', user_id)
            
            if file_name:
                query = query.ilike('file_name', f'%{file_name}%')
            
            result = query.order('created_at', desc=True).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Failed to get files: {e}")
            return []
    
    def delete_file(self, file_id: str, user_id: str) -> bool:
        """
        Delete a file entry.
        
        Args:
            file_id: File entry UUID
            user_id: User UUID (for security)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.table('files').delete().eq('id', file_id).eq('user_id', user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False
