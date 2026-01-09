"""Action logging module for tracking AI agent operations.

This module provides structured logging for all cart operations,
navigation actions, and session health metrics. Logs are stored
in SQLite for easy querying and analysis.
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any
import json
import sqlite3
from contextlib import contextmanager


class ActionType(str, Enum):
    """Types of actions the agent can perform."""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    ADD_TO_CART = "add_to_cart"
    REMOVE_FROM_CART = "remove_from_cart"
    CHANGE_ADDRESS = "change_address"
    VERIFY_ADDRESS = "verify_address"
    CHECKOUT = "checkout"
    LOGIN = "login"
    SEARCH = "search"
    SCREENSHOT = "screenshot"
    EVALUATE = "evaluate"


class ActionStatus(str, Enum):
    """Status of an action."""
    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class ActionLogger:
    """Logger for tracking agent actions and outcomes."""

    def __init__(self, db_path: str | None = None):
        """Initialize action logger.

        Args:
            db_path: Path to SQLite database. Defaults to ./logs/actions.db
        """
        if db_path is None:
            log_dir = Path(__file__).parent.parent.parent / "logs"
            log_dir.mkdir(exist_ok=True)
            db_path = str(log_dir / "actions.db")

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    platform TEXT NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    login_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    target TEXT,
                    platform TEXT,
                    asin TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    duration_ms INTEGER,
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    context TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS cart_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    asin TEXT NOT NULL,
                    product_name TEXT,
                    quantity INTEGER DEFAULT 1,
                    operation TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    delivery_address TEXT,
                    price REAL,
                    currency TEXT DEFAULT 'INR',
                    warranty_modal_shown INTEGER DEFAULT 0,
                    address_verification_needed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (action_id) REFERENCES actions(id)
                );

                CREATE TABLE IF NOT EXISTS issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    action_id INTEGER,
                    issue_type TEXT NOT NULL,
                    description TEXT,
                    asin TEXT,
                    platform TEXT,
                    selector TEXT,
                    resolved INTEGER DEFAULT 0,
                    resolution TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (action_id) REFERENCES actions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_actions_session ON actions(session_id);
                CREATE INDEX IF NOT EXISTS idx_actions_type ON actions(action_type);
                CREATE INDEX IF NOT EXISTS idx_actions_asin ON actions(asin);
                CREATE INDEX IF NOT EXISTS idx_cart_ops_asin ON cart_operations(asin);
                CREATE INDEX IF NOT EXISTS idx_issues_type ON issues(issue_type);
            """)

    @contextmanager
    def _get_conn(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def start_session(self, platform: str, metadata: dict | None = None) -> str:
        """Start a new logging session.

        Args:
            platform: Platform name (e.g., 'amazon')
            metadata: Optional session metadata

        Returns:
            Session ID
        """
        session_id = f"{platform}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO sessions (session_id, platform, metadata)
                   VALUES (?, ?, ?)""",
                (session_id, platform, json.dumps(metadata) if metadata else None)
            )

        return session_id

    def end_session(self, session_id: str, status: str = "completed"):
        """End a logging session.

        Args:
            session_id: Session ID to end
            status: Final status (completed, failed, abandoned)
        """
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE sessions
                   SET ended_at = CURRENT_TIMESTAMP, status = ?
                   WHERE session_id = ?""",
                (status, session_id)
            )

    def log_action(
        self,
        session_id: str,
        action_type: ActionType,
        status: ActionStatus,
        target: str | None = None,
        platform: str | None = None,
        asin: str | None = None,
        duration_ms: int | None = None,
        retry_count: int = 0,
        error_message: str | None = None,
        context: dict | None = None,
    ) -> int:
        """Log an action.

        Args:
            session_id: Session this action belongs to
            action_type: Type of action
            status: Action status
            target: Target element/URL
            platform: Platform name
            asin: Product ASIN if applicable
            duration_ms: Action duration in milliseconds
            retry_count: Number of retries
            error_message: Error message if failed
            context: Additional context

        Returns:
            Action ID
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO actions
                   (session_id, action_type, status, target, platform, asin,
                    completed_at, duration_ms, retry_count, error_message, context)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)""",
                (
                    session_id,
                    action_type.value if isinstance(action_type, ActionType) else action_type,
                    status.value if isinstance(status, ActionStatus) else status,
                    target,
                    platform,
                    asin,
                    duration_ms,
                    retry_count,
                    error_message,
                    json.dumps(context) if context else None,
                )
            )
            return cursor.lastrowid

    def log_cart_operation(
        self,
        action_id: int,
        platform: str,
        asin: str,
        operation: str,
        success: bool,
        product_name: str | None = None,
        quantity: int = 1,
        delivery_address: str | None = None,
        price: float | None = None,
        warranty_modal_shown: bool = False,
        address_verification_needed: bool = False,
    ):
        """Log a cart operation.

        Args:
            action_id: Parent action ID
            platform: Platform name
            asin: Product ASIN
            operation: Operation type (add, remove, update_quantity)
            success: Whether operation succeeded
            product_name: Product name
            quantity: Quantity
            delivery_address: Delivery address used
            price: Product price
            warranty_modal_shown: Whether warranty modal appeared
            address_verification_needed: Whether address change was needed
        """
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO cart_operations
                   (action_id, platform, asin, product_name, quantity, operation,
                    success, delivery_address, price, warranty_modal_shown,
                    address_verification_needed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    action_id,
                    platform,
                    asin,
                    product_name,
                    quantity,
                    operation,
                    1 if success else 0,
                    delivery_address,
                    price,
                    1 if warranty_modal_shown else 0,
                    1 if address_verification_needed else 0,
                )
            )

    def log_issue(
        self,
        session_id: str,
        issue_type: str,
        description: str,
        action_id: int | None = None,
        asin: str | None = None,
        platform: str | None = None,
        selector: str | None = None,
    ) -> int:
        """Log an issue encountered.

        Args:
            session_id: Session ID
            issue_type: Type of issue (selector_not_found, timeout, etc.)
            description: Human-readable description
            action_id: Related action ID
            asin: Related product ASIN
            platform: Platform name
            selector: CSS selector that failed

        Returns:
            Issue ID
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO issues
                   (session_id, action_id, issue_type, description, asin, platform, selector)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, action_id, issue_type, description, asin, platform, selector)
            )
            return cursor.lastrowid

    def resolve_issue(self, issue_id: int, resolution: str):
        """Mark an issue as resolved.

        Args:
            issue_id: Issue ID to resolve
            resolution: How the issue was resolved
        """
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE issues SET resolved = 1, resolution = ? WHERE id = ?""",
                (resolution, issue_id)
            )

    # Analytics queries

    def get_cart_success_rate(
        self,
        platform: str | None = None,
        since_hours: int = 24,
    ) -> dict:
        """Get cart operation success rate.

        Args:
            platform: Filter by platform
            since_hours: Time window in hours

        Returns:
            Dictionary with success/failure counts and rate
        """
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)

        query = """
            SELECT
                COUNT(*) as total,
                SUM(success) as successes,
                COUNT(*) - SUM(success) as failures
            FROM cart_operations
            WHERE created_at >= ?
        """
        params = [cutoff.isoformat()]

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        with self._get_conn() as conn:
            row = conn.execute(query, params).fetchone()

        total = row["total"] or 0
        successes = row["successes"] or 0
        failures = row["failures"] or 0

        return {
            "total": total,
            "successes": successes,
            "failures": failures,
            "success_rate": (successes / total * 100) if total > 0 else 0,
            "since_hours": since_hours,
            "platform": platform,
        }

    def get_average_cart_time(
        self,
        platform: str | None = None,
        since_hours: int = 24,
    ) -> dict:
        """Get average time to add items to cart.

        Args:
            platform: Filter by platform
            since_hours: Time window in hours

        Returns:
            Dictionary with timing statistics
        """
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)

        query = """
            SELECT
                AVG(a.duration_ms) as avg_ms,
                MIN(a.duration_ms) as min_ms,
                MAX(a.duration_ms) as max_ms,
                COUNT(*) as count
            FROM actions a
            JOIN cart_operations c ON a.id = c.action_id
            WHERE a.started_at >= ?
            AND a.action_type = 'add_to_cart'
            AND a.duration_ms IS NOT NULL
        """
        params = [cutoff.isoformat()]

        if platform:
            query += " AND a.platform = ?"
            params.append(platform)

        with self._get_conn() as conn:
            row = conn.execute(query, params).fetchone()

        return {
            "avg_ms": row["avg_ms"] or 0,
            "min_ms": row["min_ms"] or 0,
            "max_ms": row["max_ms"] or 0,
            "count": row["count"] or 0,
            "since_hours": since_hours,
            "platform": platform,
        }

    def get_common_issues(
        self,
        limit: int = 10,
        since_hours: int = 168,  # 1 week
    ) -> list[dict]:
        """Get most common issues.

        Args:
            limit: Max issues to return
            since_hours: Time window in hours

        Returns:
            List of issue types with counts
        """
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)

        query = """
            SELECT
                issue_type,
                platform,
                COUNT(*) as count,
                SUM(resolved) as resolved_count
            FROM issues
            WHERE created_at >= ?
            GROUP BY issue_type, platform
            ORDER BY count DESC
            LIMIT ?
        """

        with self._get_conn() as conn:
            rows = conn.execute(query, (cutoff.isoformat(), limit)).fetchall()

        return [
            {
                "issue_type": row["issue_type"],
                "platform": row["platform"],
                "count": row["count"],
                "resolved_count": row["resolved_count"],
                "resolution_rate": (row["resolved_count"] / row["count"] * 100)
                    if row["count"] > 0 else 0,
            }
            for row in rows
        ]

    def get_failed_products(
        self,
        platform: str | None = None,
        since_hours: int = 168,
    ) -> list[dict]:
        """Get products that frequently fail to add to cart.

        Args:
            platform: Filter by platform
            since_hours: Time window in hours

        Returns:
            List of products with failure counts
        """
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)

        query = """
            SELECT
                asin,
                product_name,
                platform,
                COUNT(*) as attempts,
                SUM(success) as successes,
                COUNT(*) - SUM(success) as failures
            FROM cart_operations
            WHERE created_at >= ?
            AND success = 0
        """
        params = [cutoff.isoformat()]

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        query += """
            GROUP BY asin, platform
            HAVING failures > 0
            ORDER BY failures DESC
            LIMIT 20
        """

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            {
                "asin": row["asin"],
                "product_name": row["product_name"],
                "platform": row["platform"],
                "attempts": row["attempts"],
                "successes": row["successes"],
                "failures": row["failures"],
            }
            for row in rows
        ]


# Global logger instance
_logger: ActionLogger | None = None


def get_action_logger() -> ActionLogger:
    """Get the global action logger instance."""
    global _logger
    if _logger is None:
        _logger = ActionLogger()
    return _logger
