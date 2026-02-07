"""Tests for ingestion tools — Story 2.1."""

import pathlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tools.ingestion import (
    confirm_ingestion,
    ingest_file,
    ingest_uploaded_file,
    request_file_upload,
)

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"


class TestRequestFileUpload:
    """request_file_upload returns a dict signaling the UI to show upload dialog."""

    def test_returns_waiting_status(self):
        ctx = MagicMock()
        ctx.state = {}
        result = request_file_upload(ctx)
        assert result["status"] == "waiting_for_upload"

    def test_returns_accepted_formats(self):
        ctx = MagicMock()
        ctx.state = {}
        result = request_file_upload(ctx)
        assert "accepted_formats" in result
        assert ".csv" in result["accepted_formats"]
        assert ".xlsx" in result["accepted_formats"]

    def test_sets_uploading_status(self):
        ctx = MagicMock()
        ctx.state = {}
        request_file_upload(ctx)
        assert ctx.state["status"] == "UPLOADING"


class TestConfirmIngestion:
    """confirm_ingestion checks records in state and sets RUNNING."""

    def test_success_with_records(self):
        ctx = MagicMock()
        ctx.state = {
            "dataframe_records": [{"a": 1}, {"a": 2}],
            "dataframe_columns": ["a"],
            "file_name": "test.csv",
        }
        result = confirm_ingestion(ctx)
        assert result["status"] == "success"
        assert result["row_count"] == 2
        assert ctx.state["status"] == "RUNNING"

    def test_error_without_records(self):
        ctx = MagicMock()
        ctx.state = {"dataframe_records": [], "dataframe_columns": []}
        result = confirm_ingestion(ctx)
        assert result["status"] == "error"

    def test_returns_file_name(self):
        ctx = MagicMock()
        ctx.state = {
            "dataframe_records": [{"a": 1}],
            "dataframe_columns": ["a"],
            "file_name": "expenses.xlsx",
        }
        result = confirm_ingestion(ctx)
        assert result["file_name"] == "expenses.xlsx"

    def test_returns_columns(self):
        ctx = MagicMock()
        ctx.state = {
            "dataframe_records": [{"x": 1, "y": 2}],
            "dataframe_columns": ["x", "y"],
            "file_name": "data.csv",
        }
        result = confirm_ingestion(ctx)
        assert result["columns"] == ["x", "y"]


class TestIngestFile:
    """ingest_file reads CSV/XLSX from disk and populates state."""

    def test_reads_csv(self):
        ctx = MagicMock()
        ctx.state = {}
        csv_path = str(FIXTURES / "test_data.csv")
        result = ingest_file(ctx, file_path=csv_path)
        assert result["status"] == "success"
        assert result["row_count"] == 3
        assert "employee_id" in result["columns"]

    def test_populates_state_records(self):
        ctx = MagicMock()
        ctx.state = {}
        csv_path = str(FIXTURES / "test_data.csv")
        ingest_file(ctx, file_path=csv_path)
        assert len(ctx.state["dataframe_records"]) == 3

    def test_populates_state_columns(self):
        ctx = MagicMock()
        ctx.state = {}
        csv_path = str(FIXTURES / "test_data.csv")
        ingest_file(ctx, file_path=csv_path)
        assert "employee_id" in ctx.state["dataframe_columns"]
        assert "dept" in ctx.state["dataframe_columns"]

    def test_sets_status_running(self):
        ctx = MagicMock()
        ctx.state = {}
        csv_path = str(FIXTURES / "test_data.csv")
        ingest_file(ctx, file_path=csv_path)
        assert ctx.state["status"] == "RUNNING"

    def test_unsupported_extension_returns_error(self):
        ctx = MagicMock()
        ctx.state = {}
        result = ingest_file(ctx, file_path="/tmp/data.json")
        assert result["status"] == "error"

    def test_missing_file_returns_error(self):
        ctx = MagicMock()
        ctx.state = {}
        result = ingest_file(ctx, file_path="/tmp/nonexistent_file.csv")
        assert result["status"] == "error"


class TestReIngestionStateReset:
    """Re-ingesting a file clears stale validation state."""

    def _ingest(self, **pre_state):
        ctx = MagicMock()
        ctx.state = {**pre_state}
        csv_path = str(FIXTURES / "test_data.csv")
        result = ingest_file(ctx, file_path=csv_path)
        assert result["status"] == "success"
        return ctx

    def test_clears_pending_fixes(self):
        ctx = self._ingest(
            pending_fixes=[
                {
                    "row_index": 0,
                    "field": "dept",
                    "current_value": "BAD",
                    "error_message": "Invalid",
                }
            ]
        )
        assert ctx.state["pending_fixes"] == []

    def test_clears_skipped_fixes(self):
        ctx = self._ingest(
            skipped_fixes=[
                {
                    "row_index": 0,
                    "field": "dept",
                    "current_value": "BAD",
                    "error_message": "Skipped",
                }
            ]
        )
        assert ctx.state["skipped_fixes"] == []

    def test_clears_total_error_rows(self):
        ctx = self._ingest(total_error_rows=5)
        assert ctx.state["total_error_rows"] == 0

    def test_clears_validation_complete(self):
        ctx = self._ingest(validation_complete=True)
        assert not ctx.state["validation_complete"]

    def test_clears_waiting_since(self):
        ctx = self._ingest(waiting_since=12345)
        assert ctx.state["waiting_since"] is None


