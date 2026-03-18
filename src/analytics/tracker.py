"""Lightweight analytics tracker with best-effort persistence."""

from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from src.database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class AnalyticsTracker:
    """Best-effort event tracking wrapper that never breaks user flows."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def track(
        self,
        event_name: str,
        telegram_id: Optional[int] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        try:
            self.db.track_event(
                event_name=event_name,
                telegram_id=telegram_id,
                user_id=user_id,
                metadata=metadata or {},
            )
        except Exception as exc:
            logger.debug("Analytics tracking skipped due to error: %s", exc)
