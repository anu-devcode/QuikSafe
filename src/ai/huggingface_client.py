"""
QuikSafe Bot - Hugging Face AI Client
Uses Hugging Face Inference API for search, summarization, and tag intelligence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
import json
import logging
import re

import requests

logger = logging.getLogger(__name__)


class HuggingFaceClient:
    """Handles AI operations using Hugging Face Inference API."""

    CHAT_ENDPOINT = "https://router.huggingface.co/v1/chat/completions"

    def __init__(
        self,
        api_key: str,
        chat_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
        timeout_seconds: int = 20,
    ):
        self.api_key = api_key.strip()
        self.chat_model = chat_model
        self.timeout_seconds = timeout_seconds
        self.enabled = bool(self.api_key)

        if self.enabled:
            logger.info("Hugging Face AI client initialized")
        else:
            logger.warning("Hugging Face API key is missing; falling back to local AI heuristics")

    def search_content(self, query: str, items: List[Dict[str, Any]], item_type: str) -> List[Dict[str, Any]]:
        """
        Hybrid search:
        1) local lexical ranking
        2) optional LLM reranking on top candidates
        """
        if not items or not query.strip():
            return []

        normalized_query = self._normalize_text(query)
        query_tokens = self._tokenize(normalized_query)
        scored: List[Tuple[float, Dict[str, Any]]] = []

        for item in items:
            searchable_text = self._build_search_text(item, item_type)
            normalized_item_text = self._normalize_text(searchable_text)
            score = self._score_text_relevance(normalized_query, query_tokens, normalized_item_text)
            if score > 0:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            return []

        top_candidates = [item for _, item in scored[:10]]

        if not self.enabled or len(top_candidates) <= 1:
            return top_candidates

        reranked = self._rerank_with_llm(query, top_candidates, item_type)
        return reranked if reranked else top_candidates

    def summarize_tasks(self, tasks: List[Dict[str, Any]]) -> str:
        """Summarize tasks with deterministic stats and optional LLM narrative."""
        if not tasks:
            return "You have no tasks."

        total = len(tasks)
        by_status = {"pending": 0, "in_progress": 0, "completed": 0}
        by_priority = {"high": 0, "medium": 0, "low": 0}

        pending_tasks: List[Dict[str, Any]] = []
        overdue_count = 0

        for task in tasks:
            status = task.get("status", "pending")
            priority = task.get("priority", "medium")

            if status in by_status:
                by_status[status] += 1
            if priority in by_priority:
                by_priority[priority] += 1

            if status != "completed":
                pending_tasks.append(task)
                if self._is_overdue(task.get("due_date")):
                    overdue_count += 1

        prioritized = self.prioritize_tasks(tasks)[:5]
        top_focus = [entry["content"] for entry in prioritized if entry["status"] != "completed"]

        baseline = (
            f"Total tasks: {total}\n"
            f"Status: pending={by_status['pending']}, in_progress={by_status['in_progress']}, completed={by_status['completed']}\n"
            f"Priority: high={by_priority['high']}, medium={by_priority['medium']}, low={by_priority['low']}\n"
            f"Overdue tasks: {overdue_count}\n"
        )

        if top_focus:
            baseline += "Top focus items:\n" + "\n".join([f"- {item}" for item in top_focus[:3]])
        else:
            baseline += "Top focus items:\n- No urgent open tasks."

        if not self.enabled:
            return baseline

        prompt = (
            "Create a concise weekly productivity summary under 180 words. "
            "Use plain text with sections: Snapshot, Risks, Next Actions. "
            "Base it on this data:\n\n"
            f"{baseline}"
        )
        ai_text = self._chat(prompt)
        return ai_text if ai_text else baseline

    def suggest_tags(self, content: str, content_type: str) -> List[str]:
        """Suggest tags using local NLP heuristics with optional LLM enrichment."""
        if not content:
            return []

        text = self._normalize_text(content)
        candidates: List[str] = []

        keyword_map = {
            "finance": ["bank", "invoice", "tax", "payment", "salary", "finance", "budget"],
            "work": ["project", "client", "meeting", "office", "work", "deadline"],
            "personal": ["family", "home", "personal", "health"],
            "security": ["password", "2fa", "auth", "security", "token"],
            "travel": ["flight", "hotel", "trip", "travel"],
            "study": ["study", "course", "learn", "exam", "assignment"],
            "media": ["image", "video", "photo", "audio", "document"],
            "urgent": ["urgent", "asap", "today", "critical", "important"],
        }

        for tag, words in keyword_map.items():
            if any(word in text for word in words):
                candidates.append(tag)

        words = [w for w in self._tokenize(text) if len(w) >= 4 and w not in self._stopwords()]
        candidates.extend(words[:4])

        if self.enabled:
            prompt = (
                "Return 3 to 5 short lowercase tags as a JSON array for this content. "
                "Do not include hashtags or explanations.\n"
                f"Content type: {content_type}\n"
                f"Content: {content}"
            )
            ai_tags = self._chat_json_array(prompt)
            if ai_tags:
                candidates.extend(ai_tags)

        cleaned = self._clean_tags(candidates)
        return cleaned[:6]

    def prioritize_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank tasks by urgency and impact."""
        ranked: List[Dict[str, Any]] = []

        for task in tasks:
            status = task.get("status", "pending")
            priority = task.get("priority", "medium")
            content = task.get("encrypted_content") or task.get("content") or "Untitled task"
            due_date_raw = task.get("due_date")

            score = 0.0
            reasons: List[str] = []

            if status == "completed":
                score -= 50
                reasons.append("already completed")
            elif status == "in_progress":
                score += 25
                reasons.append("already started")
            else:
                score += 15
                reasons.append("pending")

            if priority == "high":
                score += 35
                reasons.append("high priority")
            elif priority == "medium":
                score += 20
                reasons.append("medium priority")
            else:
                score += 10
                reasons.append("low priority")

            due_delta = self._days_until_due(due_date_raw)
            if due_delta is not None:
                if due_delta < 0:
                    score += 40
                    reasons.append("overdue")
                elif due_delta == 0:
                    score += 30
                    reasons.append("due today")
                elif due_delta <= 2:
                    score += 20
                    reasons.append("due soon")

            ranked.append(
                {
                    "id": task.get("id"),
                    "content": content,
                    "status": status,
                    "priority": priority,
                    "due_date": due_date_raw,
                    "score": round(score, 2),
                    "reason": ", ".join(reasons),
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

    def generate_productivity_insights(
        self,
        tasks: List[Dict[str, Any]],
        passwords: List[Dict[str, Any]],
        files: List[Dict[str, Any]],
    ) -> str:
        """Generate higher-level usage and productivity insights."""
        total_tasks = len(tasks)
        completed = len([t for t in tasks if t.get("status") == "completed"])
        completion_rate = (completed / total_tasks * 100) if total_tasks else 0
        overdue = len([t for t in tasks if self._is_overdue(t.get("due_date")) and t.get("status") != "completed"])

        total_passwords = len(passwords)
        weakly_tagged_passwords = len([p for p in passwords if len(p.get("tags", [])) < 1])
        total_files = len(files)
        untagged_files = len([f for f in files if len(f.get("tags", [])) < 1])

        baseline = (
            "Productivity Insights\n"
            f"- Tasks: {total_tasks} total, {completed} completed ({completion_rate:.1f}%)\n"
            f"- Overdue tasks: {overdue}\n"
            f"- Password vault: {total_passwords} entries, {weakly_tagged_passwords} untagged\n"
            f"- Files: {total_files} entries, {untagged_files} untagged\n"
            "- Recommendation: complete high-priority overdue items first, then improve tagging quality for faster retrieval."
        )

        if not self.enabled:
            return baseline

        prompt = (
            "Generate actionable productivity insights in under 180 words. "
            "Include sections: Performance, Risks, Improvement Plan. "
            "Use this data:\n\n"
            f"{baseline}"
        )
        ai_text = self._chat(prompt)
        return ai_text if ai_text else baseline

    def _rerank_with_llm(self, query: str, items: List[Dict[str, Any]], item_type: str) -> List[Dict[str, Any]]:
        lines = []
        index_map: Dict[str, Dict[str, Any]] = {}

        for idx, item in enumerate(items, 1):
            key = str(idx)
            index_map[key] = item
            lines.append(f"{idx}. {self._build_search_text(item, item_type)}")

        prompt = (
            "You are ranking search results by relevance. "
            "Return only a JSON array of ranked item numbers.\n"
            f"Query: {query}\n"
            f"Items:\n{chr(10).join(lines)}"
        )

        ranked_ids = self._chat_json_array(prompt)
        if not ranked_ids:
            return []

        ranked: List[Dict[str, Any]] = []
        seen = set()
        for item_id in ranked_ids:
            key = str(item_id).strip()
            if key in index_map and key not in seen:
                seen.add(key)
                ranked.append(index_map[key])

        return ranked

    def _chat(self, prompt: str) -> Optional[str]:
        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": "You are a helpful productivity assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 350,
        }

        try:
            response = requests.post(
                self.CHAT_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            choices = body.get("choices", [])
            if not choices:
                return None
            content = choices[0].get("message", {}).get("content", "").strip()
            return content or None
        except Exception as e:
            logger.error(f"Hugging Face chat request failed: {e}")
            return None

    def _chat_json_array(self, prompt: str) -> List[str]:
        response_text = self._chat(prompt)
        if not response_text:
            return []

        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, list):
                return [str(item).strip().lower() for item in parsed if str(item).strip()]
        except Exception:
            pass

        match = re.search(r"\[[^\]]*\]", response_text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    return [str(item).strip().lower() for item in parsed if str(item).strip()]
            except Exception:
                return []

        return []

    def _build_search_text(self, item: Dict[str, Any], item_type: str) -> str:
        if item_type == "passwords":
            return f"service {item.get('service_name', '')} tags {' '.join(item.get('tags', []))}"
        if item_type == "tasks":
            return (
                f"task {item.get('encrypted_content', '')} "
                f"priority {item.get('priority', '')} status {item.get('status', '')} "
                f"tags {' '.join(item.get('tags', []))}"
            )
        if item_type == "files":
            return (
                f"file {item.get('file_name', '')} type {item.get('file_type', '')} "
                f"tags {' '.join(item.get('tags', []))}"
            )
        return str(item)

    def _score_text_relevance(self, query: str, query_tokens: List[str], item_text: str) -> float:
        if not item_text:
            return 0

        score = 0.0

        if query in item_text:
            score += 60

        item_tokens = self._tokenize(item_text)
        if query_tokens and item_tokens:
            overlap = len(set(query_tokens).intersection(set(item_tokens)))
            score += overlap * 10
            score += SequenceMatcher(None, " ".join(query_tokens), " ".join(item_tokens[:20])).ratio() * 25

        return score

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").lower()).strip()

    def _tokenize(self, value: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", value)

    def _clean_tags(self, tags: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen = set()

        for tag in tags:
            normalized = re.sub(r"[^a-z0-9_-]", "", str(tag).strip().lower())
            if not normalized or len(normalized) < 2:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(normalized)

        return cleaned

    def _stopwords(self) -> set:
        return {
            "this", "that", "with", "from", "your", "have", "will", "into", "about", "task",
            "file", "password", "item", "items", "and", "the", "for", "you", "are", "all",
        }

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    def _days_until_due(self, due_date: Optional[str]) -> Optional[int]:
        parsed = self._parse_datetime(due_date)
        if not parsed:
            return None

        now = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return (parsed.date() - now.date()).days

    def _is_overdue(self, due_date: Optional[str]) -> bool:
        delta = self._days_until_due(due_date)
        return delta is not None and delta < 0
