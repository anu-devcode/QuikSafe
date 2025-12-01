"""
QuikSafe Bot - Gemini AI Client
Integrates with Google Gemini API (free tier) for smart search and summarization.
"""

import google.generativeai as genai
from typing import List, Dict, Any, Optional
import logging
import json

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
            # We need to map the 1-based index used in the prompt to the actual item ID
            items_text, index_map = self._format_items_for_search(items, item_type)
            
            prompt = f"""Given this search query: "{query}"
            
And these {item_type}:
{items_text}

Return the IDs (the numbers at the start of each line) of the most relevant items, ranked by relevance.
Only return the numbers, separated by commas.
If no items match, return "NONE".

Example response: "1,3,5" or "NONE"
"""
            
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            if result_text == "NONE":
                return []
            
            # Parse the response and filter items
            relevant_indices = [idx.strip() for idx in result_text.split(',')]
            results = []
            
            for idx in relevant_indices:
                if idx in index_map:
                    # Find the item with this ID
                    item_id = index_map[idx]
                    for item in items:
                        if item.get('id') == item_id:
                            results.append(item)
                            break
            
            return results
            
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
    
    def _format_items_for_search(self, items: List[Dict[str, Any]], item_type: str) -> tuple[str, Dict[str, str]]:
        """Format items for search prompt and return index mapping."""
        formatted = []
        index_map = {}
        
        for i, item in enumerate(items, 1):
            index_str = str(i)
            index_map[index_str] = item.get('id')
            
            if item_type == "passwords":
                formatted.append(f"{i}. Service: {item.get('service_name', 'N/A')}, Tags: {', '.join(item.get('tags', []))}")
            elif item_type == "tasks":
                formatted.append(f"{i}. Task: {item.get('encrypted_content', 'N/A')}, Priority: {item.get('priority', 'medium')}")
            elif item_type == "files":
                formatted.append(f"{i}. File: {item.get('file_name', 'N/A')}, Type: {item.get('file_type', 'N/A')}")
        
        return "\n".join(formatted), index_map
    
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
