"""Pydantic request/response models for the async pipeline API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class CreateRunResponse(BaseModel):
    """Response from POST /runs."""

    run_id: str
    status: str  # "RUNNING"


class SingleFix(BaseModel):
    """A single cell fix."""

    row_index: int
    field: str
    new_value: Any


class RowFixes(BaseModel):
    """Batch fixes for one row."""

    row_index: int
    fixes: dict[str, Any]  # field -> new_value


class AnswerRequest(BaseModel):
    """Request body for POST /runs/{run_id}/answers."""

    fixes: Optional[list[SingleFix]] = None
    row_fixes: Optional[list[RowFixes]] = None
    skip_rows: Optional[list[int]] = None
    skip_all: bool = False


class AnswerResponse(BaseModel):
    """Response from POST /runs/{run_id}/answers."""

    status: str
    pending_review_count: int
    total_errors_remaining: int
    skipped_count: int
    applied_count: int
    message: str
