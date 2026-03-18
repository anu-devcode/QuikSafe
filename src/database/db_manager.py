"""
QuikSafe Bot - Database Manager
Handles all database operations with PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import uuid

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages all database operations for QuikSafe Bot."""

    def __init__(
        self,
        database_url: str,
        min_pool_size: int = 1,
        max_pool_size: int = 10,
        connect_timeout: int = 10,
    ):
        """
        Initialize PostgreSQL connection pool.

        Args:
            database_url: PostgreSQL connection URL
            min_pool_size: Minimum pooled connections
            max_pool_size: Maximum pooled connections
            connect_timeout: Connection timeout in seconds
        """
        if not database_url:
            raise ValueError("DATABASE_URL is required")

        self.database_url = database_url
        self.pool = ConnectionPool(
            conninfo=database_url,
            min_size=max(1, min_pool_size),
            max_size=max(max_pool_size, min_pool_size),
            kwargs={
                "connect_timeout": connect_timeout,
                "row_factory": dict_row,
            },
            open=True,
        )
        logger.info("PostgreSQL connection pool established")

    def initialize_database(self):
        """Apply schema and SQL migrations on startup."""
        logger.info("Initializing database schema and migrations")
        self._apply_schema_file()
        self._ensure_migrations_table()
        self._apply_migrations()
        logger.info("Database initialization completed")

    # ==================== Bootstrap ====================

    def _apply_schema_file(self):
        schema_path = Path(__file__).resolve().parent / "schema.sql"
        schema_sql = schema_path.read_text(encoding="utf-8")

        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()

    def _ensure_migrations_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
        self._execute(sql)

    def _apply_migrations(self):
        migrations_dir = Path(__file__).resolve().parent / "migrations"
        if not migrations_dir.exists():
            return

        migration_files = sorted(migrations_dir.glob("*.sql"))
        if not migration_files:
            return

        applied = {row["name"] for row in self._fetchall("SELECT name FROM schema_migrations")}

        for file_path in migration_files:
            migration_name = file_path.name
            if migration_name in applied:
                continue

            sql = file_path.read_text(encoding="utf-8")
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (name) VALUES (%s)",
                        (migration_name,),
                    )
                conn.commit()
            logger.info(f"Applied migration: {migration_name}")

    # ==================== Core SQL Helpers ====================

    def _execute(self, sql: str, params: tuple = ()) -> bool:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            return False

    def _fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    row = cur.fetchone()
            return self._normalize_row(row) if row else None
        except Exception as e:
            logger.error(f"SQL fetchone failed: {e}")
            return None

    def _fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()
            return [self._normalize_row(row) for row in rows]
        except Exception as e:
            logger.error(f"SQL fetchall failed: {e}")
            return []

    def _normalize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for key, value in row.items():
            normalized[key] = self._normalize_value(value)
        return normalized

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        if isinstance(value, list):
            return [self._normalize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._normalize_value(v) for k, v in value.items()}
        return value

    # ==================== User Operations ====================

    def create_user(self, telegram_id: int, master_password_hash: str) -> Optional[Dict[str, Any]]:
        sql = """
        INSERT INTO users (telegram_id, master_password_hash)
        VALUES (%s, %s)
        RETURNING *;
        """
        return self._fetchone(sql, (telegram_id, master_password_hash))

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM users WHERE telegram_id = %s LIMIT 1"
        return self._fetchone(sql, (telegram_id,))

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM users WHERE id = %s LIMIT 1"
        return self._fetchone(sql, (user_id,))

    def update_master_password(self, telegram_id: int, new_password_hash: str) -> bool:
        sql = """
        UPDATE users
        SET master_password_hash = %s, updated_at = NOW()
        WHERE telegram_id = %s
        """
        return self._execute(sql, (new_password_hash, telegram_id))

    def update_master_password_by_user_id(self, user_id: str, new_password_hash: str) -> bool:
        sql = """
        UPDATE users
        SET master_password_hash = %s, updated_at = NOW()
        WHERE id = %s
        """
        return self._execute(sql, (new_password_hash, user_id))

    def get_user_settings(self, user_id: str) -> Dict[str, Any]:
        sql = "SELECT settings FROM users WHERE id = %s LIMIT 1"
        row = self._fetchone(sql, (user_id,))
        return row.get("settings", {}) if row else {}

    def update_user_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        sql = """
        UPDATE users
        SET settings = %s::jsonb, updated_at = NOW()
        WHERE id = %s
        """
        return self._execute(sql, (json.dumps(settings), user_id))

    # ==================== Password Operations ====================

    def save_password(
        self,
        user_id: str,
        service_name: str,
        encrypted_username: str,
        encrypted_password: str,
        tags: List[str] = None,
        notes: str = None,
    ) -> Optional[Dict[str, Any]]:
        sql = """
        INSERT INTO passwords (user_id, service_name, encrypted_username, encrypted_password, tags, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *;
        """
        return self._fetchone(
            sql,
            (user_id, service_name, encrypted_username, encrypted_password, tags or [], notes),
        )

    def get_passwords(self, user_id: str, service_name: Optional[str] = None) -> List[Dict[str, Any]]:
        if service_name:
            sql = """
            SELECT * FROM passwords
            WHERE user_id = %s AND service_name ILIKE %s
            ORDER BY created_at DESC
            """
            return self._fetchall(sql, (user_id, f"%{service_name}%"))

        sql = "SELECT * FROM passwords WHERE user_id = %s ORDER BY created_at DESC"
        return self._fetchall(sql, (user_id,))

    def update_password(self, password_id: str, encrypted_password: str) -> bool:
        sql = """
        UPDATE passwords
        SET encrypted_password = %s, updated_at = NOW()
        WHERE id = %s
        """
        return self._execute(sql, (encrypted_password, password_id))

    def delete_password(self, password_id: str, user_id: str) -> bool:
        sql = "DELETE FROM passwords WHERE id = %s AND user_id = %s"
        return self._execute(sql, (password_id, user_id))

    def update_password_tags(self, password_id: str, tags: List[str]) -> bool:
        sql = """
        UPDATE passwords
        SET tags = %s, updated_at = NOW()
        WHERE id = %s
        """
        return self._execute(sql, (tags, password_id))

    # ==================== Task Operations ====================

    def create_task(
        self,
        user_id: str,
        encrypted_content: str,
        priority: str = "medium",
        due_date: Optional[datetime] = None,
        tags: List[str] = None,
    ) -> Optional[Dict[str, Any]]:
        sql = """
        INSERT INTO tasks (user_id, encrypted_content, priority, due_date, tags)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *;
        """
        return self._fetchone(sql, (user_id, encrypted_content, priority, due_date, tags or []))

    def get_tasks(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if status:
            sql = "SELECT * FROM tasks WHERE user_id = %s AND status = %s ORDER BY created_at DESC"
            return self._fetchall(sql, (user_id, status))

        sql = "SELECT * FROM tasks WHERE user_id = %s ORDER BY created_at DESC"
        return self._fetchall(sql, (user_id,))

    def get_task_by_id(self, task_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM tasks WHERE id = %s AND user_id = %s LIMIT 1"
        return self._fetchone(sql, (task_id, user_id))

    def update_task_status(self, task_id: str, user_id: str, status: str) -> bool:
        completed_at = datetime.now(timezone.utc) if status == "completed" else None
        sql = """
        UPDATE tasks
        SET status = %s, completed_at = %s, updated_at = NOW()
        WHERE id = %s AND user_id = %s
        """
        return self._execute(sql, (status, completed_at, task_id, user_id))

    def delete_task(self, task_id: str, user_id: str) -> bool:
        sql = "DELETE FROM tasks WHERE id = %s AND user_id = %s"
        return self._execute(sql, (task_id, user_id))

    def update_task_tags(self, task_id: str, tags: List[str]) -> bool:
        sql = """
        UPDATE tasks
        SET tags = %s, updated_at = NOW()
        WHERE id = %s
        """
        return self._execute(sql, (tags, task_id))

    # ==================== File Operations ====================

    def save_file(
        self,
        user_id: str,
        file_id: str,
        file_name: str,
        file_type: str,
        file_size: int,
        encrypted_description: str = None,
        tags: List[str] = None,
    ) -> Optional[Dict[str, Any]]:
        sql = """
        INSERT INTO files (user_id, file_id, file_name, file_type, file_size, encrypted_description, tags)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *;
        """
        return self._fetchone(
            sql,
            (user_id, file_id, file_name, file_type, file_size, encrypted_description, tags or []),
        )

    def get_files(self, user_id: str, file_name: Optional[str] = None) -> List[Dict[str, Any]]:
        if file_name:
            sql = """
            SELECT * FROM files
            WHERE user_id = %s AND file_name ILIKE %s
            ORDER BY created_at DESC
            """
            return self._fetchall(sql, (user_id, f"%{file_name}%"))

        sql = "SELECT * FROM files WHERE user_id = %s ORDER BY created_at DESC"
        return self._fetchall(sql, (user_id,))

    def delete_file(self, file_id: str, user_id: str) -> bool:
        sql = "DELETE FROM files WHERE id = %s AND user_id = %s"
        return self._execute(sql, (file_id, user_id))

    def update_file_tags(self, file_id: str, tags: List[str]) -> bool:
        sql = """
        UPDATE files
        SET tags = %s, updated_at = NOW()
        WHERE id = %s
        """
        return self._execute(sql, (tags, file_id))
