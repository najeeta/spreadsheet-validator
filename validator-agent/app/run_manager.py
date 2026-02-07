"""RunManager — tracks background pipeline runs and coordinates HITL resume."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from google.adk.runners import Runner
from google.genai.types import Content, Part

from app.fix_utils import apply_skip_all

logger = logging.getLogger(__name__)

HITL_TIMEOUT_SECONDS = 300  # 5 minutes


@dataclass
class RunContext:
    """Tracks a single background pipeline run."""

    run_id: str
    task: Optional[asyncio.Task] = None
    resume_event: asyncio.Event = field(default_factory=asyncio.Event)
    created_at: float = field(default_factory=time.time)
    error: Optional[str] = None
    completed: bool = False


class RunManager:
    """Manages background pipeline runs."""

    def __init__(self) -> None:
        self._runs: dict[str, RunContext] = {}

    def create_run(self, run_id: str) -> RunContext:
        """Register a new run. Raises ValueError if run_id already exists."""
        if run_id in self._runs:
            raise ValueError(f"Run '{run_id}' already exists.")
        ctx = RunContext(run_id=run_id)
        self._runs[run_id] = ctx
        return ctx

    def get_run(self, run_id: str) -> Optional[RunContext]:
        """Get a run context by ID, or None if not found."""
        return self._runs.get(run_id)

    def signal_resume(self, run_id: str) -> None:
        """Set the resume event to wake up the background pipeline loop."""
        ctx = self._runs.get(run_id)
        if ctx:
            ctx.resume_event.set()
            logger.info("[RunManager] Signalled resume for run %s", run_id)

    def remove_run(self, run_id: str) -> None:
        """Remove a run from tracking."""
        self._runs.pop(run_id, None)


# Module-level singleton
run_manager = RunManager()


async def run_pipeline(
    run_ctx: RunContext,
    runner: Runner,
    session_id: str,
    user_id: str,
    filename: str,
) -> None:
    """Background agent loop: runs the ADK agent and handles HITL pauses.

    1. Send initial message telling the agent the file is uploaded.
    2. Consume all events from runner.run_async().
    3. After each turn, check session status:
       - COMPLETED/FAILED: done
       - WAITING_FOR_USER: pause until resume_event or timeout
       - Other: send nudge to continue
    """
    try:
        # Initial turn — tell the agent to process the file
        message = Content(
            role="user",
            parts=[Part(text=f"File '{filename}' uploaded. Please process it.")],
        )

        while True:
            # Run one agent turn
            async for _event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=message,
            ):
                pass  # consume all events

            # Check session state after the turn
            session = await runner._session_service.get_session(
                app_name=runner._app_name,
                user_id=user_id,
                session_id=session_id,
            )
            if not session:
                run_ctx.error = "Session not found after agent turn"
                run_ctx.completed = True
                return

            status = session.state.get("status", "")
            logger.info("[run_pipeline] After turn, status=%s for run %s", status, run_ctx.run_id)

            if status in ("COMPLETED", "FAILED"):
                run_ctx.completed = True
                if status == "FAILED":
                    run_ctx.error = session.state.get("error_message", "Pipeline failed")
                return

            if status == "WAITING_FOR_USER":
                # Pause and wait for /answers to signal resume
                run_ctx.resume_event.clear()
                try:
                    await asyncio.wait_for(
                        run_ctx.resume_event.wait(),
                        timeout=HITL_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "[run_pipeline] HITL timeout for run %s — auto-skipping all",
                        run_ctx.run_id,
                    )
                    # Re-fetch session to get latest state
                    session = await runner._session_service.get_session(
                        app_name=runner._app_name,
                        user_id=user_id,
                        session_id=session_id,
                    )
                    if session:
                        apply_skip_all(session.state)

                # Re-fetch session to check if fixes were applied
                session = await runner._session_service.get_session(
                    app_name=runner._app_name,
                    user_id=user_id,
                    session_id=session_id,
                )
                if not session:
                    run_ctx.error = "Session lost during HITL wait"
                    run_ctx.completed = True
                    return

                current_status = session.state.get("status", "")
                if current_status in ("RUNNING", "FIXING"):
                    message = Content(
                        role="user",
                        parts=[Part(text="Fixes applied. Please re-validate and continue.")],
                    )
                else:
                    message = Content(
                        role="user",
                        parts=[Part(text="Please continue processing.")],
                    )
            else:
                # Safety nudge for unexpected statuses
                message = Content(
                    role="user",
                    parts=[Part(text="Please continue processing.")],
                )

    except Exception:
        logger.exception("[run_pipeline] Error in background pipeline for run %s", run_ctx.run_id)
        run_ctx.error = "Internal pipeline error"
        run_ctx.completed = True
        # Try to mark session as FAILED
        try:
            session = await runner._session_service.get_session(
                app_name=runner._app_name,
                user_id=user_id,
                session_id=session_id,
            )
            if session:
                session.state["status"] = "FAILED"
                session.state["error_message"] = "Internal pipeline error"
        except Exception:
            logger.exception("[run_pipeline] Failed to mark session as FAILED")
