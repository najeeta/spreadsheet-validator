"""Tests for PipelineState model — Story 1.2."""

import pytest
from pydantic import ValidationError

from app.models import PipelineState


class TestPipelineStateDefaults:
    """PipelineState should be constructable with all defaults."""

    def test_default_construction(self):
        state = PipelineState()
        assert state is not None

    def test_default_status_is_idle(self):
        state = PipelineState()
        assert state.status == "IDLE"

    def test_default_dataframe_records_empty(self):
        state = PipelineState()
        assert state.dataframe_records == []

    def test_default_dataframe_columns_empty(self):
        state = PipelineState()
        assert state.dataframe_columns == []

    def test_default_pending_fixes_empty(self):
        state = PipelineState()
        assert state.pending_fixes == []

    def test_default_artifacts_empty(self):
        state = PipelineState()
        assert state.artifacts == {}


class TestPipelineStateStatusValues:
    """All 10 status values should be accepted."""

    @pytest.mark.parametrize(
        "status",
        [
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
        ],
    )
    def test_valid_status(self, status: str):
        state = PipelineState(status=status)
        assert state.status == status

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            PipelineState(status="INVALID")

    def test_invalid_status_bogus_raises(self):
        with pytest.raises(ValidationError):
            PipelineState(status="NOT_A_STATUS")


class TestPipelineStateNoUIEvents:
    """Plan A does not use A2UI events — no ui_events field."""

    def test_no_ui_events_field(self):
        state = PipelineState()
        assert not hasattr(state, "ui_events")

    def test_ui_events_not_in_model_fields(self):
        assert "ui_events" not in PipelineState.model_fields
