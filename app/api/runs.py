"""API endpoints for agent runs."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.logging import get_run_tracker, RunStatus


router = APIRouter(prefix="/api/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    """Request to create a new run."""
    name: str
    description: str = ""
    platform: str = "amazon"
    metadata: dict | None = None


class RunResponse(BaseModel):
    """Response for a run."""
    id: int
    name: str
    description: str
    platform: str
    status: str
    started_at: str | None
    completed_at: str | None
    duration_ms: int | None
    error_message: str | None
    steps: list[dict] = []

    class Config:
        from_attributes = True


@router.get("")
async def list_runs(
    platform: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List all runs with optional filtering."""
    tracker = get_run_tracker()

    run_status = RunStatus(status) if status else None
    runs = tracker.get_runs(platform=platform, status=run_status, limit=limit, offset=offset)

    return {
        "runs": [
            {
                "id": run.id,
                "name": run.name,
                "description": run.description,
                "platform": run.platform,
                "status": run.status.value,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "duration_ms": run.duration_ms,
                "error_message": run.error_message,
                "step_count": len(run.steps),
            }
            for run in runs
        ],
        "count": len(runs),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{run_id}")
async def get_run(run_id: int):
    """Get a run by ID with all steps."""
    tracker = get_run_tracker()

    try:
        run = tracker.get_run(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return {
        "id": run.id,
        "name": run.name,
        "description": run.description,
        "platform": run.platform,
        "status": run.status.value,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_ms": run.duration_ms,
        "error_message": run.error_message,
        "metadata": run.metadata,
        "steps": [
            {
                "id": step.id,
                "name": step.name,
                "description": step.description,
                "status": step.status.value,
                "screenshot_path": step.screenshot_path,
                "error_message": step.error_message,
                "started_at": step.started_at.isoformat() if step.started_at else None,
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                "duration_ms": step.duration_ms,
                "metadata": step.metadata,
            }
            for step in run.steps
        ],
    }


@router.post("")
async def create_run(request: CreateRunRequest):
    """Create a new run."""
    tracker = get_run_tracker()
    run = tracker.create_run(
        name=request.name,
        description=request.description,
        platform=request.platform,
        metadata=request.metadata,
    )

    return {
        "id": run.id,
        "name": run.name,
        "description": run.description,
        "platform": run.platform,
        "status": run.status.value,
    }


@router.post("/{run_id}/start")
async def start_run(run_id: int):
    """Start a run."""
    tracker = get_run_tracker()

    try:
        run = tracker.start_run(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return {"status": "started", "run_id": run.id}


@router.post("/{run_id}/complete")
async def complete_run(run_id: int, success: bool = True, error_message: str | None = None):
    """Complete a run."""
    tracker = get_run_tracker()

    try:
        run = tracker.complete_run(run_id, success=success, error_message=error_message)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return {
        "status": run.status.value,
        "run_id": run.id,
        "duration_ms": run.duration_ms,
    }


@router.post("/{run_id}/screenshot")
async def capture_screenshot(run_id: int, step_id: int | None = None, name: str = "screenshot"):
    """Capture a screenshot for a run."""
    tracker = get_run_tracker()

    try:
        tracker.get_run(run_id)  # Verify run exists
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    screenshot_path = await tracker.capture_screenshot(run_id, step_id, name)

    if screenshot_path is None:
        raise HTTPException(status_code=500, detail="Failed to capture screenshot")

    return {"screenshot_path": screenshot_path}