class TestReIngestionStripsOutputColumns:
    """Re-ingesting a file that contains output columns (e.g. errors.xlsx) strips them."""

    def test_strips_error_reason_column(self):
        import tempfile

        csv = "employee_id,dept,amount,currency,spend_date,vendor,fx_rate,error_reason\nEMP001,ENG,1500,USD,2024-01-15,Acme,1.0,some error\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv)
            tmp = f.name
        ctx = MagicMock()
        ctx.state = {}
        result = ingest_file(ctx, file_path=tmp)
        assert result["status"] == "success"
        assert "error_reason" not in ctx.state["dataframe_columns"]
        for rec in ctx.state["dataframe_records"]:
            assert "error_reason" not in rec
        import os

        os.unlink(tmp)

    def test_strips_computed_columns(self):
        import tempfile

        csv = "employee_id,dept,amount,currency,spend_date,vendor,fx_rate,amount_usd,cost_center,approval_required\nEMP001,ENG,1500,USD,2024-01-15,Acme,1.0,1500,300,NO\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv)
            tmp = f.name
        ctx = MagicMock()
        ctx.state = {}
        result = ingest_file(ctx, file_path=tmp)
        assert result["status"] == "success"
        for col in ("amount_usd", "cost_center", "approval_required"):
            assert col not in ctx.state["dataframe_columns"]
            for rec in ctx.state["dataframe_records"]:
                assert col not in rec
        import os

        os.unlink(tmp)

    def test_preserves_original_data_columns(self):
        import tempfile

        csv = "employee_id,dept,amount,currency,spend_date,vendor,fx_rate,error_reason\nEMP001,ENG,1500,USD,2024-01-15,Acme,1.0,some error\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv)
            tmp = f.name
        ctx = MagicMock()
        ctx.state = {}
        result = ingest_file(ctx, file_path=tmp)
        assert result["status"] == "success"
        for col in ("employee_id", "dept", "amount", "currency", "spend_date", "vendor", "fx_rate"):
            assert col in ctx.state["dataframe_columns"]
        import os

        os.unlink(tmp)


class TestIngestUploadedFile:
    """ingest_uploaded_file uses tool_context.load_artifact (backend-agnostic)."""

    def _make_csv_artifact(self, csv_bytes: bytes):
        """Create a mock artifact with inline_data matching the ADK Part shape."""
        artifact = MagicMock()
        artifact.inline_data.data = csv_bytes
        return artifact

    @pytest.mark.asyncio
    async def test_calls_tool_context_load_artifact(self):
        csv = b"employee_id,dept,amount\nEMP001,ENG,1500\n"
        artifact = self._make_csv_artifact(csv)

        ctx = MagicMock()
        ctx.state = {}
        ctx.load_artifact = AsyncMock(return_value=artifact)

        result = await ingest_uploaded_file(ctx, file_name="test.csv")

        ctx.load_artifact.assert_called_once_with(filename="test.csv")
        assert result["status"] == "success"
        assert result["row_count"] == 1
        assert "employee_id" in result["columns"]

    @pytest.mark.asyncio
    async def test_populates_state(self):
        csv = b"employee_id,dept,amount\nEMP001,ENG,1500\nEMP002,HR,2000\n"
        artifact = self._make_csv_artifact(csv)

        ctx = MagicMock()
        ctx.state = {}
        ctx.load_artifact = AsyncMock(return_value=artifact)

        await ingest_uploaded_file(ctx, file_name="data.csv")

        assert len(ctx.state["dataframe_records"]) == 2
        assert "employee_id" in ctx.state["dataframe_columns"]
        assert ctx.state["file_name"] == "data.csv"
        assert ctx.state["status"] == "INGESTING"

    @pytest.mark.asyncio
    async def test_artifact_not_found(self):
        ctx = MagicMock()
        ctx.state = {}
        ctx.load_artifact = AsyncMock(return_value=None)

        result = await ingest_uploaded_file(ctx, file_name="missing.csv")

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_unsupported_file_type(self):
        artifact = MagicMock()
        artifact.inline_data.data = b'{"a": 1}'

        ctx = MagicMock()
        ctx.state = {}
        ctx.load_artifact = AsyncMock(return_value=artifact)

        result = await ingest_uploaded_file(ctx, file_name="data.json")

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_tries_tool_context_first(self):
        """Verify tool_context.load_artifact is tried before artifact_service fallback."""
        csv = b"employee_id,dept,amount\nEMP001,ENG,1500\n"
        artifact = self._make_csv_artifact(csv)

        ctx = MagicMock()
        ctx.state = {}
        # tool_context.load_artifact succeeds — no fallback needed
        ctx.load_artifact = AsyncMock(return_value=artifact)

        result = await ingest_uploaded_file(ctx, file_name="test.csv")

        ctx.load_artifact.assert_called_once_with(filename="test.csv")
        assert result["status"] == "success"
