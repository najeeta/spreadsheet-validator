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
    active_run_id: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    uploaded_file: Optional[str] = None
    dataframe_records: list[dict] = []
    dataframe_columns: list[str] = []
    validation_errors: list[dict] = []
    validation_complete: bool = False
    pending_fixes: list[dict] = []
    artifacts: dict[str, str] = {}
    as_of: Optional[str] = None
    usd_rounding: Optional[Literal["cents", "whole"]] = "cents"
    cost_center_map: dict[str, str] = {}
