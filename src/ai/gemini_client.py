"""
QuikSafe Bot - Gemini AI Client
Integrates with Google Gemini API (free tier) for smart search and summarization.
"""

import google.generativeai as genai
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class GeminiClient:
    """Handles AI operations using Google Gemini API (free tier)."""
    
    def __init__(self, api_key: str):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Google Gemini API key
        """
        try:
            genai.configure(api_key=api_key)
            # Use gemini-pro model (free tier)
            self.model = genai.GenerativeModel('gemini-pro')
            logger.info("Gemini AI client initialized (free tier)")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
    
    def search_content(self, query: str, items: List[Dict[str, Any]], item_type: str) -> List[Dict[str, Any]]:
        """
        Smart search across items using natural language.
        
        Args:
            query: Natural language search query
            items: List of items to search through
            item_type: Type of items (passwords, tasks, files)
            
        Returns:
            List of relevant items ranked by relevance
        """
        if not items:
            return []
        
        try:
            # Create a searchable text representation of items
            items_text = self._format_items_for_search(items, item_type)
            
            prompt = f"""Given this search query: "{query}"
            
And these {item_type}:
{items_text}

Return the IDs of the most relevant items, ranked by relevance.
Only return item IDs that match the query, separated by commas.
If no items match, return "NONE".

Example response: "1,3,5" or "NONE"
"""
            
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            if result_text == "NONE":
                return []
            
            # Parse the response and filter items
            relevant_ids = [id.strip() for id in result_text.split(',')]
            return [item for item in items if str(item.get('id', '')) in relevant_ids]
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            # Fallback to simple text matching
            return self._simple_search(query, items, item_type)
    
    def summarize_tasks(self, tasks: List[Dict[str, Any]]) -> str:
        """
        Generate a summary of tasks.
        
        Args:
            tasks: List of task dictionaries
            
        Returns:
            AI-generated summary
        """
        if not tasks:
            return "You have no tasks."
        
        try:
            tasks_text = "\n".join([
                f"- {task.get('encrypted_content', 'N/A')} (Priority: {task.get('priority', 'medium')}, Status: {task.get('status', 'pending')})"
                for task in tasks
            ])
            
            prompt = f"""Summarize these tasks in a concise, helpful way:

{tasks_text}

Provide:
1. Total number of tasks
2. Breakdown by status
3. Priority items that need attention
4. Brief overview

Keep it under 200 words."""
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return f"You have {len(tasks)} tasks. Unable to generate detailed summary."
    
    def suggest_tags(self, content: str, content_type: str) -> List[str]:
        """
        Suggest relevant tags for content.
        
        Args:
            content: Content to analyze
            content_type: Type of content (password, task, file)
            
        Returns:
            List of suggested tags
        """
        try:
            prompt = f"""Suggest 3-5 relevant tags for this {content_type}:

"{content}"

Return only the tags, comma-separated, lowercase, no hashtags.
Example: work, important, finance"""
            
            response = self.model.generate_content(prompt)
            tags_text = response.text.strip()
            
            # Parse and clean tags
            tags = [tag.strip().lower() for tag in tags_text.split(',')]
            return tags[:5]  # Limit to 5 tags
            
        except Exception as e:
            logger.error(f"Tag suggestion failed: {e}")
            return []
    
    def _format_items_for_search(self, items: List[Dict[str, Any]], item_type: str) -> str:
        """Format items for search prompt."""
        formatted = []
        
        for i, item in enumerate(items, 1):
            if item_type == "passwords":
                formatted.append(f"{i}. Service: {item.get('service_name', 'N/A')}, Tags: {', '.join(item.get('tags', []))}")
            elif item_type == "tasks":
                formatted.append(f"{i}. Task: {item.get('encrypted_content', 'N/A')}, Priority: {item.get('priority', 'medium')}")
            elif item_type == "files":
                formatted.append(f"{i}. File: {item.get('file_name', 'N/A')}, Type: {item.get('file_type', 'N/A')}")
        
        return "\n".join(formatted)
    
    def _simple_search(self, query: str, items: List[Dict[str, Any]], item_type: str) -> List[Dict[str, Any]]:
        """Fallback simple text search."""
        query_lower = query.lower()
        results = []
        
        for item in items:
            # Search in different fields based on item type
            searchable_text = ""
            
            if item_type == "passwords":
                searchable_text = f"{item.get('service_name', '')} {' '.join(item.get('tags', []))}"
            elif item_type == "tasks":
                searchable_text = f"{item.get('encrypted_content', '')} {' '.join(item.get('tags', []))}"
            elif item_type == "files":
                searchable_text = f"{item.get('file_name', '')} {item.get('file_type', '')}"
            
            if query_lower in searchable_text.lower():
                results.append(item)
        
        return results


# Example usage
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv('GEMINI_API_KEY')
    
    if api_key:
        client = GeminiClient(api_key)
        
        # Test tag suggestion
        tags = client.suggest_tags("Gmail account password", "password")
        print(f"Suggested tags: {tags}")
        
        # Test task summarization
        sample_tasks = [
            {"encrypted_content": "Complete project report", "priority": "high", "status": "pending"},
            {"encrypted_content": "Buy groceries", "priority": "low", "status": "pending"},
            {"encrypted_content": "Call dentist", "priority": "medium", "status": "completed"}
        ]
        summary = client.summarize_tasks(sample_tasks)
        print(f"\nTask summary:\n{summary}")
    else:
        print("GEMINI_API_KEY not found in environment")
