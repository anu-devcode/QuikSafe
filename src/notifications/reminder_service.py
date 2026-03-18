"""Scheduled reminder engine for retention-focused bot notifications."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict
import logging

from telegram.ext import ContextTypes

from src.database.db_manager import DatabaseManager
from src.security.encryption import EncryptionManager
from src.analytics import AnalyticsTracker

logger = logging.getLogger(__name__)


class ReminderService:
    """Sends periodic nudges based on user data and notification settings."""

    def __init__(
        self,
        db: DatabaseManager,
        encryption: EncryptionManager,
        analytics: AnalyticsTracker,
        due_soon_hours: int = 24,
        inactivity_hours: int = 72,
    ):
        self.db = db
        self.encryption = encryption
        self.analytics = analytics
        self.due_soon_hours = max(1, due_soon_hours)
        self.inactivity_hours = max(24, inactivity_hours)

    async def run_task_reminders(self, context: ContextTypes.DEFAULT_TYPE):
        """Send due-soon reminders once per day per user."""
        now = datetime.now(timezone.utc)
        today_key = now.date().isoformat()

        for user in self.db.get_all_users():
            telegram_id = user.get("telegram_id")
            user_id = user.get("id")
            settings = self._settings(user)
            notifications = settings.get("notifications", {})

            if not notifications.get("tasks", True):
                continue

            if self._is_in_quiet_hours(notifications, now):
                continue

            reminder_window_hours = int(notifications.get("reminder_window_hours", self.due_soon_hours) or self.due_soon_hours)
            reminder_window_hours = max(1, reminder_window_hours)

            if notifications.get("last_task_reminder_date") == today_key:
                continue

            due_soon = self.db.get_due_soon_tasks(user_id, reminder_window_hours)
            if not due_soon:
                continue

            first_title = self._safe_task_preview(due_soon[0])
            message = (
                "Reminder: you have tasks due soon.\n"
                f"Due in next {reminder_window_hours}h: {len(due_soon)}\n"
                f"Top item: {first_title}\n\n"
                "Open the bot and tap Task Planner to continue."
            )

            try:
                await context.bot.send_message(chat_id=telegram_id, text=message)
                notifications["last_task_reminder_date"] = today_key
                self._mark_notification_sent(notifications, now, "task_reminder")
                settings["notifications"] = notifications
                self.db.update_user_settings(user_id, settings)
                self.analytics.track(
                    "notification_task_reminder_sent",
                    telegram_id=telegram_id,
                    user_id=user_id,
                    metadata={"count": len(due_soon)},
                )
            except Exception as exc:
                logger.debug("Task reminder skipped for %s: %s", telegram_id, exc)

    async def run_weekly_summary(self, context: ContextTypes.DEFAULT_TYPE):
        """Send a compact weekly summary once per week to opted-in users."""
        now = datetime.now(timezone.utc)
        iso_year, iso_week, _ = now.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"

        for user in self.db.get_all_users():
            telegram_id = user.get("telegram_id")
            user_id = user.get("id")
            settings = self._settings(user)
            notifications = settings.get("notifications", {})

            if not notifications.get("summary", False):
                continue

            if self._is_in_quiet_hours(notifications, now):
                continue

            if notifications.get("last_weekly_summary_week") == week_key:
                continue

            overview = self.db.get_user_task_overview(user_id)
            if sum(overview.values()) == 0:
                continue

            message = (
                "Weekly snapshot:\n"
                f"Pending: {overview['pending']}\n"
                f"In progress: {overview['in_progress']}\n"
                f"Completed: {overview['completed']}\n"
                f"Overdue high priority: {overview['overdue_high']}\n\n"
                "Tip: start with one high-impact task today."
            )

            try:
                await context.bot.send_message(chat_id=telegram_id, text=message)
                notifications["last_weekly_summary_week"] = week_key
                self._mark_notification_sent(notifications, now, "weekly_summary")
                settings["notifications"] = notifications
                self.db.update_user_settings(user_id, settings)
                self.analytics.track(
                    "notification_weekly_summary_sent",
                    telegram_id=telegram_id,
                    user_id=user_id,
                )
            except Exception as exc:
                logger.debug("Weekly summary skipped for %s: %s", telegram_id, exc)

    async def run_inactivity_nudges(self, context: ContextTypes.DEFAULT_TYPE):
        """Send gentle nudges to inactive users with unfinished work."""
        now = datetime.now(timezone.utc)

        for user in self.db.get_all_users():
            telegram_id = user.get("telegram_id")
            user_id = user.get("id")
            settings = self._settings(user)
            notifications = settings.get("notifications", {})
            if self._is_in_quiet_hours(notifications, now):
                continue

            inactivity_hours = int(notifications.get("inactivity_nudge_hours", self.inactivity_hours) or self.inactivity_hours)
            inactivity_hours = max(24, inactivity_hours)

            last_nudge_raw = notifications.get("last_inactivity_nudge_at")
            if last_nudge_raw:
                try:
                    last_nudge = datetime.fromisoformat(last_nudge_raw.replace("Z", "+00:00"))
                    hours_since_nudge = (now - last_nudge.astimezone(timezone.utc)).total_seconds() / 3600
                    if hours_since_nudge < inactivity_hours:
                        continue
                except Exception:
                    pass

            last_seen_raw = notifications.get("last_seen_at")
            if not last_seen_raw:
                continue

            try:
                last_seen = datetime.fromisoformat(last_seen_raw.replace("Z", "+00:00"))
                hours_since_seen = (now - last_seen.astimezone(timezone.utc)).total_seconds() / 3600
            except Exception:
                continue

            if hours_since_seen < inactivity_hours:
                continue

            overview = self.db.get_user_task_overview(user_id)
            if overview["pending"] <= 0 and overview["overdue_high"] <= 0:
                continue

            message = (
                "We miss you in QuikSafe.\n"
                f"You still have {overview['pending']} pending task(s)"
                f" and {overview['overdue_high']} overdue high-priority task(s).\n"
                "Jump back in and clear one task now."
            )

            try:
                await context.bot.send_message(chat_id=telegram_id, text=message)
                notifications["last_inactivity_nudge_at"] = now.isoformat()
                self._mark_notification_sent(notifications, now, "inactivity_nudge")
                settings["notifications"] = notifications
                self.db.update_user_settings(user_id, settings)
                self.analytics.track(
                    "notification_inactivity_nudge_sent",
                    telegram_id=telegram_id,
                    user_id=user_id,
                )
            except Exception as exc:
                logger.debug("Inactivity nudge skipped for %s: %s", telegram_id, exc)

    def mark_seen(self, user_id: str, telegram_id: int, settings: Dict[str, Any]):
        """Persist last user activity timestamp in settings."""
        now = datetime.now(timezone.utc)
        notifications = settings.get("notifications")
        if not isinstance(notifications, dict):
            notifications = {}
        notifications["last_seen_at"] = now.isoformat()

        sent_at_raw = notifications.get("last_notification_sent_at")
        sent_type = notifications.get("last_notification_type")
        reengaged_marker = notifications.get("last_notification_reengaged_at")

        if sent_at_raw and sent_type and sent_at_raw != reengaged_marker:
            try:
                sent_at = datetime.fromisoformat(sent_at_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
                delta_hours = (now - sent_at).total_seconds() / 3600
                if 0 <= delta_hours <= 24:
                    self.analytics.track(
                        "notification_reengaged",
                        telegram_id=telegram_id,
                        user_id=user_id,
                        metadata={
                            "notification_type": sent_type,
                            "hours_since_notification": round(delta_hours, 2),
                        },
                    )
                    notifications["last_notification_reengaged_at"] = sent_at_raw
            except Exception:
                pass

        settings["notifications"] = notifications
        self.db.update_user_settings(user_id, settings)

    def _settings(self, user: Dict[str, Any]) -> Dict[str, Any]:
        settings = user.get("settings")
        if isinstance(settings, dict):
            return settings
        return {}

    def _safe_task_preview(self, task: Dict[str, Any]) -> str:
        try:
            encrypted = task.get("encrypted_content", "")
            if not encrypted:
                return "Untitled task"
            content = self.encryption.decrypt(encrypted)
            content = (content or "Untitled task").strip()
            return content[:60]
        except Exception:
            return "Task item"

    def _is_in_quiet_hours(self, notifications: Dict[str, Any], now_utc: datetime) -> bool:
        """Check whether notifications should be suppressed for this local user time."""
        if not notifications.get("quiet_hours_enabled", False):
            return False

        try:
            offset_minutes = int(notifications.get("timezone_offset_minutes", 0) or 0)
            local_time = now_utc + timedelta(minutes=offset_minutes)
            local_minutes = local_time.hour * 60 + local_time.minute
            start = (int(notifications.get("quiet_hours_start", 22) or 22) % 24) * 60
            end = (int(notifications.get("quiet_hours_end", 8) or 8) % 24) * 60
        except Exception:
            return False

        if start == end:
            return True
        if start < end:
            return start <= local_minutes < end
        return local_minutes >= start or local_minutes < end

    @staticmethod
    def _mark_notification_sent(notifications: Dict[str, Any], now: datetime, notification_type: str):
        notifications["last_notification_sent_at"] = now.isoformat()
        notifications["last_notification_type"] = notification_type
