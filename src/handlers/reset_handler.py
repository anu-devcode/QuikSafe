"""
QuikSafe Bot - Master Password Reset Handler
Provides a secure Telegram-based recovery flow for forgotten master passwords.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any, Dict, Optional

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from src.database.db_manager import DatabaseManager
from src.security.auth import AuthManager, SessionManager


AWAITING_RESET_CODE = 1
AWAITING_NEW_MASTER_PASSWORD = 2


class ResetHandler:
    """Handles secure recovery when users forget their master password."""

    RESET_CODE_EXPIRY_MINUTES = 10
    RESET_COOLDOWN_MINUTES = 15
    RESET_VERIFY_WINDOW_MINUTES = 10
    RESET_MAX_ATTEMPTS = 5

    def __init__(self, db: DatabaseManager, auth: AuthManager, session: SessionManager, support_admin_ids: Optional[set[int]] = None):
        self.db = db
        self.auth = auth
        self.session = session
        self.support_admin_ids = support_admin_ids or set()

    async def start_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start reset flow by issuing a one-time recovery code."""
        user = update.effective_user
        telegram_id = user.id

        self._clear_reset_flow_context(context)

        if self.session.is_authenticated(telegram_id):
            await update.message.reply_text(
                "✅ You are already authenticated.\n"
                "Use Settings > Security > Change Master Pass for normal password updates."
            )
            self._clear_reset_flow_context(context)
            return ConversationHandler.END

        db_user = self.db.get_user_by_telegram_id(telegram_id)
        if not db_user:
            await update.message.reply_text(
                "❌ No account found for this Telegram user.\n"
                "Use /start to create your account first."
            )
            self._clear_reset_flow_context(context)
            return ConversationHandler.END

        settings = self._get_settings(db_user)
        reset_state = self._get_reset_state(settings)
        now = self._utcnow()

        locked_until = self._parse_datetime(reset_state.get("locked_until"))
        if locked_until and locked_until > now:
            remaining = int((locked_until - now).total_seconds() // 60) + 1
            await update.message.reply_text(
                f"⛔ Recovery is temporarily locked due to failed attempts. Try again in about {remaining} minutes."
            )
            self._clear_reset_flow_context(context)
            return ConversationHandler.END

        last_requested_at = self._parse_datetime(reset_state.get("last_requested_at"))
        if last_requested_at and now < last_requested_at + timedelta(minutes=self.RESET_COOLDOWN_MINUTES):
            remaining = int(((last_requested_at + timedelta(minutes=self.RESET_COOLDOWN_MINUTES)) - now).total_seconds() // 60) + 1
            await update.message.reply_text(
                f"⏳ A reset was requested recently. Please wait about {remaining} minutes before requesting another code."
            )
            self._clear_reset_flow_context(context)
            return ConversationHandler.END

        code = self._generate_code()
        salt = secrets.token_hex(16)
        code_hash = self._hash_code(telegram_id, code, salt)

        new_reset_state = {
            "status": "code_sent",
            "code_hash": code_hash,
            "salt": salt,
            "attempts": 0,
            "max_attempts": self.RESET_MAX_ATTEMPTS,
            "expires_at": self._to_iso(now + timedelta(minutes=self.RESET_CODE_EXPIRY_MINUTES)),
            "last_requested_at": self._to_iso(now),
            "verified_until": None,
            "locked_until": None,
        }

        self._set_reset_state(settings, new_reset_state)
        if not self.db.update_user_settings(db_user["id"], settings):
            await update.message.reply_text("❌ Failed to start password reset. Please try again later.")
            self._clear_reset_flow_context(context)
            return ConversationHandler.END

        context.user_data["reset_user_id"] = db_user["id"]
        context.user_data["in_reset_flow"] = True

        await update.message.reply_text(
            "🔐 **Master Password Recovery**\n\n"
            "A one-time recovery code has been generated for this Telegram account.\n"
            f"Recovery code: **{code}**\n\n"
            f"This code expires in {self.RESET_CODE_EXPIRY_MINUTES} minutes and allows up to {self.RESET_MAX_ATTEMPTS} attempts.\n"
            "Reply with the code now to continue.\n\n"
            "⚠️ If this was not you, ignore this message.",
            parse_mode="Markdown",
        )
        return AWAITING_RESET_CODE

    async def verify_reset_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Verify one-time recovery code."""
        user = update.effective_user
        telegram_id = user.id
        entered_code = (update.message.text or "").strip()

        db_user = self.db.get_user_by_telegram_id(telegram_id)
        if not db_user:
            await update.message.reply_text("❌ Account not found. Use /start first.")
            self._clear_reset_flow_context(context)
            return ConversationHandler.END

        settings = self._get_settings(db_user)
        reset_state = self._get_reset_state(settings)
        now = self._utcnow()

        expires_at = self._parse_datetime(reset_state.get("expires_at"))
        if reset_state.get("status") != "code_sent" or not expires_at or expires_at <= now:
            self._clear_reset_state(settings)
            self.db.update_user_settings(db_user["id"], settings)
            await update.message.reply_text("❌ Reset code expired or invalid. Use /resetmaster to request a new code.")
            self._clear_reset_flow_context(context)
            return ConversationHandler.END

        if not entered_code.isdigit():
            await update.message.reply_text("❌ Code must contain only numbers. Please try again:")
            return AWAITING_RESET_CODE

        salt = reset_state.get("salt", "")
        expected_hash = reset_state.get("code_hash", "")
        provided_hash = self._hash_code(telegram_id, entered_code, salt)

        if not hmac.compare_digest(provided_hash, expected_hash):
            attempts = int(reset_state.get("attempts", 0)) + 1
            reset_state["attempts"] = attempts

            if attempts >= self.RESET_MAX_ATTEMPTS:
                reset_state["status"] = "locked"
                reset_state["locked_until"] = self._to_iso(now + timedelta(minutes=self.RESET_COOLDOWN_MINUTES))
                reset_state.pop("code_hash", None)
                reset_state.pop("salt", None)
                self._set_reset_state(settings, reset_state)
                self.db.update_user_settings(db_user["id"], settings)
                await update.message.reply_text(
                    "⛔ Too many invalid attempts. Recovery is temporarily locked.\n"
                    f"Please retry with /resetmaster in {self.RESET_COOLDOWN_MINUTES} minutes."
                )
                self._clear_reset_flow_context(context)
                return ConversationHandler.END

            self._set_reset_state(settings, reset_state)
            self.db.update_user_settings(db_user["id"], settings)
            remaining = self.RESET_MAX_ATTEMPTS - attempts
            await update.message.reply_text(
                f"❌ Invalid code. You have {remaining} attempt(s) remaining."
            )
            return AWAITING_RESET_CODE

        reset_state["status"] = "verified"
        reset_state["verified_until"] = self._to_iso(now + timedelta(minutes=self.RESET_VERIFY_WINDOW_MINUTES))
        reset_state.pop("code_hash", None)
        reset_state.pop("salt", None)
        self._set_reset_state(settings, reset_state)

        if not self.db.update_user_settings(db_user["id"], settings):
            await update.message.reply_text("❌ Failed to verify reset code. Please try /resetmaster again.")
            self._clear_reset_flow_context(context)
            return ConversationHandler.END

        await update.message.reply_text(
            "✅ Code verified.\n\n"
            "Now enter your new master password. It must include uppercase, lowercase, a number, and a special character."
        )
        return AWAITING_NEW_MASTER_PASSWORD

    async def set_new_master_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Finalize reset by saving new master password hash."""
        user = update.effective_user
        telegram_id = user.id
        new_password = (update.message.text or "").strip()

        db_user = self.db.get_user_by_telegram_id(telegram_id)
        if not db_user:
            await update.message.reply_text("❌ Account not found. Use /start first.")
            self._clear_reset_flow_context(context)
            return ConversationHandler.END

        settings = self._get_settings(db_user)
        reset_state = self._get_reset_state(settings)
        now = self._utcnow()

        verified_until = self._parse_datetime(reset_state.get("verified_until"))
        if reset_state.get("status") != "verified" or not verified_until or verified_until <= now:
            self._clear_reset_state(settings)
            self.db.update_user_settings(db_user["id"], settings)
            await update.message.reply_text("❌ Verification window expired. Please run /resetmaster again.")
            self._clear_reset_flow_context(context)
            return ConversationHandler.END

        is_valid, error = self.auth.validate_password_strength(new_password)
        if not is_valid:
            await update.message.reply_text(f"❌ {error}\n\nPlease enter a stronger password:")
            return AWAITING_NEW_MASTER_PASSWORD

        new_hash = self.auth.hash_password(new_password)
        if not self.db.update_master_password_by_user_id(db_user["id"], new_hash):
            await update.message.reply_text("❌ Failed to update your master password. Please try again later.")
            self._clear_reset_flow_context(context)
            return ConversationHandler.END

        self._clear_reset_state(settings)
        self.db.update_user_settings(db_user["id"], settings)

        self.session.delete_session(telegram_id)
        self._clear_reset_flow_context(context)

        try:
            await update.message.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "✅ Master password reset successful.\n"
            "For security, please run /start and log in with your new password."
        )
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel reset flow."""
        self._clear_reset_flow_context(context)
        await update.message.reply_text("Recovery cancelled. Use /resetmaster if you need it again.")
        return ConversationHandler.END

    @staticmethod
    def _clear_reset_flow_context(context: ContextTypes.DEFAULT_TYPE):
        """Clear temporary reset flow flags from user context."""
        context.user_data.pop("reset_user_id", None)
        context.user_data.pop("in_reset_flow", None)

    def get_handler(self) -> ConversationHandler:
        """Return conversation handler for secure reset flow."""
        return ConversationHandler(
            entry_points=[CommandHandler("resetmaster", self.start_reset)],
            states={
                AWAITING_RESET_CODE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.verify_reset_code)
                ],
                AWAITING_NEW_MASTER_PASSWORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_new_master_password)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            allow_reentry=True,
        )

    def get_admin_handler(self) -> CommandHandler:
        """Admin-only handler for unlocking a user's reset state."""
        return CommandHandler("adminreset", self.admin_reset_unlock)

    async def admin_reset_unlock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear reset lockout/cooldown for a user without touching their password hash."""
        requester = update.effective_user
        if not requester or requester.id not in self.support_admin_ids:
            await update.message.reply_text("❌ Unauthorized.")
            return

        if not context.args:
            await update.message.reply_text(
                "Usage: /adminreset <telegram_id>\n"
                "Example: /adminreset 123456789"
            )
            return

        raw_target = context.args[0].strip()
        if not raw_target.isdigit():
            await update.message.reply_text("❌ telegram_id must be numeric.")
            return

        target_telegram_id = int(raw_target)
        target_user = self.db.get_user_by_telegram_id(target_telegram_id)
        if not target_user:
            await update.message.reply_text("❌ User not found for that telegram_id.")
            return

        settings = self._get_settings(target_user)
        self._clear_reset_state(settings)

        if not self.db.update_user_settings(target_user["id"], settings):
            await update.message.reply_text("❌ Failed to clear reset state.")
            return

        # In-memory session invalidation for this running bot instance.
        self.session.delete_session(target_telegram_id)

        await update.message.reply_text(
            "✅ Reset lockout state cleared.\n"
            "User should now run /resetmaster to recover access securely."
        )

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _to_iso(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _generate_code() -> str:
        return str(secrets.randbelow(900000) + 100000)

    @staticmethod
    def _hash_code(telegram_id: int, code: str, salt: str) -> str:
        payload = f"{telegram_id}:{code}:{salt}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _get_settings(user_row: Dict[str, Any]) -> Dict[str, Any]:
        settings = user_row.get("settings")
        if isinstance(settings, dict):
            return settings
        return {}

    @staticmethod
    def _get_reset_state(settings: Dict[str, Any]) -> Dict[str, Any]:
        security = settings.get("security", {})
        if not isinstance(security, dict):
            return {}
        reset = security.get("master_password_reset", {})
        return reset if isinstance(reset, dict) else {}

    @staticmethod
    def _set_reset_state(settings: Dict[str, Any], reset_state: Dict[str, Any]):
        security = settings.get("security")
        if not isinstance(security, dict):
            security = {}
            settings["security"] = security
        security["master_password_reset"] = reset_state

    @staticmethod
    def _clear_reset_state(settings: Dict[str, Any]):
        security = settings.get("security")
        if isinstance(security, dict):
            security.pop("master_password_reset", None)
