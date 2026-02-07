"""Shared data models for the Spreadsheet Validator pipeline."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Status = Literal[
    "IDLE",
    "UPLOADING",
    "RUNNING",
    "VALIDATING",
    "WAITING_FOR_USER",
    "FIXING",
    "TRANSFORMING",
    "PACKAGING",
    "COMPLETED",
    "FAILED",
]


class PipelineState(BaseModel):
    """Shared pipeline state stored in ADK session.

    Tools read and write this state. The frontend subscribes to state
    changes via useCoAgentStateRender to render appropriate cards.
    """

    status: Status = "IDLE"
    file_name: Optional[str] = None
    dataframe_records: list[dict] = []
    dataframe_columns: list[str] = []
    pending_fixes: list[dict] = []
    skipped_fixes: list[dict] = []
    remaining_fixes: list[dict] = []
    waiting_since: Optional[float] = None
    total_error_rows: int = 0
    artifacts: dict[str, str] = {}
    globals: Optional[dict] = None  # RunGlobals from frontend (e.g. cost_center_map)
