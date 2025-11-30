"""
QuikSafe Bot - Scene Manager
Framework for managing multi-step wizard flows.
"""

from typing import Dict, Any, Optional, Callable, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SceneState(Enum):
    """Scene states."""
    IDLE = "idle"
    ACTIVE = "active"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Scene:
    """Represents a multi-step wizard scene."""
    
    def __init__(self, scene_id: str, steps: List[str]):
        """
        Initialize a scene.
        
        Args:
            scene_id: Unique identifier for the scene
            steps: List of step names in order
        """
        self.scene_id = scene_id
        self.steps = steps
        self.current_step = 0
        self.state = SceneState.IDLE
        self.data = {}
    
    def start(self):
        """Start the scene."""
        self.state = SceneState.ACTIVE
        self.current_step = 0
        self.data = {}
    
    def next_step(self) -> Optional[str]:
        """
        Move to next step.
        
        Returns:
            Next step name or None if completed
        """
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.state = SceneState.COMPLETED
            return None
        return self.steps[self.current_step]
    
    def previous_step(self) -> Optional[str]:
        """
        Move to previous step.
        
        Returns:
            Previous step name or None if at start
        """
        if self.current_step > 0:
            self.current_step -= 1
            return self.steps[self.current_step]
        return None
    
    def get_current_step(self) -> Optional[str]:
        """Get current step name."""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None
    
    def set_data(self, key: str, value: Any):
        """Store data for this scene."""
        self.data[key] = value
    
    def get_data(self, key: str, default: Any = None) -> Any:
        """Retrieve data from this scene."""
        return self.data.get(key, default)
    
    def get_all_data(self) -> Dict[str, Any]:
        """Get all scene data."""
        return self.data.copy()
    
    def cancel(self):
        """Cancel the scene."""
        self.state = SceneState.CANCELLED
        self.data = {}
    
    def complete(self):
        """Mark scene as completed."""
        self.state = SceneState.COMPLETED
    
    def get_progress(self) -> tuple[int, int]:
        """
        Get scene progress.
        
        Returns:
            Tuple of (current_step, total_steps)
        """
        return (self.current_step + 1, len(self.steps))


class SceneManager:
    """Manages wizard scenes for users."""
    
    def __init__(self):
        """Initialize scene manager."""
        self.active_scenes: Dict[int, Scene] = {}  # telegram_id -> Scene
        self.scene_templates: Dict[str, List[str]] = {
            # Password wizard
            'save_password': [
                'service_name',
                'username',
                'password',
                'tags',
                'confirm'
            ],
            
            # Task wizard
            'add_task': [
                'content',
                'priority',
                'due_date',
                'tags',
                'confirm'
            ],
            
            # File upload wizard
            'upload_file': [
                'file',
                'description',
                'tags',
                'confirm'
            ],
            
            # Edit password wizard
            'edit_password': [
                'select_field',
                'new_value',
                'confirm'
            ],
            
            # Edit task wizard
            'edit_task': [
                'select_field',
                'new_value',
                'confirm'
            ],
        }
    
    def start_scene(self, telegram_id: int, scene_id: str) -> Optional[Scene]:
        """
        Start a new scene for a user.
        
        Args:
            telegram_id: User's Telegram ID
            scene_id: Scene template ID
            
        Returns:
            Scene instance or None if template not found
        """
        if scene_id not in self.scene_templates:
            logger.error(f"Scene template not found: {scene_id}")
            return None
        
        # Cancel any existing scene
        if telegram_id in self.active_scenes:
            self.active_scenes[telegram_id].cancel()
        
        # Create new scene
        steps = self.scene_templates[scene_id]
        scene = Scene(scene_id, steps)
        scene.start()
        
        self.active_scenes[telegram_id] = scene
        logger.info(f"Started scene '{scene_id}' for user {telegram_id}")
        
        return scene
    
    def get_scene(self, telegram_id: int) -> Optional[Scene]:
        """
        Get active scene for a user.
        
        Args:
            telegram_id: User's Telegram ID
            
        Returns:
            Scene instance or None
        """
        return self.active_scenes.get(telegram_id)
    
    def has_active_scene(self, telegram_id: int) -> bool:
        """
        Check if user has an active scene.
        
        Args:
            telegram_id: User's Telegram ID
            
        Returns:
            True if user has active scene
        """
        scene = self.active_scenes.get(telegram_id)
        return scene is not None and scene.state == SceneState.ACTIVE
    
    def advance_scene(self, telegram_id: int) -> Optional[str]:
        """
        Advance scene to next step.
        
        Args:
            telegram_id: User's Telegram ID
            
        Returns:
            Next step name or None
        """
        scene = self.get_scene(telegram_id)
        if not scene:
            return None
        
        return scene.next_step()
    
    def go_back(self, telegram_id: int) -> Optional[str]:
        """
        Go back to previous step.
        
        Args:
            telegram_id: User's Telegram ID
            
        Returns:
            Previous step name or None
        """
        scene = self.get_scene(telegram_id)
        if not scene:
            return None
        
        return scene.previous_step()
    
    def cancel_scene(self, telegram_id: int):
        """
        Cancel active scene for a user.
        
        Args:
            telegram_id: User's Telegram ID
        """
        if telegram_id in self.active_scenes:
            self.active_scenes[telegram_id].cancel()
            del self.active_scenes[telegram_id]
            logger.info(f"Cancelled scene for user {telegram_id}")
    
    def complete_scene(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Complete scene and return collected data.
        
        Args:
            telegram_id: User's Telegram ID
            
        Returns:
            Scene data or None
        """
        scene = self.get_scene(telegram_id)
        if not scene:
            return None
        
        scene.complete()
        data = scene.get_all_data()
        
        # Clean up
        del self.active_scenes[telegram_id]
        logger.info(f"Completed scene '{scene.scene_id}' for user {telegram_id}")
        
        return data
    
    def set_scene_data(self, telegram_id: int, key: str, value: Any) -> bool:
        """
        Store data in active scene.
        
        Args:
            telegram_id: User's Telegram ID
            key: Data key
            value: Data value
            
        Returns:
            True if successful
        """
        scene = self.get_scene(telegram_id)
        if not scene:
            return False
        
        scene.set_data(key, value)
        return True
    
    def get_scene_data(self, telegram_id: int, key: str, default: Any = None) -> Any:
        """
        Retrieve data from active scene.
        
        Args:
            telegram_id: User's Telegram ID
            key: Data key
            default: Default value if not found
            
        Returns:
            Data value or default
        """
        scene = self.get_scene(telegram_id)
        if not scene:
            return default
        
        return scene.get_data(key, default)
    
    def get_progress(self, telegram_id: int) -> Optional[tuple[int, int]]:
        """
        Get scene progress.
        
        Args:
            telegram_id: User's Telegram ID
            
        Returns:
            Tuple of (current_step, total_steps) or None
        """
        scene = self.get_scene(telegram_id)
        if not scene:
            return None
        
        return scene.get_progress()
    
    def get_current_step(self, telegram_id: int) -> Optional[str]:
        """
        Get current step name.
        
        Args:
            telegram_id: User's Telegram ID
            
        Returns:
            Step name or None
        """
        scene = self.get_scene(telegram_id)
        if not scene:
            return None
        
        return scene.get_current_step()
