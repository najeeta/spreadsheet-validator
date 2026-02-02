"""Tests for ingestion tools — Story 2.1."""

import pathlib
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from app.tools.ingestion import ingest_file, ingest_uploaded_file, request_file_upload

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


class TestIngestUploadedFile:
    """ingest_uploaded_file reads from ADK ArtifactService."""

    @pytest.mark.asyncio
    async def test_loads_artifact_and_parses(self):
        # Create a CSV in memory
        df = pd.DataFrame(
            {
                "employee_id": ["EMP001"],
                "dept": ["Engineering"],
                "amount": [1000.0],
                "currency": ["USD"],
                "spend_date": ["2024-01-15"],
                "vendor": ["Test Corp"],
                "fx_rate": [1.0],
            }
        )
        csv_bytes = df.to_csv(index=False).encode()

        ctx = MagicMock()
        ctx.state = {"uploaded_file": "upload_test.csv"}
        artifact_mock = MagicMock()
        artifact_mock.inline_data.data = csv_bytes
        artifact_mock.inline_data.mime_type = "text/csv"
        ctx.load_artifact = AsyncMock(return_value=artifact_mock)

        result = await ingest_uploaded_file(ctx)
        assert result["status"] == "success"
        assert result["row_count"] == 1
        assert ctx.state["status"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_no_uploaded_file_returns_error(self):
        ctx = MagicMock()
        ctx.state = {}
        ctx.load_artifact = AsyncMock(return_value=None)
        result = await ingest_uploaded_file(ctx)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_artifact_not_found_returns_error(self):
        ctx = MagicMock()
        ctx.state = {"uploaded_file": "missing.csv"}
        ctx.load_artifact = AsyncMock(return_value=None)
        result = await ingest_uploaded_file(ctx)
        assert result["status"] == "error"
