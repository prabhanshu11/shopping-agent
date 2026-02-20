"""Agent run tracker with screenshot capture support.

This module provides tracking for complete agent "runs" - discrete tasks
like "Add items to cart" or "Login to Amazon". Each run contains:
- A sequence of steps with screenshots
- Status tracking (pending/running/success/failed)
- Timing information
- Error details

The web UI uses this data to visualize agent activity.
"""

import asyncio
import base64
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
import json
import sqlite3
from contextlib import contextmanager
import httpx


class RunStatus(str, Enum):
    """Status of an agent run."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Status of a step within a run."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Step:
    """A step in an agent run."""
    id: int | None = None
    run_id: int | None = None
    name: str = ""
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    screenshot_path: str | None = None
    screenshot_data: bytes | None = None  # For in-memory transfer
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Run:
    """An agent run - a complete task like 'Add to cart'."""
    id: int | None = None
    name: str = ""
    description: str = ""
    platform: str = "amazon"
    status: RunStatus = RunStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    steps: list[Step] = field(default_factory=list)
    error_message: str | None = None
    metadata: dict = field(default_factory=dict)


class RunTracker:
    """Tracker for agent runs with screenshot support."""

    def __init__(
        self,
        db_path: str | None = None,
        screenshots_dir: str | None = None,
        ui_agent_url: str = "http://localhost:8000",
    ):
        """Initialize run tracker.

        Args:
            db_path: Path to SQLite database
            screenshots_dir: Directory to store screenshots
            ui_agent_url: URL of UI-Agent for taking screenshots
        """
        base_dir = Path(__file__).parent.parent.parent

        if db_path is None:
            log_dir = base_dir / "logs"
            log_dir.mkdir(exist_ok=True)
            db_path = str(log_dir / "runs.db")

        if screenshots_dir is None:
            screenshots_dir = str(base_dir / "static" / "screenshots")

        self.db_path = db_path
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.ui_agent_url = ui_agent_url
        self._http_client: httpx.AsyncClient | None = None

        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    platform TEXT DEFAULT 'amazon',
                    status TEXT DEFAULT 'pending',
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    duration_ms INTEGER,
                    error_message TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    step_order INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    screenshot_path TEXT,
                    error_message TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    duration_ms INTEGER,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs(id)
                );

                CREATE INDEX IF NOT EXISTS idx_steps_run ON steps(run_id);
                CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
                CREATE INDEX IF NOT EXISTS idx_runs_platform ON runs(platform);
            """)

    @contextmanager
    def _get_conn(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get HTTP client for UI-Agent."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.ui_agent_url,
                timeout=30.0,
            )
        return self._http_client

    async def close(self):
        """Close resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    # Run management

    def create_run(self, name: str, description: str = "", platform: str = "amazon", metadata: dict | None = None) -> Run:
        """Create a new run.

        Args:
            name: Run name (e.g., "Add items to cart")
            description: Detailed description
            platform: Platform name
            metadata: Additional data

        Returns:
            Created Run object
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO runs (name, description, platform, metadata)
                   VALUES (?, ?, ?, ?)""",
                (name, description, platform, json.dumps(metadata) if metadata else None)
            )
            run_id = cursor.lastrowid

        return Run(
            id=run_id,
            name=name,
            description=description,
            platform=platform,
            metadata=metadata or {},
        )

    def start_run(self, run_id: int) -> Run:
        """Mark a run as started.

        Args:
            run_id: Run ID

        Returns:
            Updated Run object
        """
        now = datetime.utcnow()
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE runs SET status = ?, started_at = ? WHERE id = ?""",
                (RunStatus.RUNNING.value, now.isoformat(), run_id)
            )

        return self.get_run(run_id)

    def complete_run(self, run_id: int, success: bool, error_message: str | None = None) -> Run:
        """Mark a run as complete.

        Args:
            run_id: Run ID
            success: Whether run succeeded
            error_message: Error message if failed

        Returns:
            Updated Run object
        """
        run = self.get_run(run_id)
        now = datetime.utcnow()

        duration_ms = None
        if run.started_at:
            duration_ms = int((now - run.started_at).total_seconds() * 1000)

        status = RunStatus.SUCCESS if success else RunStatus.FAILED

        with self._get_conn() as conn:
            conn.execute(
                """UPDATE runs SET status = ?, completed_at = ?, duration_ms = ?, error_message = ?
                   WHERE id = ?""",
                (status.value, now.isoformat(), duration_ms, error_message, run_id)
            )

        return self.get_run(run_id)

    def get_run(self, run_id: int) -> Run:
        """Get a run by ID.

        Args:
            run_id: Run ID

        Returns:
            Run object
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE id = ?", (run_id,)
            ).fetchone()

            if not row:
                raise ValueError(f"Run {run_id} not found")

            steps_rows = conn.execute(
                "SELECT * FROM steps WHERE run_id = ? ORDER BY step_order",
                (run_id,)
            ).fetchall()

        steps = [
            Step(
                id=s["id"],
                run_id=s["run_id"],
                name=s["name"],
                description=s["description"] or "",
                status=StepStatus(s["status"]),
                screenshot_path=s["screenshot_path"],
                error_message=s["error_message"],
                started_at=datetime.fromisoformat(s["started_at"]) if s["started_at"] else None,
                completed_at=datetime.fromisoformat(s["completed_at"]) if s["completed_at"] else None,
                duration_ms=s["duration_ms"],
                metadata=json.loads(s["metadata"]) if s["metadata"] else {},
            )
            for s in steps_rows
        ]

        return Run(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            platform=row["platform"],
            status=RunStatus(row["status"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            duration_ms=row["duration_ms"],
            steps=steps,
            error_message=row["error_message"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def get_runs(
        self,
        platform: str | None = None,
        status: RunStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Run]:
        """Get runs with optional filtering.

        Args:
            platform: Filter by platform
            status: Filter by status
            limit: Max runs to return
            offset: Offset for pagination

        Returns:
            List of Run objects
        """
        query = "SELECT * FROM runs WHERE 1=1"
        params = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            Run(
                id=row["id"],
                name=row["name"],
                description=row["description"] or "",
                platform=row["platform"],
                status=RunStatus(row["status"]),
                started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                duration_ms=row["duration_ms"],
                error_message=row["error_message"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            for row in rows
        ]

    # Step management

    def add_step(self, run_id: int, name: str, description: str = "", metadata: dict | None = None) -> Step:
        """Add a step to a run.

        Args:
            run_id: Parent run ID
            name: Step name
            description: Step description
            metadata: Additional data

        Returns:
            Created Step object
        """
        with self._get_conn() as conn:
            # Get next step order
            row = conn.execute(
                "SELECT MAX(step_order) as max_order FROM steps WHERE run_id = ?",
                (run_id,)
            ).fetchone()
            step_order = (row["max_order"] or 0) + 1

            cursor = conn.execute(
                """INSERT INTO steps (run_id, step_order, name, description, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (run_id, step_order, name, description, json.dumps(metadata) if metadata else None)
            )
            step_id = cursor.lastrowid

        return Step(
            id=step_id,
            run_id=run_id,
            name=name,
            description=description,
            metadata=metadata or {},
        )

    def start_step(self, step_id: int) -> Step:
        """Mark a step as started.

        Args:
            step_id: Step ID

        Returns:
            Updated Step object
        """
        now = datetime.utcnow()
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE steps SET status = ?, started_at = ? WHERE id = ?""",
                (StepStatus.RUNNING.value, now.isoformat(), step_id)
            )
            row = conn.execute("SELECT * FROM steps WHERE id = ?", (step_id,)).fetchone()

        return Step(
            id=row["id"],
            run_id=row["run_id"],
            name=row["name"],
            description=row["description"] or "",
            status=StepStatus(row["status"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
        )

    def complete_step(
        self,
        step_id: int,
        success: bool,
        error_message: str | None = None,
        screenshot_path: str | None = None,
    ) -> Step:
        """Mark a step as complete.

        Args:
            step_id: Step ID
            success: Whether step succeeded
            error_message: Error if failed
            screenshot_path: Path to screenshot

        Returns:
            Updated Step object
        """
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM steps WHERE id = ?", (step_id,)).fetchone()
            started_at = datetime.fromisoformat(row["started_at"]) if row["started_at"] else None

            now = datetime.utcnow()
            duration_ms = None
            if started_at:
                duration_ms = int((now - started_at).total_seconds() * 1000)

            status = StepStatus.SUCCESS if success else StepStatus.FAILED

            conn.execute(
                """UPDATE steps SET status = ?, completed_at = ?, duration_ms = ?,
                   error_message = ?, screenshot_path = ?
                   WHERE id = ?""",
                (status.value, now.isoformat(), duration_ms, error_message, screenshot_path, step_id)
            )

            row = conn.execute("SELECT * FROM steps WHERE id = ?", (step_id,)).fetchone()

        return Step(
            id=row["id"],
            run_id=row["run_id"],
            name=row["name"],
            description=row["description"] or "",
            status=StepStatus(row["status"]),
            screenshot_path=row["screenshot_path"],
            error_message=row["error_message"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            duration_ms=row["duration_ms"],
        )

    # Screenshot support

    async def capture_screenshot(self, run_id: int, step_id: int | None = None, name: str = "screenshot") -> str | None:
        """Capture a screenshot from UI-Agent.

        Args:
            run_id: Run ID (for organizing screenshots)
            step_id: Optional step ID
            name: Screenshot name

        Returns:
            Path to saved screenshot, or None if failed
        """
        try:
            client = await self._get_http_client()
            response = await client.get("/browser/screenshot")

            if response.status_code != 200:
                return None

            # Create run directory
            run_dir = self.screenshots_dir / f"run_{run_id}"
            run_dir.mkdir(exist_ok=True)

            # Generate filename
            timestamp = datetime.utcnow().strftime("%H%M%S")
            if step_id:
                filename = f"step_{step_id}_{name}_{timestamp}.png"
            else:
                filename = f"{name}_{timestamp}.png"

            filepath = run_dir / filename
            filepath.write_bytes(response.content)

            # Return relative path for web serving
            return f"/static/screenshots/run_{run_id}/{filename}"

        except Exception as e:
            print(f"Screenshot capture failed: {e}")
            return None

    async def execute_step(
        self,
        run_id: int,
        name: str,
        action: callable,
        description: str = "",
        capture_before: bool = True,
        capture_after: bool = True,
        metadata: dict | None = None,
    ) -> tuple[Step, Any]:
        """Execute a step with automatic tracking and screenshots.

        Args:
            run_id: Parent run ID
            name: Step name
            action: Async callable to execute
            description: Step description
            capture_before: Take screenshot before action
            capture_after: Take screenshot after action
            metadata: Additional data

        Returns:
            Tuple of (Step, action result)
        """
        step = self.add_step(run_id, name, description, metadata)
        step = self.start_step(step.id)

        result = None
        error_message = None
        success = False
        screenshot_path = None

        try:
            # Screenshot before
            if capture_before:
                await self.capture_screenshot(run_id, step.id, f"{name}_before")

            # Execute action
            result = await action()
            success = True

            # Screenshot after
            if capture_after:
                screenshot_path = await self.capture_screenshot(run_id, step.id, f"{name}_after")

        except Exception as e:
            error_message = str(e)
            # Capture error state
            screenshot_path = await self.capture_screenshot(run_id, step.id, f"{name}_error")

        step = self.complete_step(step.id, success, error_message, screenshot_path)
        return step, result


# Global tracker instance
_tracker: RunTracker | None = None


def get_run_tracker() -> RunTracker:
    """Get the global run tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = RunTracker()
    return _tracker
